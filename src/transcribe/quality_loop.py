"""7-dim quality loop for batch redraw.

Reuses ``shell4_qa_repair.SevenDimensionScorer`` so the loop has the same
behaviour as the orchestrator's per-shot QA. On failure we retry the redraw
with a slight parameter perturbation up to ``params.max_iter`` times.
"""
from __future__ import annotations

import logging
import pathlib
from dataclasses import dataclass, field
from typing import Any

from .engine import RedrawEngine, RedrawResult
from .params import RedrawParams

_log = logging.getLogger(__name__)


@dataclass
class QualityLoopRecord:
    item_id: int
    source: str
    final_output: str
    final_scores: dict[str, float]
    overall: float
    passed: bool
    repair_iters: int
    backend_chain: list[str] = field(default_factory=list)
    history: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "item_id": self.item_id,
            "source": self.source,
            "final_output": self.final_output,
            "final_scores": self.final_scores,
            "overall": self.overall,
            "passed": self.passed,
            "repair_iters": self.repair_iters,
            "backend_chain": self.backend_chain,
            "history": self.history,
        }


def run_quality_loop(
    engine: RedrawEngine,
    item_id: int,
    source: str,
    params: RedrawParams,
) -> QualityLoopRecord:
    from src.shell4_qa_repair.seven_dim_scorer import SevenDimensionScorer

    scorer = SevenDimensionScorer(pass_threshold=params.pass_threshold)
    backend_chain: list[str] = []
    history: list[dict[str, Any]] = []

    result: RedrawResult = engine.redraw(item_id, source, params)
    backend_chain.append(result.backend)
    score = scorer.score(item_id, result.output_path, prompt=params.refs.text_prompt)
    history.append({"iter": 0, "score": score.to_dict(), "output": result.output_path})

    repair_iters = 0
    cur_params = params

    while (
        not score.passed
        and repair_iters < params.max_iter
        and not _engine_only_mock(backend_chain)
    ):
        repair_iters += 1
        # Perturbation: bump detail_enhance + seed shift
        cur_params = RedrawParams.from_dict(cur_params.to_dict())
        cur_params.detail_enhance = min(1.0, cur_params.detail_enhance + 0.15)
        cur_params.seed = (cur_params.seed or 0) + repair_iters * 1000 + item_id

        result = engine.redraw(item_id, source, cur_params)
        backend_chain.append(result.backend)
        score = scorer.score(item_id, result.output_path, prompt=cur_params.refs.text_prompt)
        history.append(
            {"iter": repair_iters, "score": score.to_dict(), "output": result.output_path}
        )

    return QualityLoopRecord(
        item_id=item_id,
        source=source,
        final_output=result.output_path,
        final_scores=score.scores,
        overall=score.overall,
        passed=score.passed,
        repair_iters=repair_iters,
        backend_chain=backend_chain,
        history=history,
    )


def _engine_only_mock(chain: list[str]) -> bool:
    """If we only have a mock backend the loop can't actually improve."""
    return all(b == "mock" for b in chain)


__all__ = ["run_quality_loop", "QualityLoopRecord"]
