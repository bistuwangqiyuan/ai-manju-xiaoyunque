"""Issue diagnosis: turn 7-dim scores + raw VLM issues into repair routes.

Maps low axes / VLM issue categories to one of the repair routes registered
on ``RepairRouter``. The output is a list of (route, reason, region) tuples
ordered by priority so the closed-loop repair runs cheapest-first.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .seven_dim_scorer import SEVEN_DIM_KEYS, ShotScore


@dataclass
class DiagnosedIssue:
    category: str             # face / hand / limb / structure / style / detail / blur / color / intent
    route: str                # face_drift / closeup_lipsync / costume_drift / cross_show_style / motion_axis / climax_enhance / god_tier
    severity: float           # 0–10 (higher = worse)
    evidence: str
    region: dict[str, float] = field(default_factory=dict)
    axes: list[str] = field(default_factory=list)


# Axis → primary category mapping (requirement doc §自动诊断)
_AXIS_TO_CATEGORY = {
    "structure": ("structure", "motion_axis"),
    "style": ("style", "cross_show_style"),
    "detail": ("detail", "costume_drift"),
    "clarity": ("blur", "climax_enhance"),
    "color": ("color", "cross_show_style"),
    "no_deform": ("face", "face_drift"),
    "intent": ("intent", "closeup_lipsync"),
}


def diagnose(
    score: ShotScore,
    *,
    pass_threshold: float = 7.0,
    region_hints: dict[str, dict[str, float]] | None = None,
) -> list[DiagnosedIssue]:
    """Return ordered list of issues that need repairing."""

    region_hints = region_hints or {}
    issues: list[DiagnosedIssue] = []

    # If the per-shot scorer raised explicit issue categories, prefer them.
    raw_issues = score.raw.get("issues") if isinstance(score.raw, dict) else None
    if isinstance(raw_issues, list):
        for it in raw_issues:
            cat = (it.get("category") if isinstance(it, dict) else None) or "structure"
            route = _category_to_route(cat)
            issues.append(
                DiagnosedIssue(
                    category=cat,
                    route=route,
                    severity=_severity_from_label(it.get("severity", "medium")),
                    evidence=it.get("evidence", ""),
                    region=region_hints.get(cat, {}),
                )
            )

    # Score-based diagnosis: low axes → derived issues.
    for axis in SEVEN_DIM_KEYS:
        v = score.scores.get(axis, 10.0)
        if v >= pass_threshold:
            continue
        cat, route = _AXIS_TO_CATEGORY[axis]
        severity = round(pass_threshold - v + 1.0, 2)
        issues.append(
            DiagnosedIssue(
                category=cat,
                route=route,
                severity=severity,
                evidence=f"axis '{axis}' = {v:.2f} < {pass_threshold}",
                region=region_hints.get(cat, {}),
                axes=[axis],
            )
        )

    # Deduplicate by route, keeping the most severe + merge evidence/axes.
    merged: dict[str, DiagnosedIssue] = {}
    for issue in issues:
        ex = merged.get(issue.route)
        if ex is None or issue.severity > ex.severity:
            if ex is not None:
                # carry axes forward
                seen = set(ex.axes)
                for a in issue.axes:
                    if a not in seen:
                        ex.axes.append(a)
                issue.axes = ex.axes + [a for a in issue.axes if a not in ex.axes]
            merged[issue.route] = issue
    return sorted(merged.values(), key=lambda x: -x.severity)


def _severity_from_label(label: str) -> float:
    return {"low": 1.0, "medium": 2.0, "high": 3.0}.get(label, 2.0)


def _category_to_route(category: str) -> str:
    cmap = {
        "face_drift": "face_drift",
        "face": "face_drift",
        "limb": "motion_axis",
        "lipsync": "closeup_lipsync",
        "costume_drift": "costume_drift",
        "signature_missing": "costume_drift",
        "motion_axis": "motion_axis",
        "ai_text": "climax_enhance",
        "structure": "motion_axis",
        "style": "cross_show_style",
        "detail": "costume_drift",
        "blur": "climax_enhance",
        "color": "cross_show_style",
        "intent": "closeup_lipsync",
    }
    return cmap.get(category, "motion_axis")


__all__ = ["DiagnosedIssue", "diagnose"]
