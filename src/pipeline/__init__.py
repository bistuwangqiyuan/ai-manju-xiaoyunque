"""6-step production orchestrator for SaaS jobs.

v1 (``PipelineOrchestrator``) is preserved for backward compatibility.
v2 (``PipelineOrchestratorV2``) wires the full Shell4 + Shell5 stack with
7-dim per-shot scoring, closed-loop auto-repair and version snapshots.
"""

from .orchestrator import PipelineOrchestrator, PipelineResult
from .orchestrator_v2 import (
    PipelineOrchestratorV2,
    PipelineResult as PipelineResultV2,
    ShotResult,
    STEP_LABELS,
)

__all__ = [
    "PipelineOrchestrator",
    "PipelineResult",
    "PipelineOrchestratorV2",
    "PipelineResultV2",
    "ShotResult",
    "STEP_LABELS",
]
