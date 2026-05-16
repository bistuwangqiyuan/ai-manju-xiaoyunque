"""Five-tier repair router.

Given a set of QA findings on a shot, dispatch to the cheapest viable repair
route. Each repair returns a replacement video path that gets spliced back
into the master timeline by `shot_video_extractor.compose_with_ffmpeg`.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Callable, Sequence

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
