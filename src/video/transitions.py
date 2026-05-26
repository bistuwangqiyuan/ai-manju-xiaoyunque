"""V10 §7.4 — xfade transition plan + ffmpeg filter-complex builder.

Takes a list of input clips with durations and a chosen transition (one of
the 50+ ``xfade`` transition names) and produces:

    1. A normalised :class:`TransitionPlan` (per-clip offsets, transition
       duration, computed total).
    2. A ready-to-paste ffmpeg ``-filter_complex`` string + the matching
       ``-i`` argument list.

The compositor (``shell5_post_production.ffmpeg_compose.compose_final``)
can either consume the plan directly or shell out to the helper
``build_concat_command`` below.

Supported transitions are validated against the ffmpeg ``xfade`` upstream
list; unknown names fall back to ``fade``.
"""
from __future__ import annotations

import logging
import pathlib
import shutil
import subprocess
from dataclasses import dataclass, field
from typing import Any

_log = logging.getLogger(__name__)


XFADE_TRANSITIONS = (
    "fade", "fadeblack", "fadewhite", "distance", "wipeleft", "wiperight",
    "wipeup", "wipedown", "slideleft", "slideright", "slideup", "slidedown",
    "circlecrop", "rectcrop", "circleclose", "circleopen", "horzclose",
    "horzopen", "vertclose", "vertopen", "diagbl", "diagbr", "diagtl",
    "diagtr", "hlslice", "hrslice", "vuslice", "vdslice", "dissolve",
    "pixelize", "radial", "smoothleft", "smoothright", "smoothup",
    "smoothdown", "squeezeh", "squeezev", "zoomin",
    "fadefast", "fadeslow", "hblur", "wipetl", "wipetr", "wipebl", "wipebr",
)
_DEFAULT_TRANSITION = "fade"
_DEFAULT_DURATION = 0.6


@dataclass
class TransitionPlan:
    """Plan describing how to chain N clips with N-1 xfades."""
    clip_paths: list[str]
    clip_durations: list[float]
    transitions: list[str]
    durations: list[float]
    offsets: list[float]       # absolute time of each transition start
    total_duration: float
    audio_strategy: str = "concat"   # concat | mix | mute

    def to_dict(self) -> dict[str, Any]:
        return {
            "clip_paths": list(self.clip_paths),
            "clip_durations": [round(d, 3) for d in self.clip_durations],
            "transitions": list(self.transitions),
            "durations": [round(d, 3) for d in self.durations],
            "offsets": [round(o, 3) for o in self.offsets],
            "total_duration": round(self.total_duration, 3),
            "audio_strategy": self.audio_strategy,
        }


def _validate_transition(name: str | None) -> str:
    if not name:
        return _DEFAULT_TRANSITION
    return name if name in XFADE_TRANSITIONS else _DEFAULT_TRANSITION


def _probe_duration(path: str | pathlib.Path) -> float | None:
    if not shutil.which("ffprobe"):
        return None
    try:
        out = subprocess.check_output(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=nw=1:nk=1", str(path)],
            stderr=subprocess.STDOUT, timeout=10,
        )
        return float(out.decode().strip())
    except Exception:
        return None


def build_plan(
    clip_paths: list[str | pathlib.Path],
    *, clip_durations: list[float] | None = None,
    transitions: list[str] | None = None,
    transition_duration: float = _DEFAULT_DURATION,
    audio_strategy: str = "concat",
) -> TransitionPlan:
    paths = [str(p) for p in clip_paths]
    n = len(paths)
    if n == 0:
        raise ValueError("need at least one clip")

    if clip_durations is None:
        clip_durations = []
        for p in paths:
            d = _probe_duration(p)
            clip_durations.append(d if d is not None else 5.0)
    if len(clip_durations) != n:
        raise ValueError("clip_durations length must equal clip_paths length")

    if n == 1:
        return TransitionPlan(
            clip_paths=paths, clip_durations=list(clip_durations),
            transitions=[], durations=[], offsets=[],
            total_duration=clip_durations[0], audio_strategy=audio_strategy,
        )

    if transitions is None:
        transitions = [_DEFAULT_TRANSITION] * (n - 1)
    transitions = [_validate_transition(t) for t in transitions[: n - 1]]
    while len(transitions) < n - 1:
        transitions.append(_DEFAULT_TRANSITION)
    durations = [
        max(0.0, min(transition_duration, clip_durations[i], clip_durations[i + 1]))
        for i in range(n - 1)
    ]

    offsets: list[float] = []
    clip_start = 0.0     # output-time start of clip i
    for i in range(n - 1):
        # xfade between clip i and clip i+1 begins (xfade_dur) before clip i ends
        offsets.append(clip_start + clip_durations[i] - durations[i])
        # clip i+1 visually starts at the xfade offset (overlapping)
        clip_start = offsets[i]
    total = offsets[-1] + clip_durations[-1]

    return TransitionPlan(
        clip_paths=paths, clip_durations=list(clip_durations),
        transitions=transitions, durations=durations, offsets=offsets,
        total_duration=total, audio_strategy=audio_strategy,
    )


def build_filter_complex(plan: TransitionPlan) -> tuple[list[str], str, str, str]:
    """Return ``(input_args, filter_complex, video_label, audio_label)``.

    Caller assembles::

        ffmpeg -y *input_args -filter_complex "filter_complex" \
               -map "video_label" -map "audio_label" out.mp4
    """
    n = len(plan.clip_paths)
    inputs: list[str] = []
    for p in plan.clip_paths:
        inputs += ["-i", p]

    if n == 1:
        return inputs, "", "0:v", "0:a"

    video_parts: list[str] = []
    audio_parts: list[str] = []
    prev_v_label = "[0:v]"
    prev_a_label = "[0:a]"
    for i, (trans, dur, off) in enumerate(zip(
            plan.transitions, plan.durations, plan.offsets)):
        next_v = f"[{i + 1}:v]"
        next_a = f"[{i + 1}:a]"
        v_out = f"[v{i + 1}]"
        a_out = f"[a{i + 1}]"
        video_parts.append(
            f"{prev_v_label}{next_v}xfade=transition={trans}:"
            f"duration={dur:.3f}:offset={off:.3f}{v_out}"
        )
        if plan.audio_strategy == "concat":
            audio_parts.append(
                f"{prev_a_label}{next_a}acrossfade=d={max(dur, 0.05):.3f}{a_out}"
            )
        else:
            audio_parts.append(f"{prev_a_label}{next_a}amix=inputs=2{a_out}")
        prev_v_label = v_out
        prev_a_label = a_out

    filter_complex = ";".join(video_parts + audio_parts)
    return inputs, filter_complex, prev_v_label, prev_a_label


def build_concat_command(
    plan: TransitionPlan,
    output_path: str | pathlib.Path,
    *, crf: int = 18, preset: str = "slow",
) -> list[str]:
    """Build the full ffmpeg command for offline use."""
    inputs, fc, v_lab, a_lab = build_filter_complex(plan)
    cmd = ["ffmpeg", "-y"] + inputs
    if fc:
        cmd += ["-filter_complex", fc, "-map", v_lab, "-map", a_lab]
    else:
        cmd += ["-map", "0:v", "-map", "0:a"]
    cmd += [
        "-c:v", "libx264", "-preset", preset, "-crf", str(crf),
        "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k",
        str(output_path),
    ]
    return cmd


__all__ = [
    "XFADE_TRANSITIONS", "TransitionPlan",
    "build_plan", "build_filter_complex", "build_concat_command",
]
