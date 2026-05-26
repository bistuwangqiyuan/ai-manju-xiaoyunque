"""V10 §8.3.2 — Video → comic via scene detection.

Detects shot boundaries in a finished mp4, extracts a representative
keyframe per shot, then composes them into a ComicSpec (delegating actual
PDF rendering to :mod:`novel_to_comic`).

Backends:
    1. ``scenedetect`` + ``ffmpeg``      (proper PySceneDetect content detector)
    2. ``ffmpeg`` only (uniform sampling) — every N seconds
    3. mock — single placeholder panel

Returns the :class:`ComicResult` produced by ``novel_to_comic.render_comic``
plus the intermediate keyframe paths.
"""
from __future__ import annotations

import logging
import pathlib
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from typing import Any

from .novel_to_comic import ComicPanel, ComicResult, ComicSpec, render_comic

_log = logging.getLogger(__name__)


@dataclass
class Keyframe:
    image_path: str
    timestamp_sec: float
    shot_index: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "image_path": self.image_path,
            "timestamp_sec": round(self.timestamp_sec, 3),
            "shot_index": self.shot_index,
        }


@dataclass
class VideoToComicResult:
    comic: ComicResult
    keyframes: list[Keyframe] = field(default_factory=list)
    backend: str = "mock"
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "comic": self.comic.to_dict(),
            "keyframes": [k.to_dict() for k in self.keyframes],
            "backend": self.backend, "notes": list(self.notes),
        }


def _scenedetect_keyframes(video: pathlib.Path,
                           out_dir: pathlib.Path) -> list[Keyframe] | None:
    try:
        from scenedetect import SceneManager, open_video  # type: ignore
        from scenedetect.detectors import ContentDetector  # type: ignore
    except Exception:
        return None
    if not shutil.which("ffmpeg"):
        return None
    try:
        v = open_video(str(video))
        sm = SceneManager()
        sm.add_detector(ContentDetector(threshold=27.0))
        sm.detect_scenes(v)
        scene_list = sm.get_scene_list()
        if not scene_list:
            return None
        kfs: list[Keyframe] = []
        for i, (start, end) in enumerate(scene_list):
            mid = (start.get_seconds() + end.get_seconds()) / 2.0
            out_png = out_dir / f"kf_{i:03d}.png"
            cmd = [
                "ffmpeg", "-y", "-ss", f"{mid:.3f}",
                "-i", str(video), "-frames:v", "1", str(out_png),
            ]
            subprocess.run(cmd, check=True, capture_output=True, timeout=30)
            kfs.append(Keyframe(image_path=str(out_png), timestamp_sec=mid,
                                shot_index=i))
        return kfs
    except Exception as exc:
        _log.warning("scenedetect failed: %s", exc)
        return None


def _uniform_keyframes(video: pathlib.Path, out_dir: pathlib.Path,
                       every_seconds: float = 4.0) -> list[Keyframe] | None:
    if not shutil.which("ffmpeg"):
        return None
    try:
        # probe duration
        from ..audio.dialogue_timeline import _ffprobe_duration
        dur = _ffprobe_duration(video) or 30.0
        n = max(3, int(dur / every_seconds))
        kfs: list[Keyframe] = []
        for i in range(n):
            t = (i + 0.5) * (dur / n)
            out_png = out_dir / f"kf_{i:03d}.png"
            cmd = [
                "ffmpeg", "-y", "-ss", f"{t:.3f}",
                "-i", str(video), "-frames:v", "1", str(out_png),
            ]
            try:
                subprocess.run(cmd, check=True, capture_output=True, timeout=30)
                kfs.append(Keyframe(image_path=str(out_png), timestamp_sec=t,
                                    shot_index=i))
            except Exception:
                continue
        return kfs or None
    except Exception as exc:
        _log.warning("uniform keyframes failed: %s", exc)
        return None


def _mock_keyframes(out_dir: pathlib.Path, n: int = 6) -> list[Keyframe]:
    try:
        from PIL import Image  # type: ignore
        kfs: list[Keyframe] = []
        for i in range(n):
            p = out_dir / f"kf_{i:03d}.png"
            Image.new("RGB", (640, 360),
                      ((i * 37) % 255, (i * 73) % 255, (i * 113) % 255)).save(p)
            kfs.append(Keyframe(image_path=str(p),
                                timestamp_sec=float(i * 4),
                                shot_index=i))
        return kfs
    except Exception:
        kfs: list[Keyframe] = []
        for i in range(n):
            p = out_dir / f"kf_{i:03d}.placeholder"
            p.write_text(f"shot {i}", encoding="utf-8")
            kfs.append(Keyframe(image_path=str(p),
                                timestamp_sec=float(i * 4),
                                shot_index=i))
        return kfs


def extract_keyframes(
    video_path: str | pathlib.Path,
    out_dir: str | pathlib.Path,
    *, mode: str = "auto",
    uniform_every_seconds: float = 4.0,
) -> tuple[list[Keyframe], str]:
    """Return ``(keyframes, backend_used)``.

    ``mode`` ∈ {auto, scenedetect, uniform, mock}.
    """
    video = pathlib.Path(video_path)
    od = pathlib.Path(out_dir)
    od.mkdir(parents=True, exist_ok=True)
    if mode == "auto":
        if video.exists():
            kfs = _scenedetect_keyframes(video, od)
            if kfs:
                return kfs, "scenedetect"
            kfs = _uniform_keyframes(video, od, uniform_every_seconds)
            if kfs:
                return kfs, "ffmpeg_uniform"
        return _mock_keyframes(od), "mock"
    if mode == "scenedetect" and video.exists():
        kfs = _scenedetect_keyframes(video, od)
        if kfs:
            return kfs, "scenedetect"
    if mode == "uniform" and video.exists():
        kfs = _uniform_keyframes(video, od, uniform_every_seconds)
        if kfs:
            return kfs, "ffmpeg_uniform"
    return _mock_keyframes(od), "mock"


def video_to_comic(
    video_path: str | pathlib.Path,
    output_path: str | pathlib.Path,
    *, title: str | None = None, author: str = "",
    captions_by_shot: dict[int, str] | None = None,
    mode: str = "auto",
    panels_per_page: int = 2,
) -> VideoToComicResult:
    video = pathlib.Path(video_path)
    title = title or video.stem
    with tempfile.TemporaryDirectory(prefix="v10_v2c_") as td:
        td_p = pathlib.Path(td)
        keyframes, backend = extract_keyframes(video, td_p, mode=mode)
        panels: list[ComicPanel] = []
        for kf in keyframes:
            cap = (captions_by_shot or {}).get(kf.shot_index, "")
            panels.append(ComicPanel(
                caption=cap or f"镜头 {kf.shot_index + 1}（t≈{kf.timestamp_sec:.1f}s）",
                image_path=kf.image_path,
                chapter_index=0, panel_index=kf.shot_index,
            ))
        spec = ComicSpec(title=title, author=author, panels=panels,
                         panels_per_page=panels_per_page)
        comic = render_comic(spec, output_path)

    return VideoToComicResult(
        comic=comic, keyframes=keyframes, backend=backend,
    )


__all__ = [
    "Keyframe", "VideoToComicResult", "extract_keyframes", "video_to_comic",
]
