"""V10 §6.3 — Unified repair router."""
from __future__ import annotations

import pathlib
from dataclasses import dataclass, field
from typing import Any, Callable

REPAIR_ROUTES = (
    "face_drift", "closeup_lipsync", "costume_drift", "cross_show_style",
    "motion_axis", "climax_enhance", "hand_local",
    "cover_safe_swap", "violence_softening", "symbol_replace",
    "object_replace", "political_safe_swap", "brand_blur", "god_tier",
)

_AXIS_ROUTES: dict[str, list[str]] = {
    "structure":  ["motion_axis", "god_tier"],
    "style":      ["cross_show_style", "god_tier"],
    "detail":     ["costume_drift", "climax_enhance"],
    "clarity":    ["climax_enhance"],
    "color":      ["cross_show_style"],
    "no_deform":  ["hand_local", "face_drift", "god_tier"],
    "intent":     ["closeup_lipsync", "god_tier"],
}

_ROUTE_BACKEND: dict[str, str] = {
    "face_drift":          "flux_kontext_inpaint",
    "closeup_lipsync":     "wan_animate",
    "costume_drift":       "flux_kontext_inpaint",
    "cross_show_style":    "flux_kontext_styletransfer",
    "motion_axis":         "manju_agent_rerender",
    "climax_enhance":      "magnific_upscaler",
    "hand_local":          "flux_kontext_inpaint",
    "cover_safe_swap":     "seedream_cover_safe",
    "violence_softening":  "pil_blur_overlay",
    "symbol_replace":      "flux_kontext_inpaint",
    "object_replace":      "flux_kontext_inpaint",
    "political_safe_swap": "manju_agent_rerender",
    "brand_blur":          "pil_blur_local",
    "god_tier":            "premium_chain",
}

_ROUTE_COST_CNY = {
    "face_drift": 0.21, "hand_local": 0.21, "costume_drift": 0.21,
    "closeup_lipsync": 0.40, "cross_show_style": 0.21,
    "motion_axis": 0.72, "climax_enhance": 0.30,
    "cover_safe_swap": 0.10, "violence_softening": 0.01,
    "symbol_replace": 0.21, "object_replace": 0.21,
    "political_safe_swap": 0.72, "brand_blur": 0.01,
    "god_tier": 1.45,
}


@dataclass
class RepairTask:
    route: str
    backend: str
    image_path: str
    mask_path: str | None = None
    prompt_addendum: str = ""
    priority: int = 5
    notes: str = ""
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "route": self.route, "backend": self.backend,
            "image_path": self.image_path, "mask_path": self.mask_path,
            "prompt_addendum": self.prompt_addendum,
            "priority": self.priority, "notes": self.notes, "extra": self.extra,
        }


@dataclass
class RepairPlan:
    image_path: str
    tasks: list[RepairTask] = field(default_factory=list)
    rationale: list[str] = field(default_factory=list)
    severity_summary: dict[str, float] = field(default_factory=dict)
    estimated_cost_cny: float = 0.0

    def to_dict(self) -> dict:
        return {
            "image_path": self.image_path,
            "tasks": [t.to_dict() for t in self.tasks],
            "rationale": self.rationale,
            "severity_summary": self.severity_summary,
            "estimated_cost_cny": round(self.estimated_cost_cny, 3),
        }


