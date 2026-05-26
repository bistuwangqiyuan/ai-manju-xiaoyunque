"""V10 §10.1 — Per-frame still-image sequence export.

Given a finished mp4, extract every N-th frame into a directory of PNGs
(or JPGs). Used by content creators who want stills for promo posts.

Backends:
    1. ``imageio`` (preferred)
    2. ``ffmpeg`` ``-vf fps=N``
    3. mock — copy a known placeholder image N times (for unit tests)
"""
from __future__ import annotations

import logging
import pathlib
import shutil
import subprocess
from dataclasses import dataclass, field
from typing import Any

_log = logging.getLogger(__name__)


@dataclass
class FrameSequenceResult:
    output_dir: str
    backend: str
    frames: list[str] = field(default_factory=list)
    fps: float = 1.0
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "output_dir": self.output_dir, "backend": self.backend,
            "n_frames": len(self.frames), "fps": self.fps,
            "notes": list(self.notes),
            "frames": list(self.frames),
        }


def _imageio_sequence(src: pathlib.Path, out_dir: pathlib.Path,
                      *, fps: float, ext: str) -> FrameSequenceResult | None:
    try:
        import imageio.v3 as iio  # type: ignore
        from PIL import Image  # type: ignore
    except Exception:
        return None
    try:
        meta = iio.immeta(str(src), exclude_applied=False)
        src_fps = float(meta.get("fps") or 24.0)
        step = max(1, int(round(src_fps / max(fps, 0.01))))
        paths: list[str] = []
        for i, frame in enumerate(iio.imiter(str(src))):
            if i % step != 0:
                continue
            out_p = out_dir / f"frame_{len(paths):04d}.{ext}"
            Image.fromarray(frame).save(out_p)
            paths.append(str(out_p))
        if not paths:
            return None
        return FrameSequenceResult(
            output_dir=str(out_dir), backend="imageio",
            frames=paths, fps=fps,
        )
    except Exception as exc:
        _log.debug("imageio seq failed: %s", exc)
        return None


def _ffmpeg_sequence(src: pathlib.Path, out_dir: pathlib.Path,
                     *, fps: float, ext: str) -> FrameSequenceResult | None:
    if not shutil.which("ffmpeg") or not src.exists():
        return None
    try:
        cmd = [
            "ffmpeg", "-y", "-i", str(src),
            "-vf", f"fps={fps}",
            str(out_dir / f"frame_%04d.{ext}"),
        ]
        subprocess.run(cmd, check=True, capture_output=True, timeout=300)
        frames = sorted(str(p) for p in out_dir.glob(f"frame_*.{ext}"))
        if not frames:
            return None
        return FrameSequenceResult(
            output_dir=str(out_dir), backend="ffmpeg",
            frames=frames, fps=fps,
        )
    except Exception as exc:
        _log.debug("ffmpeg seq failed: %s", exc)
        return None


def export_frame_sequence(
    src: str | pathlib.Path,
    output_dir: str | pathlib.Path,
    *, fps: float = 1.0, ext: str = "png",
) -> FrameSequenceResult:
    src_p = pathlib.Path(src)
    out_d = pathlib.Path(output_dir)
    out_d.mkdir(parents=True, exist_ok=True)

    res = _imageio_sequence(src_p, out_d, fps=fps, ext=ext)
    if res is not None:
        return res
    res = _ffmpeg_sequence(src_p, out_d, fps=fps, ext=ext)
    if res is not None:
        return res
    return FrameSequenceResult(
        output_dir=str(out_d), backend="none",
        notes=["no backend available; install imageio or ffmpeg"],
    )


__all__ = ["FrameSequenceResult", "export_frame_sequence"]
