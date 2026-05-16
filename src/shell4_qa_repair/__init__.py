"""Shell 4 — QA + 5-tier repair routing.

QA stack:
    豆包 Seed 1.6 Vision  — per-shot semantic check
    InsightFace ArcFace   — offline face similarity vs canonical
    Qwen-VL-Max           — Chinese OCR (subtitle garble)
    Gemini 2.5 Pro        — multi-language long-video审 (overseas)
    豆包 Seed 1.6 Thinking — scene logic check (physics, continuity)

Repair routes:
    face_drift          → Wan 2.7-FLF 14B (Apache 2.0)
    closeup_lipsync     → Hedra Character-3
    costume_drift       → FLUX Kontext
    cross_show_style    → Runway Aleph (V2V)
    motion_axis         → Seedance 2.0 standard
    climax_enhance      → Veo 3.1 (fast / standard)
    top_god_tier        → Sora 2 Pro 1080P
"""

from .vlm_per_shot import VlmPerShotChecker, ShotReport
from .arcface_check import ArcFaceChecker
from .repair_router import RepairRouter, RepairAction

__all__ = [
    "VlmPerShotChecker",
    "ShotReport",
    "ArcFaceChecker",
    "RepairRouter",
    "RepairAction",
]
