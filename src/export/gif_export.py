"""V10 §10.1 — GIF + multi-image-sequence export.

Backends (auto-fallback):

    1. ``imageio`` (preferred, supports both reading mp4 frames and writing
       optimised animated GIFs).
    2. ``ffmpeg`` palette-gen + paletteuse two-pass GIF (much higher
       quality than the default).
    3. ``Pillow`` frame-stitching from pre-extracted PNGs (no mp4 input).

All return a :class:`GifExportResult` with the absolute output path, the
frame count, the chosen backend and any helpful notes.
"""
from __future__ import annotations

import logging
import pathlib
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from typing import Any

_log = logging.getLogger(__name__)


@dataclass
class GifExportResult:
    output_path: str
    backend: str
    n_frames: int = 0
    fps: int = 12
    size: tuple[int, int] | None = None
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "output_path": self.output_path, "backend": self.backend,
            "n_frames": self.n_frames, "fps": self.fps,
            "size": list(self.size) if self.size else None,
            "notes": list(self.notes),
        }


def _imageio_gif(
    src: pathlib.Path,
    out_path: pathlib.Path,
    *, fps: int = 12,
    width: int | None = None,
    start_sec: float = 0.0,
    duration_sec: float | None = None,
) -> GifExportResult | None:
    try:
        import imageio.v3 as iio  # type: ignore
        import numpy as np  # type: ignore
    except Exception:
        return None
    try:
        frames: list = []
        meta = iio.immeta(str(src), exclude_applied=False)
        src_fps = float(meta.get("fps") or 24.0)
        step = max(1, int(round(src_fps / max(fps, 1))))
        cur_idx = 0
        max_frames = (
            None if duration_sec is None
            else int(round(duration_sec * fps))
        )
        for i, frame in enumerate(iio.imiter(str(src))):
            if i < int(start_sec * src_fps):
                continue
            if i % step != 0:
                continue
            arr = frame
            if width and arr.shape[1] != width:
                try:
                    from PIL import Image  # type: ignore
                    pil = Image.fromarray(arr)
                    new_h = int(round(width * arr.shape[0] / arr.shape[1]))
                    pil = pil.resize((width, new_h))
                    arr = np.array(pil)
                except Exception:
                    pass
            frames.append(arr)
            cur_idx += 1
            if max_frames is not None and cur_idx >= max_frames:
                break
        if not frames:
            return None
        iio.imwrite(str(out_path), frames, duration=int(1000 / fps),
                    loop=0)
        h, w = frames[0].shape[:2]
        return GifExportResult(
            output_path=str(out_path), backend="imageio",
            n_frames=len(frames), fps=fps, size=(w, h),
        )
    except Exception as exc:
        _log.debug("imageio gif export failed: %s", exc)
        return None


def _ffmpeg_gif(
    src: pathlib.Path,
    out_path: pathlib.Path,
    *, fps: int = 12, width: int | None = None,
    start_sec: float = 0.0, duration_sec: float | None = None,
) -> GifExportResult | None:
    if not shutil.which("ffmpeg") or not src.exists():
        return None
    try:
        with tempfile.TemporaryDirectory(prefix="v10_gif_") as td:
            palette = pathlib.Path(td) / "palette.png"
            scale = f"scale={width}:-1:flags=lanczos," if width else ""
            vf_pal = f"{scale}fps={fps},palettegen=stats_mode=diff"
            cmd1 = ["ffmpeg", "-y"]
            if start_sec > 0:
                cmd1 += ["-ss", str(start_sec)]
            cmd1 += ["-i", str(src)]
            if duration_sec is not None:
                cmd1 += ["-t", str(duration_sec)]
            cmd1 += ["-vf", vf_pal, str(palette)]
            subprocess.run(cmd1, check=True, capture_output=True)

            vf = f"{scale}fps={fps}[x];[x][1:v]paletteuse=dither=floyd_steinberg"
            cmd2 = ["ffmpeg", "-y"]
            if start_sec > 0:
                cmd2 += ["-ss", str(start_sec)]
            cmd2 += ["-i", str(src), "-i", str(palette)]
            if duration_sec is not None:
                cmd2 += ["-t", str(duration_sec)]
            cmd2 += ["-filter_complex", vf, str(out_path)]
            subprocess.run(cmd2, check=True, capture_output=True)
        return GifExportResult(
            output_path=str(out_path), backend="ffmpeg",
            n_frames=-1, fps=fps,
        )
    except Exception as exc:
        _log.debug("ffmpeg gif export failed: %s", exc)
        return None


def _pil_gif(
    frame_paths: list[str | pathlib.Path],
    out_path: pathlib.Path,
    *, fps: int = 12,
) -> GifExportResult | None:
    try:
        from PIL import Image  # type: ignore
    except Exception:
        return None
    try:
        imgs = [Image.open(p).convert("RGB") for p in frame_paths]
        if not imgs:
            return None
        imgs[0].save(out_path, save_all=True, append_images=imgs[1:],
                     duration=int(1000 / fps), loop=0, optimize=True)
        return GifExportResult(
            output_path=str(out_path), backend="pil",
            n_frames=len(imgs), fps=fps, size=imgs[0].size,
        )
    except Exception as exc:
        _log.debug("pil gif export failed: %s", exc)
        return None


def video_to_gif(
    src: str | pathlib.Path,
    output_path: str | pathlib.Path,
    *, fps: int = 12, width: int | None = None,
    start_sec: float = 0.0, duration_sec: float | None = None,
) -> GifExportResult:
    src_p = pathlib.Path(src)
    out_p = pathlib.Path(output_path)
    out_p.parent.mkdir(parents=True, exist_ok=True)

    res = _imageio_gif(src_p, out_p, fps=fps, width=width,
                       start_sec=start_sec, duration_sec=duration_sec)
    if res is not None:
        return res
    res = _ffmpeg_gif(src_p, out_p, fps=fps, width=width,
                      start_sec=start_sec, duration_sec=duration_sec)
    if res is not None:
        return res
    return GifExportResult(
        output_path=str(out_p), backend="none",
        notes=["no backend available (imageio + ffmpeg both missing or "
               "source not readable)"],
    )


def frames_to_gif(
    frame_paths: list[str | pathlib.Path],
    output_path: str | pathlib.Path,
    *, fps: int = 12,
) -> GifExportResult:
    out_p = pathlib.Path(output_path)
    out_p.parent.mkdir(parents=True, exist_ok=True)
    res = _pil_gif(frame_paths, out_p, fps=fps)
    if res is not None:
        return res
    return GifExportResult(
        output_path=str(out_p), backend="none",
        notes=["no backend available (PIL missing)"],
    )


__all__ = ["GifExportResult", "video_to_gif", "frames_to_gif"]
