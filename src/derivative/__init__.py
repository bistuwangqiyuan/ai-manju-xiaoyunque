"""V10 §8.3 — Derivative works pipelines.

Modules:
    novel_to_comic   — Generate PDF/PNG comic from a novel manuscript
    video_to_comic   — Scene-detect a finished mp4 → comic layout
    comic_to_motion  — Comic (PDF/PNG) → animated video via OCR + I2V
    restyle_brush    — User-supplied "brush mask" for partial restyle
"""
from __future__ import annotations

__all__ = [
    "novel_to_comic", "video_to_comic", "comic_to_motion", "restyle_brush",
]
