"""V10 §5 — Frame generation modules.

Submodules:
    storyboard_layouter   — generate 9-25 panel storyboard layouts with shot/reverse-shot
    storyboard_grid       — PIL grid composition with numbered cells
    parallel_scheduler    — asyncio bounded-concurrency renderer
    resumer               — checkpoint-resume after partial failure
    anatomy_detector      — mediapipe face/hand/body anomaly scoring
    repair_hand_local     — local MediaPipe-only hand crop → repair handoff
"""
from . import (
    storyboard_layouter,
    storyboard_grid,
    parallel_scheduler,
    resumer,
    anatomy_detector,
    repair_hand_local,
)

__all__ = [
    "storyboard_layouter",
    "storyboard_grid",
    "parallel_scheduler",
    "resumer",
    "anatomy_detector",
    "repair_hand_local",
]
