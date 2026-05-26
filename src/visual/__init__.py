"""V10 §4 — Visual asset modules.

Submodules:
    three_view          — character 3-view sheets with fixed seed grouping
    expression_router   — emotion→facial expression+camera framing mapping
    pose_extract        — mediapipe pose extraction → action library
    costume_climate     — atmosphere→costume mapping
    scene_search        — open_clip+faiss semantic scene similarity
    atmosphere_inferer  — text→atmosphere classifier
    shot_size_coupler   — camera distance ↔ emotion ↔ pose linkage
"""
from . import (
    three_view,
    expression_router,
    pose_extract,
    costume_climate,
    scene_search,
    atmosphere_inferer,
    shot_size_coupler,
)

__all__ = [
    "three_view",
    "expression_router",
    "pose_extract",
    "costume_climate",
    "scene_search",
    "atmosphere_inferer",
    "shot_size_coupler",
]
