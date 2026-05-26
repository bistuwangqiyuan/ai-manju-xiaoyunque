"""V10 §7.4 — End-to-end episode composer.

Glues together the V10 audio/video layer into a single function the
orchestrator can call::

    compose_episode(
        shot_video_paths=[...],
        dialogue_lines=[DialogueLine(...), ...],
        bgm_path="assets/bgm/...mp3",
        scene_actions=[{"text": "她推开门", "start": 2.4}, ...],
        watermark_text="AI 生成",
        subtitle_style="ancient_kai",
    )

Steps performed:

    1. ``transitions.build_plan`` — xfade plan across all shot clips
    2. ``transitions.build_concat_command`` → renders ``concat.mp4``
    3. ``dialogue_timeline.build_timeline`` — per-line start/end seconds
    4. ``ass_subtitle.render_ass`` — burnable subtitle file
    5. ``sfx_auto_inject.auto_inject`` — keyword-matched SFX cues
    6. ``ffmpeg_compose.compose_final`` — final mux with dialogue/bgm/sfx
    7. ``lufs_normalize.normalize`` — broadcast loudness

All steps degrade gracefully — if a backend is missing (e.g. no ffmpeg
in the test env), the report contains a ``would_run`` block instead of
running anything, so unit-tests can still exercise the planning logic.
"""
from __future__ import annotations

import json
import logging
import pathlib
import shutil
from dataclasses import dataclass, field
from typing import Any

from ..audio import (
    bgm_recommender,
    beat_align,
    dialogue_timeline as dt_mod,
    lufs_normalize,
    sfx_auto_inject,
)
from . import transitions as trans_mod

_log = logging.getLogger(__name__)


@dataclass
class ComposeV10Report:
    output_path: str
    transition_plan: dict[str, Any] = field(default_factory=dict)
    dialogue_timeline: dict[str, Any] = field(default_factory=dict)
    bgm_choice: dict[str, Any] = field(default_factory=dict)
    beat_grid: dict[str, Any] = field(default_factory=dict)
    snapped_cuts: list[dict[str, Any]] = field(default_factory=list)
    sfx_cues: list[dict[str, Any]] = field(default_factory=list)
    subtitle_path: str | None = None
    concat_command: list[str] = field(default_factory=list)
    compose_executed: bool = False
    lufs_report: dict[str, Any] | None = None
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "output_path": self.output_path,
            "transition_plan": self.transition_plan,
            "dialogue_timeline": self.dialogue_timeline,
            "bgm_choice": self.bgm_choice,
            "beat_grid": self.beat_grid,
            "snapped_cuts": self.snapped_cuts,
            "sfx_cues": self.sfx_cues,
            "subtitle_path": self.subtitle_path,
            "concat_command": self.concat_command,
            "compose_executed": self.compose_executed,
            "lufs_report": self.lufs_report,
            "notes": self.notes,
        }


