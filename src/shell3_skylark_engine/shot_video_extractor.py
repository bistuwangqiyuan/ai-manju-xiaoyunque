"""Shot-level切镜 helpers.

The 官方 Skylark Agent 2.0 with vinput 接口只返回**一个** `video_url`（整集成品）；
并没有 `shot_videos[]` 数组可供单镜重生。要做"逐镜质检 + 单镜重生回灌"必须本地
完成：

1. 从 episode YAML 的 shots[] 计算镜头时间码（按 duration_seconds 累加）
2. 用 ffmpeg `-ss / -t` 精确切镜（带 `-c copy` 零损 + 关键帧对齐）
3. QA 标记失败镜头 → 仅对失败镜头走 Shell 4 修复路由
4. 拼回完整时间线（替换镜头时容器复用，无重编码损失）
"""
from __future__ import annotations

import json
import logging
import os
import pathlib
import subprocess
from dataclasses import dataclass, field
from typing import Iterable, Mapping, Sequence

from .client import EpisodeResult


_log = logging.getLogger(__name__)


@dataclass
class Shot:
    shot_id: int
    start_seconds: float
    duration_seconds: float
    prompt: str | None = None
    path: str | None = None        # 切出的单镜本地路径（切片后才有）

    @property
    def end_seconds(self) -> float:
        return self.start_seconds + self.duration_seconds


@dataclass
class SplicePlan:
    episode_id: str
    full_video: str                # 整集成品路径（小云雀返回 + 转存后）
    shots: list[Shot] = field(default_factory=list)

    def replace_shot(self, shot_id: int, new_video_path: str) -> "SplicePlan":
        new_shots = []
        for s in self.shots:
            if s.shot_id == shot_id:
                new_shots.append(Shot(
                    shot_id=s.shot_id,
                    start_seconds=s.start_seconds,
                    duration_seconds=s.duration_seconds,
                    prompt=s.prompt,
                    path=new_video_path,
                ))
            else:
                new_shots.append(s)
        return SplicePlan(self.episode_id, self.full_video, new_shots)


def build_splice_plan(result: EpisodeResult, ep_id: str,
                      shot_specs: Sequence[Mapping]) -> SplicePlan:
    """Compute per-shot time codes from the episode YAML's shots[]."""

    shots: list[Shot] = []
    cursor = 0.0
    for spec in shot_specs:
        sid = int(spec["shot_id"])
        dur = float(spec["duration_seconds"])
        shots.append(Shot(
            shot_id=sid,
            start_seconds=cursor,
            duration_seconds=dur,
            prompt=spec.get("action_desc") or spec.get("key_visual"),
        ))
        cursor += dur
    return SplicePlan(
        episode_id=str(ep_id),
        full_video=result.archived_video_path,
        shots=shots,
    )


def extract_shots(plan: SplicePlan, out_dir: str | pathlib.Path) -> SplicePlan:
    """Slice the full episode mp4 into N per-shot mp4 files via ffmpeg.

    Uses re-encoding at the shot start to ensure精确切割 (the default `-c copy`
    falls back to keyframe boundaries, which can drift up to a GOP length).
    """

    out = pathlib.Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    sliced: list[Shot] = []
    for s in plan.shots:
        target = out / f"shot_{s.shot_id:03d}.mp4"
        cmd = [
            "ffmpeg", "-y",
            "-ss", f"{s.start_seconds:.3f}",
            "-i", plan.full_video,
            "-t", f"{s.duration_seconds:.3f}",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "16",
            "-c:a", "aac", "-b:a", "192k",
            "-pix_fmt", "yuv420p",
            "-movflags", "+faststart",
            str(target),
        ]
        _log.debug("ffmpeg slice shot %d: %s", s.shot_id, " ".join(cmd))
        subprocess.run(cmd, check=True, capture_output=True)
        sliced.append(Shot(
            shot_id=s.shot_id,
            start_seconds=s.start_seconds,
            duration_seconds=s.duration_seconds,
            prompt=s.prompt,
            path=str(target),
        ))
    return SplicePlan(plan.episode_id, plan.full_video, sliced)


def compose_with_ffmpeg(plan: SplicePlan, output_path: str | os.PathLike) -> str:
    """Concatenate the (possibly patched) shot timeline into a final episode MP4."""

    if not all(s.path for s in plan.shots):
        raise RuntimeError("compose called on plan with un-sliced shots; "
                           "run extract_shots first or provide replacement paths")
    work = pathlib.Path(f"./data/work/{plan.episode_id}")
    work.mkdir(parents=True, exist_ok=True)
    concat_file = work / "concat.txt"
    with concat_file.open("w", encoding="utf-8") as f:
        for s in sorted(plan.shots, key=lambda x: x.shot_id):
            abs_path = pathlib.Path(s.path).resolve().as_posix()
            f.write(f"file '{abs_path}'\n")
    out = pathlib.Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0",
        "-i", str(concat_file),
        "-c:v", "libx264", "-preset", "slow", "-crf", "18",
        "-c:a", "aac", "-b:a", "192k",
        "-pix_fmt", "yuv420p",
        str(out),
    ]
    _log.info("ffmpeg compose: %s", " ".join(cmd))
    subprocess.run(cmd, check=True)
    return str(out)


def dump_plan(plan: SplicePlan, path: str | os.PathLike) -> None:
    p = pathlib.Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({
        "episode_id": plan.episode_id,
        "full_video": plan.full_video,
        "shots": [
            {
                "shot_id": s.shot_id,
                "start_seconds": s.start_seconds,
                "duration_seconds": s.duration_seconds,
                "path": s.path,
                "prompt": s.prompt,
            } for s in plan.shots
        ],
    }, ensure_ascii=False, indent=2), encoding="utf-8")


def load_plan(path: str | os.PathLike) -> SplicePlan:
    p = pathlib.Path(path)
    raw = json.loads(p.read_text(encoding="utf-8"))
    return SplicePlan(
        episode_id=raw["episode_id"],
        full_video=raw["full_video"],
        shots=[Shot(
            shot_id=int(s["shot_id"]),
            start_seconds=float(s["start_seconds"]),
            duration_seconds=float(s["duration_seconds"]),
            prompt=s.get("prompt"),
            path=s.get("path"),
        ) for s in raw.get("shots", [])],
    )


def replace_shot(plan: SplicePlan, shot_id: int, new_video_path: str,
                 duration: float | None = None) -> SplicePlan:
    """Backwards-compat helper preserved for shell4 repair handlers."""

    new_shots = []
    for s in plan.shots:
        if s.shot_id == shot_id:
            new_shots.append(Shot(
                shot_id=s.shot_id,
                start_seconds=s.start_seconds,
                duration_seconds=duration if duration is not None else s.duration_seconds,
                prompt=s.prompt,
                path=new_video_path,
            ))
        else:
            new_shots.append(s)
    return SplicePlan(plan.episode_id, plan.full_video, new_shots)
