"""Phase 1: closed-loop diagnose → repair → re-evaluate."""
from __future__ import annotations

import pathlib

from src.shell4_qa_repair.repair_router import RepairContext, RepairRouter
from src.shell4_qa_repair.seven_dim_scorer import SevenDimensionScorer, ShotScore
from src.shell4_qa_repair.auto_diagnose import diagnose


class _FixedScorer:
    """Scripted scorer: first call fails (face axis low), second call passes."""

    def __init__(self):
        self.calls = 0

    def score(self, shot_id: int, video_or_image, **kwargs):
        self.calls += 1
        if self.calls == 1:
            return ShotScore(
                shot_id=shot_id,
                scores={
                    "structure": 8.0, "style": 8.5, "detail": 8.2,
                    "clarity": 8.8, "color": 8.6, "no_deform": 6.2,  # < pass
                    "intent": 8.3,
                },
                overall=8.0,
                passed=False,
                issues=["no_deform=6.2 < 7.0"],
                raw={},
            )
        return ShotScore(
            shot_id=shot_id,
            scores={k: 9.0 for k in (
                "structure", "style", "detail", "clarity", "color", "no_deform", "intent",
            )},
            overall=9.0,
            passed=True,
            issues=[],
            raw={},
        )


def _identity_repair(context: RepairContext) -> str:
    """Mock repair handler that returns the input URL unchanged."""
    return context.shot_url


def test_repair_until_pass_runs_diagnose_then_repair_then_passes(tmp_path: pathlib.Path):
    router = RepairRouter(
        face_drift_repair=_identity_repair,
        motion_repair=_identity_repair,
        costume_repair=_identity_repair,
        style_repair=_identity_repair,
        lipsync_repair=_identity_repair,
        climax_repair=_identity_repair,
        god_tier_repair=_identity_repair,
    )
    ctx = RepairContext(
        shot_id=1,
        shot_url=str(tmp_path / "shot.mp4"),
        shot_prompt="月夜少女抬眼",
        canonical_image_url="",
    )
    scorer = _FixedScorer()
    result = router.repair_until_pass(ctx, scorer=scorer, max_iter=2, pass_threshold=7.0)
    assert result.passed
    assert len(result.iterations) >= 2
    # Iteration 1 should have an actual route taken
    routes_taken = [it.get("route") for it in result.iterations if it.get("route")]
    assert routes_taken


def test_diagnose_low_axis_yields_route():
    bad = ShotScore(
        shot_id=42,
        scores={
            "structure": 9.0, "style": 8.5, "detail": 9.0,
            "clarity": 9.0, "color": 9.0, "no_deform": 4.0,
            "intent": 9.0,
        },
        overall=8.0,
        passed=False,
        issues=["no_deform low"],
        raw={},
    )
    issues = diagnose(bad)
    assert any(i.route == "face_drift" for i in issues)