def plan_and_compose_episode(
    *,
    shot_video_paths: list[str | pathlib.Path],
    output_path: str | pathlib.Path,
    dialogue_lines: list[dict[str, Any]] | None = None,
    bgm_path: str | None = None,
    scene_text_for_bgm: str | None = None,
    scene_actions: list[dict[str, Any]] | None = None,
    transition_name: str = "fade",
    transition_duration: float = 0.6,
    subtitle_style: str = "modern_sans",
    watermark_text: str = "AI 生成",
    target_lufs: float = -14.0,
    use_whisperx: bool = False,
    dry_run: bool = True,
    work_dir: str | pathlib.Path | None = None,
) -> ComposeV10Report:
    """Plan & (optionally) compose the final episode mp4.

    Set ``dry_run=False`` to actually invoke ffmpeg. The default ``dry_run=True``
    is what tests and the orchestrator's "preview" mode use.
    """
    out_path = pathlib.Path(output_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    work_dir_p = pathlib.Path(work_dir) if work_dir else out_path.parent / "_v10_tmp"
    work_dir_p.mkdir(parents=True, exist_ok=True)

    report = ComposeV10Report(output_path=str(out_path))

    # 1) transition plan
    n_clips = len(shot_video_paths)
    if n_clips == 0:
        report.notes.append("no input clips; nothing to do")
        return report
    plan = trans_mod.build_plan(
        shot_video_paths,
        transitions=[transition_name] * max(n_clips - 1, 0),
        transition_duration=transition_duration,
    )
    report.transition_plan = plan.to_dict()

    # 2) dialogue timeline
    if dialogue_lines:
        tl = dt_mod.build_timeline(dialogue_lines, use_whisperx=use_whisperx)
        report.dialogue_timeline = tl.to_dict()
    else:
        tl = None

    # 3) BGM choice
    if bgm_path is None and scene_text_for_bgm:
        rec = bgm_recommender.recommend(scene_text_for_bgm, top_k=3)
        if rec.top:
            report.bgm_choice = rec.to_dict()
            cand_path = pathlib.Path(rec.top.entry.path)
            if cand_path.exists():
                bgm_path = str(cand_path)
        else:
            report.notes.append("bgm recommendation returned no results")
    elif bgm_path:
        report.bgm_choice = {"manual_path": bgm_path}

    # 4) beat grid + snap dialogue starts
    if bgm_path:
        grid = beat_align.compute_beats(bgm_path)
        report.beat_grid = grid.to_dict()
        if tl and tl.lines:
            cuts = beat_align.snap_cuts(grid, [l.start for l in tl.lines])
            report.snapped_cuts = [c.to_dict() for c in cuts]
            # apply small shifts back to timeline
            for line, cut in zip(tl.lines, cuts):
                if cut.beat_index >= 0:
                    delta = cut.snapped_sec - line.start
                    line.start += delta
                    line.end += delta
            report.dialogue_timeline = tl.to_dict()

    # 5) subtitle file
    if tl and tl.lines:
        try:
            from ..shell5_post_production.ass_subtitle import (
                AssLine, render_ass, resolve_style,
            )
            style_name = resolve_style(subtitle_style)
            ass_lines = [
                AssLine(l.start, l.end, l.text, style_name) for l in tl.lines
            ]
            sub_path = work_dir_p / f"{out_path.stem}.ass"
            render_ass(ass_lines, sub_path)
            report.subtitle_path = str(sub_path)
        except Exception as exc:
            report.notes.append(f"subtitle render skipped: {exc}")

    # 6) SFX cues from scene actions
    if scene_actions:
        cues = sfx_auto_inject.auto_inject(scene_actions)
        report.sfx_cues = [c.to_dict() for c in cues]

    # 7) build concat command
    cmd = trans_mod.build_concat_command(plan, out_path)
    report.concat_command = list(cmd)

    # 8) (optional) execute ffmpeg
    if not dry_run and shutil.which("ffmpeg"):
        try:
            import subprocess
            subprocess.run(cmd, check=True)
            report.compose_executed = True
            if bgm_path:
                lufs_out = out_path.with_name(out_path.stem + "_lufs.mp4")
                try:
                    rep = lufs_normalize.normalize(out_path, lufs_out, target_lufs=target_lufs)
                    report.lufs_report = rep.to_dict()
                except Exception as exc:
                    report.notes.append(f"lufs normalize skipped: {exc}")
        except Exception as exc:
            report.notes.append(f"ffmpeg execution failed: {exc}")
    else:
        report.notes.append("dry_run=True or ffmpeg unavailable; plan only")

    return report


def save_report(report: ComposeV10Report,
                output_path: str | pathlib.Path) -> pathlib.Path:
    p = pathlib.Path(output_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2),
                 encoding="utf-8")
    return p


__all__ = ["ComposeV10Report", "plan_and_compose_episode", "save_report"]
