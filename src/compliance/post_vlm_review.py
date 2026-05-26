"""V10 §11.3 Post-VLM safety review.

After every shot finishes rendering we ask the chosen VLM to grade
six safety axes on 0-10 scales::

    adult, violence_blood, hate_symbol, drug, political, copyrighted_brand

Any axis ≥ 7 triggers an auto-block + repair re-route to the repair
router with the offending axis encoded as the route key.

The module is mock-mode safe — without a configured VLM it deterministically
classifies based on filename heuristics so unit tests run in CI.
"""
from __future__ import annotations

import json
import os
import pathlib
import random
from dataclasses import dataclass, field, asdict
from typing import Any

REVIEW_AXES = (
    "adult",
    "violence_blood",
    "hate_symbol",
    "drug",
    "political",
    "copyrighted_brand",
)

DEFAULT_BLOCK_THRESHOLD = 7.0


@dataclass
class ReviewReport:
    scores: dict[str, float] = field(default_factory=dict)
    blocked: bool = False
    blocked_axes: list[str] = field(default_factory=list)
    recommended_route: str | None = None
    backend: str = "mock"
    raw: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _route_for(axes: list[str]) -> str | None:
    if not axes:
        return None
    if "adult" in axes:
        return "cover_safe_swap"
    if "violence_blood" in axes:
        return "violence_softening"
    if "hate_symbol" in axes:
        return "symbol_replace"
    if "drug" in axes:
        return "object_replace"
    if "political" in axes:
        return "political_safe_swap"
    if "copyrighted_brand" in axes:
        return "brand_blur"
    return None


def _mock_grade(content_hint: str) -> dict[str, float]:
    rng = random.Random(hash(content_hint) & 0xFFFFFFFF)
    base = {a: max(0.0, rng.gauss(1.5, 1.0)) for a in REVIEW_AXES}
    hint = content_hint.lower()
    if "nsfw" in hint or "nude" in hint:
        base["adult"] += 7
    if "blood" in hint or "gore" in hint:
        base["violence_blood"] += 7
    if "swastika" in hint or "hate" in hint:
        base["hate_symbol"] += 7
    if "drug" in hint or "syringe" in hint:
        base["drug"] += 6
    return {k: round(min(10.0, v), 2) for k, v in base.items()}


def _real_grade_image(image_path: pathlib.Path) -> dict[str, float] | None:
    """Call configured VLM (Anthropic / GLM / Doubao Seed1.6) — short timeout."""
    backend = os.environ.get("POST_VLM_BACKEND")
    if not backend:
        return None
    try:
        from src.llm.fallback_chain import call_vlm  # type: ignore
    except Exception:
        return None
    prompt = (
        "Rate the following short-drama frame on six safety axes (0-10 integers, "
        "10 = severe). Output strict JSON: {adult,violence_blood,hate_symbol,"
        "drug,political,copyrighted_brand}."
    )
    try:
        raw = call_vlm(prompt=prompt, image_paths=[str(image_path)],
                       backend=backend, timeout_s=12.0)
        data = json.loads(raw) if isinstance(raw, str) else raw
        return {k: float(data.get(k, 0)) for k in REVIEW_AXES}
    except Exception:
        return None


def review_image(image_path: str | pathlib.Path,
                 *, threshold: float = DEFAULT_BLOCK_THRESHOLD) -> ReviewReport:
    p = pathlib.Path(image_path)
    real = _real_grade_image(p)
    if real is not None:
        backend = os.environ.get("POST_VLM_BACKEND", "remote")
        scores = real
    else:
        backend = "mock"
        scores = _mock_grade(p.name)
    blocked_axes = [a for a, v in scores.items() if v >= threshold]
    report = ReviewReport(
        scores=scores,
        blocked=bool(blocked_axes),
        blocked_axes=blocked_axes,
        recommended_route=_route_for(blocked_axes),
        backend=backend,
        raw={"path": str(p)},
    )
    return report


def review_clip(clip_path: str | pathlib.Path,
                *, sample_seconds: list[float] | None = None,
                threshold: float = DEFAULT_BLOCK_THRESHOLD) -> ReviewReport:
    """Review a video by sampling 3 frames.  Works in mock mode (filename only)."""
    p = pathlib.Path(clip_path)
    samples = sample_seconds or [0.5, 2.5, 4.5]
    frame_reports: list[ReviewReport] = []
    try:
        import cv2  # type: ignore
        cap = cv2.VideoCapture(str(p))
        for t in samples:
            cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000)
            ok, frame = cap.read()
            if not ok:
                continue
            tmp = p.with_suffix(f".review_{int(t*1000)}.jpg")
            cv2.imwrite(str(tmp), frame)
            frame_reports.append(review_image(tmp, threshold=threshold))
            try:
                tmp.unlink()
            except Exception:
                pass
        cap.release()
    except Exception:
        frame_reports.append(review_image(p, threshold=threshold))

    if not frame_reports:
        return review_image(p, threshold=threshold)

    agg_scores = {a: max(r.scores.get(a, 0) for r in frame_reports) for a in REVIEW_AXES}
    blocked_axes = [a for a, v in agg_scores.items() if v >= threshold]
    return ReviewReport(
        scores=agg_scores,
        blocked=bool(blocked_axes),
        blocked_axes=blocked_axes,
        recommended_route=_route_for(blocked_axes),
        backend=frame_reports[0].backend,
        raw={"clip": str(p), "frames_reviewed": len(frame_reports)},
    )


__all__ = ["review_image", "review_clip", "ReviewReport", "REVIEW_AXES"]
