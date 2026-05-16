"""Final compose: video + dialogue + bgm + sfx + ASS subtitle + watermark."""
from __future__ import annotations

import logging
import pathlib
import subprocess
from dataclasses import dataclass


_log = logging.getLogger(__name__)


@dataclass
class ComposeInput:
    video_path: str
    dialogue_audio_path: str | None
    bgm_audio_path: str | None
    sfx_audio_paths: list[str]
    ass_subtitle_path: str | None
    bgm_volume: float = 0.25
    sfx_volume: float = 0.45
    dialogue_volume: float = 1.0
    watermark_text: str = "AI 生成"


def compose_final(payload: ComposeInput, output_path: str | pathlib.Path) -> str:
    """Compose all tracks into the final mp4 in a single ffmpeg pass."""

    inputs: list[str] = ["-i", payload.video_path]
    if payload.dialogue_audio_path:
        inputs += ["-i", payload.dialogue_audio_path]
    if payload.bgm_audio_path:
        inputs += ["-i", payload.bgm_audio_path]
    for sfx in payload.sfx_audio_paths:
        inputs += ["-i", sfx]

    # Build audio mix filter
    audio_streams = []
    next_idx = 1
    if payload.dialogue_audio_path:
        audio_streams.append((f"[{next_idx}:a]", payload.dialogue_volume))
        next_idx += 1
    if payload.bgm_audio_path:
        audio_streams.append((f"[{next_idx}:a]", payload.bgm_volume))
        next_idx += 1
    for _ in payload.sfx_audio_paths:
        audio_streams.append((f"[{next_idx}:a]", payload.sfx_volume))
        next_idx += 1

    filter_parts = []
    if audio_streams:
        for i, (stream, vol) in enumerate(audio_streams):
            filter_parts.append(f"{stream}volume={vol}[a{i}]")
        mix_inputs = "".join(f"[a{i}]" for i in range(len(audio_streams)))
        filter_parts.append(f"{mix_inputs}amix=inputs={len(audio_streams)}:duration=longest[audio_out]")

    # Video filter: ASS burn + watermark text
    vf_parts: list[str] = []
    if payload.ass_subtitle_path:
        sub = pathlib.Path(payload.ass_subtitle_path).resolve().as_posix().replace(":", "\\:")
        vf_parts.append(f"subtitles='{sub}'")
    if payload.watermark_text:
        vf_parts.append(
            f"drawtext=text='{payload.watermark_text}':"
            "fontfile='C\\:/Windows/Fonts/msyh.ttc':"
            "fontsize=36:fontcolor=white@0.6:"
            "x=w-tw-30:y=h-th-30:"
            "borderw=2:bordercolor=black@0.8"
        )
    if vf_parts:
        filter_parts.append(f"[0:v]{','.join(vf_parts)}[video_out]")

    filter_complex = ";".join(filter_parts) if filter_parts else ""

    out = pathlib.Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    cmd = ["ffmpeg", "-y"] + inputs

    if filter_complex:
        cmd += ["-filter_complex", filter_complex]
        if vf_parts:
            cmd += ["-map", "[video_out]"]
        else:
            cmd += ["-map", "0:v"]
        if audio_streams:
            cmd += ["-map", "[audio_out]"]

    cmd += [
        "-c:v", "libx264", "-preset", "slow", "-crf", "18", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k",
        str(out),
    ]
    _log.info("ffmpeg compose: %s", " ".join(cmd))
    subprocess.run(cmd, check=True)
    return str(out)
