"""V10 §5.1 — Storyboard layouter.

Generates a 9-25 panel storyboard layout for a single episode, weaving in
shot-reverse-shot (OTS) coverage for dialogue exchanges and camera-movement
suggestions for action beats.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

from src.visual.shot_size_coupler import plan_shot, build_shot_prompt_suffix, ShotPlanItem
from src.visual.expression_router import route as route_expression


SHOT_REVERSE_PATTERNS = ["OTS_A", "OTS_B", "MIDSHOT_BOTH", "CLOSEUP_A", "CLOSEUP_B"]


@dataclass
class StoryboardPanel:
    index: int
    scene_index: int
    speaker: str | None
    line: str | None
    emotion: str
    intensity: int
    atmosphere: str
    shot_plan: ShotPlanItem
    prompt_suffix: str
    grid_label: str
    is_reverse_shot: bool = False
    counterpart_index: int | None = None


@dataclass
class StoryboardLayout:
    episode: int
    panel_count: int
    panels: list[StoryboardPanel] = field(default_factory=list)


def _grid_size_for(n: int) -> tuple[int, int]:
    """Pick rows × cols for n panels (target square-ish)."""
    cols = math.ceil(math.sqrt(n))
    rows = math.ceil(n / cols)
    return rows, cols


def layout_episode(
    *,
    episode: int,
    scenes: list[dict],
    target_panel_count: int | None = None,
    atmosphere_default: str = "neutral",
) -> StoryboardLayout:
    """``scenes`` is a list of {heading, atmosphere, dialogue:[{speaker, line, emotion, intensity}], pov, is_climax}."""
    panels: list[StoryboardPanel] = []
    panel_idx = 1
    target = target_panel_count or min(25, max(9, 2 + sum(len(s.get("dialogue") or []) for s in scenes)))

    # First, lay out a master panel per scene
    for si, scene in enumerate(scenes, start=1):
        atm = (scene.get("atmosphere") or atmosphere_default)
        is_climax = bool(scene.get("is_climax"))
        # establishing master shot
        master_plan = plan_shot(emotion_intensity=2, atmosphere=atm,
                                n_characters=len(scene.get("dialogue") or []) + 1,
                                is_climax=is_climax)
        panels.append(StoryboardPanel(
            index=panel_idx, scene_index=si,
            speaker=None, line=None, emotion="neutral", intensity=2,
            atmosphere=atm, shot_plan=master_plan,
            prompt_suffix=build_shot_prompt_suffix(master_plan),
            grid_label=f"P{panel_idx:02d}",
        ))
        panel_idx += 1
        if panel_idx > target:
            break

        # shot-reverse-shot for paired dialogue lines
        dialogue = scene.get("dialogue") or []
        last_speaker = None
        for di, d in enumerate(dialogue):
            if panel_idx > target:
                break
            speaker = d.get("speaker") or "narrator"
            line = d.get("line") or ""
            emotion = d.get("emotion") or "neutral"
            intensity = int(d.get("intensity") or 3)
            prev_size = panels[-1].shot_plan.shot_size if panels else None
            sp = plan_shot(emotion_intensity=intensity, atmosphere=atm,
                           n_characters=1, prev_shot_size=prev_size,
                           is_climax=is_climax and di == len(dialogue) - 1)
            # emotion route — adds facial details
            ep = route_expression(emotion=emotion, intensity=intensity,
                                  atmosphere=atm, line_text=line)
            suffix = build_shot_prompt_suffix(sp) + f", {ep.face_prompt}, {ep.pose_prompt}"
            is_reverse = last_speaker is not None and speaker != last_speaker
            panel = StoryboardPanel(
                index=panel_idx, scene_index=si,
                speaker=speaker, line=line, emotion=emotion, intensity=intensity,
                atmosphere=atm, shot_plan=sp, prompt_suffix=suffix,
                grid_label=f"P{panel_idx:02d}",
                is_reverse_shot=is_reverse,
                counterpart_index=panels[-1].index if is_reverse else None,
            )
            panels.append(panel)
            panel_idx += 1
            last_speaker = speaker

    # If we're under the target, pad with reaction shots (CU on POV character)
    while len(panels) < target:
        sp = plan_shot(emotion_intensity=4, atmosphere=atmosphere_default,
                       n_characters=1)
        panels.append(StoryboardPanel(
            index=len(panels) + 1, scene_index=len(scenes),
            speaker=None, line=None, emotion="neutral", intensity=4,
            atmosphere=atmosphere_default, shot_plan=sp,
            prompt_suffix=build_shot_prompt_suffix(sp) + ", reaction shot",
            grid_label=f"P{len(panels) + 1:02d}",
        ))

    return StoryboardLayout(episode=episode, panel_count=len(panels), panels=panels[:target])


__all__ = ["StoryboardPanel", "StoryboardLayout", "layout_episode", "_grid_size_for"]
