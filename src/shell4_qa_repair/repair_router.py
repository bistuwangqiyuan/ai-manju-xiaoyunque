"""Five-tier repair router.

Given a set of QA findings on a shot, dispatch to the cheapest viable repair
route. Each repair returns a replacement video path that gets spliced back
into the master timeline by `shot_video_extractor.compose_with_ffmpeg`.

The closed-loop ``repair_until_pass`` runs the diagnose→repair→re-evaluate
cycle from the requirement doc (§自动修正): generate → 评估 → 修正 → 再评估.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Sequence

from .vlm_per_shot import ShotReport
from .arcface_check import FaceSimilarity


_log = logging.getLogger(__name__)


@dataclass
class RepairAction:
    route: str
    reason: str
    priority: int  # smaller = preferred


@dataclass
class RepairContext:
    shot_id: int
    shot_url: str
    shot_prompt: str
    canonical_image_url: str
    is_top_episode: bool = False
    is_climax_shot: bool = False
    multi_character: bool = False


class RepairRouter:
    """Decide which repair route to invoke for a flagged shot."""

    def __init__(self,
                 face_drift_repair: Callable[[RepairContext], str] | None = None,
                 lipsync_repair: Callable[[RepairContext], str] | None = None,
                 costume_repair: Callable[[RepairContext], str] | None = None,
                 style_repair: Callable[[RepairContext], str] | None = None,
                 motion_repair: Callable[[RepairContext], str] | None = None,
                 climax_repair: Callable[[RepairContext], str] | None = None,
                 god_tier_repair: Callable[[RepairContext], str] | None = None):
        self.routes: dict[str, Callable[[RepairContext], str] | None] = {
            "face_drift": face_drift_repair,
            "closeup_lipsync": lipsync_repair,
            "costume_drift": costume_repair,
            "cross_show_style": style_repair,
            "motion_axis": motion_repair,
            "climax_enhance": climax_repair,
            "god_tier": god_tier_repair,
        }

    # ------------------------------------------------------------------

    def plan(self, report: ShotReport, face: FaceSimilarity | None,
             context: RepairContext) -> list[RepairAction]:
        actions: list[RepairAction] = []

        # Priority 1: face drift (most damaging cross-episode)
        if face is not None and not face.passed:
            actions.append(RepairAction(
                route="face_drift",
                reason=f"ArcFace similarity {face.similarity:.3f} < threshold",
                priority=1,
            ))

        for issue in report.issues:
            if issue.category == "face_drift" and face is None:
                actions.append(RepairAction("face_drift", issue.evidence, 1))
            elif issue.category == "lipsync":
                actions.append(RepairAction("closeup_lipsync", issue.evidence, 2))
            elif issue.category == "costume_drift":
                actions.append(RepairAction("costume_drift", issue.evidence, 3))
            elif issue.category == "motion_axis":
                actions.append(RepairAction("motion_axis", issue.evidence, 2))
            elif issue.category == "limb":
                actions.append(RepairAction("motion_axis", "limb error → re-render", 2))
            elif issue.category == "signature_missing":
                actions.append(RepairAction("costume_drift",
                    "锁定符号丢失（朱砂痣/黑藤/苍白手）", 1))

        # Top episode + climax → unconditional精修
        if context.is_top_episode and context.is_climax_shot:
            actions.append(RepairAction("god_tier", "Top-tier climax shot精修", 99))
        elif context.is_climax_shot:
            actions.append(RepairAction("climax_enhance", "Climax shot精修", 50))

        actions.sort(key=lambda a: a.priority)
        return actions

    def execute(self, action: RepairAction, context: RepairContext) -> str:
        handler = self.routes.get(action.route)
        if handler is None:
            raise NotImplementedError(
                f"No repair handler registered for route={action.route!r}; "
                "register one via RepairRouter(<route>_repair=...)"
            )
        _log.info("repair shot %s via %s (%s)",
                  context.shot_id, action.route, action.reason)
        return handler(context)

    # ------------------------------------------------------------------
    # Closed-loop generate → evaluate → fix → re-evaluate
    # ------------------------------------------------------------------

    def repair_until_pass(
        self,
        context: RepairContext,
        *,
        scorer,
        diagnoser=None,
        max_iter: int = 2,
        pass_threshold: float = 7.0,
        on_step=None,
    ) -> "RepairLoopResult":
        """Iterate `diagnose → repair → re-evaluate` until passing or budget runs out.

        ``scorer`` must implement ``score(shot_id, path, canonical_image_url=, prompt=)``
        returning a ``ShotScore``. ``diagnoser`` defaults to
        ``auto_diagnose.diagnose``. Each iteration emits an event via ``on_step``
        (if provided) so callers can stream progress into job logs.
        """
        from .seven_dim_scorer import ShotScore  # local import to avoid cycles
        if diagnoser is None:
            from .auto_diagnose import diagnose as diagnoser  # type: ignore

        history: list[dict[str, Any]] = []
        current_url = context.shot_url
        score: ShotScore = scorer.score(
            context.shot_id,
            current_url,
            canonical_image_url=context.canonical_image_url,
            prompt=context.shot_prompt,
        )
        history.append({"iter": 0, "score": score.to_dict(), "url": current_url, "route": None})
        if on_step:
            on_step(0, score, current_url, None)
        if score.passed or max_iter <= 0:
            return RepairLoopResult(
                shot_id=context.shot_id,
                final_url=current_url,
                final_score=score,
                passed=score.passed,
                iterations=history,
            )

        for it in range(1, max_iter + 1):
            issues = diagnoser(score, pass_threshold=pass_threshold)
            if not issues:
                break
            primary = issues[0]
            action = RepairAction(
                route=primary.route,
                reason=primary.evidence,
                priority=1,
            )
            try:
                next_url = self.execute(action, context)
            except (NotImplementedError, Exception) as e:
                _log.warning("repair iter %d failed: %s", it, e)
                history.append({"iter": it, "error": str(e), "route": action.route})
                if on_step:
                    on_step(it, score, current_url, action.route, error=str(e))
                break
            current_url = next_url
            context.shot_url = next_url
            score = scorer.score(
                context.shot_id,
                current_url,
                canonical_image_url=context.canonical_image_url,
                prompt=context.shot_prompt,
            )
            history.append({"iter": it, "score": score.to_dict(), "url": current_url, "route": action.route})
            if on_step:
                on_step(it, score, current_url, action.route)
            if score.passed:
                break

        return RepairLoopResult(
            shot_id=context.shot_id,
            final_url=current_url,
            final_score=score,
            passed=score.passed,
            iterations=history,
        )


@dataclass
class RepairLoopResult:
    shot_id: int
    final_url: str
    final_score: Any           # ShotScore (forward-decl typing to break cycle)
    passed: bool
    iterations: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        score = self.final_score
        return {
            "shot_id": self.shot_id,
            "final_url": self.final_url,
            "final_score": score.to_dict() if hasattr(score, "to_dict") else score,
            "passed": self.passed,
            "iterations": self.iterations,
        }