def plan_repair(
    *,
    image_path: str | pathlib.Path,
    scores_7d: dict[str, float] | None = None,
    anatomy_report: dict | Any | None = None,
    safety_report: dict | Any | None = None,
    style_report: dict | Any | None = None,
    pass_threshold: float = 7.0,
    mask_provider: Callable | None = None,
    style_anchor: str | None = None,
) -> RepairPlan:
    """Build a deterministic ordered repair plan."""
    image_path = str(pathlib.Path(image_path))
    plan = RepairPlan(image_path=image_path)
    candidates: list[tuple[str, str, int]] = []  # (route, reason, priority)

    # 1) 7-dim driven (fire on worst axis only)
    if scores_7d:
        plan.severity_summary["worst_7d"] = min(scores_7d.values())
        worst_axis = min(scores_7d, key=lambda k: scores_7d[k])
        worst_val = scores_7d[worst_axis]
        if worst_val < pass_threshold:
            for r in _AXIS_ROUTES.get(worst_axis, []):
                priority = 3 if worst_val < pass_threshold - 1 else 5
                candidates.append((r, f"7d:{worst_axis}={worst_val:.2f}<{pass_threshold}", priority))

    # 2) Anatomy
    if anatomy_report:
        d = anatomy_report if isinstance(anatomy_report, dict) else getattr(anatomy_report, "to_dict", lambda: {})()
        sf = float(d.get("score_face", 0))
        sh = float(d.get("score_hand", 0))
        sb = float(d.get("score_body", 0))
        plan.severity_summary["anatomy_max"] = max(sf, sh, sb)
        if sh >= 5:
            candidates.append(("hand_local", f"anatomy:hand={sh:.1f}", 2))
        if sf >= 6:
            candidates.append(("face_drift", f"anatomy:face={sf:.1f}", 2))
        if sb >= 5:
            candidates.append(("motion_axis", f"anatomy:body={sb:.1f}", 4))
        for r in d.get("suggested_routes", []) or []:
            if r in REPAIR_ROUTES:
                candidates.append((r, "anatomy_suggested", 4))

    # 3) Safety
    if safety_report:
        d = safety_report if isinstance(safety_report, dict) else getattr(safety_report, "to_dict", lambda: {})()
        if d.get("blocked"):
            plan.severity_summary["safety_blocked"] = 10.0
            rec = d.get("recommended_route")
            if rec and rec in REPAIR_ROUTES:
                candidates.append((rec, f"safety:{','.join(d.get('blocked_axes', []))}", 1))
            else:
                candidates.append(("cover_safe_swap", "safety:generic", 1))

    # 4) Style consistency outlier
    if style_report:
        d = style_report if isinstance(style_report, dict) else getattr(style_report, "to_dict", lambda: {})()
        s10 = float(d.get("style_score_10", 10))
        plan.severity_summary["style_score_10"] = s10
        if s10 < 6.5:
            candidates.append(("cross_show_style", f"style_score={s10:.2f}<6.5", 3))

    # Dedup keeping highest priority (lowest number) per route
    best: dict[str, tuple[str, int]] = {}
    for route, reason, priority in candidates:
        if route not in best or priority < best[route][1]:
            best[route] = (reason, priority)

    for route, (reason, priority) in sorted(best.items(), key=lambda kv: kv[1][1]):
        mask = mask_provider(route, image_path) if mask_provider else None
        addendum = ""
        if route == "cross_show_style" and style_anchor:
            addendum = f"style transfer anchored to {style_anchor}"
        elif route == "hand_local":
            addendum = "perfect hand anatomy, five fingers, no extra fingers, natural pose"
        elif route == "face_drift":
            addendum = "symmetric eyes, natural facial proportions, consistent character"
        elif route == "costume_drift":
            addendum = "consistent costume across shots, matching color and pattern"
        elif route == "closeup_lipsync":
            addendum = "tight lip-sync to dialogue, natural mouth movement"
        elif route == "climax_enhance":
            addendum = "increase detail, sharpen edges, enhance facial micro-expression"
        task = RepairTask(
            route=route, backend=_ROUTE_BACKEND[route], image_path=image_path,
            mask_path=str(mask) if mask else None,
            prompt_addendum=addendum, priority=priority,
            notes=reason,
        )
        plan.tasks.append(task)
        plan.rationale.append(f"[{route}] {reason}")
        plan.estimated_cost_cny += _ROUTE_COST_CNY.get(route, 0.20)

    return plan


def route_backend(route: str) -> str:
    return _ROUTE_BACKEND.get(route, "manju_agent_rerender")


def route_cost_cny(route: str) -> float:
    return _ROUTE_COST_CNY.get(route, 0.20)


__all__ = [
    "REPAIR_ROUTES", "RepairTask", "RepairPlan",
    "plan_repair", "route_backend", "route_cost_cny",
]
