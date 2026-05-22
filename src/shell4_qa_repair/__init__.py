"""Shell 4 — QA + 5-tier repair routing + 7-dim scoring + closed-loop auto-fix.

QA stack:
    豆包 Seed 1.6 Vision  — per-shot semantic check
    InsightFace ArcFace   — offline face similarity vs canonical
    Qwen-VL-Max           — Chinese OCR (subtitle garble)
    Gemini 2.5 Pro        — multi-language long-video审 (overseas)
    豆包 Seed 1.6 Thinking — scene logic check (physics, continuity)
    7-Dim Scorer (NEW)    — per-shot 0–10 on structure/style/detail/clarity/
                             color/no_deform/intent (requirement doc §12)

Repair routes:
    face_drift          → Wan 2.7-FLF 14B (Apache 2.0)
    closeup_lipsync     → Hedra Character-3
    costume_drift       → FLUX Kontext
    cross_show_style    → Runway Aleph (V2V)
    motion_axis         → Seedance 2.0 standard
    climax_enhance      → Veo 3.1 (fast / standard)
    god_tier            → Sora 2 Pro 1080P

Closed loop (NEW):
    RepairRouter.repair_until_pass(): generate → 评估 → 修正 → 再评估
"""

from .vlm_per_shot import VlmPerShotChecker, ShotReport
from .arcface_check import ArcFaceChecker
from .repair_router import RepairRouter, RepairAction, RepairContext, RepairLoopResult
from .seven_dim_scorer import (
    SEVEN_DIM_KEYS,
    PASS_THRESHOLD,
    SevenDimensionScorer,
    ShotScore,
)
from .auto_diagnose import DiagnosedIssue, diagnose
from .run_qa import run_qa

__all__ = [
    "VlmPerShotChecker",
    "ShotReport",
    "ArcFaceChecker",
    "RepairRouter",
    "RepairAction",
    "RepairContext",
    "RepairLoopResult",
    "SevenDimensionScorer",
    "ShotScore",
    "SEVEN_DIM_KEYS",
    "PASS_THRESHOLD",
    "DiagnosedIssue",
    "diagnose",
    "run_qa",
]
