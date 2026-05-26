"""V10 §6.4 — Feedback distillation learning loop.

Accumulates per-job repair-route outcomes into a long-term JSON store,
then derives:

    1. Per-genre / per-route success rate (route effectiveness)
    2. Per-axis recurring-failure clusters (what artefacts repeat)
    3. Suggested prompt addenda for the next-shot prompt

The store is intentionally JSON-on-disk so it is portable across
serverless / VM / docker-compose; cloud deployments can later swap to
Postgres without changing the API surface.
"""
from __future__ import annotations

import json
import pathlib
from collections import Counter, defaultdict
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any

_REPO = pathlib.Path(__file__).resolve().parents[2]
DEFAULT_STORE = _REPO / "data" / "feedback" / "store.json"
DEFAULT_STORE.parent.mkdir(parents=True, exist_ok=True)


@dataclass
class FeedbackEvent:
    job_id: int
    episode: int
    shot: int
    genre: str
    route: str
    success: bool
    before_score_10: float | None = None
    after_score_10: float | None = None
    worst_axis: str | None = None
    user_label: str | None = None
    notes: str = ""
    ts: str = ""


@dataclass
class DistilledInsight:
    route_effectiveness: dict[str, dict[str, float]] = field(default_factory=dict)
    recurring_axes_top10: list[tuple[str, int]] = field(default_factory=list)
    per_genre_route_success: dict[str, dict[str, float]] = field(default_factory=dict)
    avg_delta_score: dict[str, float] = field(default_factory=dict)
    suggested_addenda: dict[str, str] = field(default_factory=dict)
    sample_size: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


_ADDENDUM_TEMPLATES = {
    "no_deform": "anatomically correct, no extra fingers, symmetric face",
    "style": "consistent style anchor, no style drift, locked palette",
    "color": "balanced colour grading, consistent tones",
    "detail": "rich detail, well-defined micro-textures",
    "clarity": "sharp focus, no motion blur, high resolution",
    "structure": "well-composed framing, correct anatomy proportions",
    "intent": "matches dialogue and emotion intent",
}


class FeedbackStore:
    def __init__(self, path: pathlib.Path | str = DEFAULT_STORE):
        self.path = pathlib.Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.events: list[FeedbackEvent] = []
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            return
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            self.events = [FeedbackEvent(**e) for e in raw.get("events", [])]
        except Exception:
            self.events = []

    def _flush(self) -> None:
        payload = {"events": [asdict(e) for e in self.events],
                   "saved_at": datetime.now(timezone.utc).isoformat()}
        self.path.write_text(json.dumps(payload, ensure_ascii=False, indent=2),
                             encoding="utf-8")

    def add(self, *, job_id: int, episode: int, shot: int, genre: str,
            route: str, success: bool,
            before_score_10: float | None = None,
            after_score_10: float | None = None,
            worst_axis: str | None = None,
            user_label: str | None = None,
            notes: str = "") -> FeedbackEvent:
        ev = FeedbackEvent(
            job_id=job_id, episode=episode, shot=shot, genre=genre,
            route=route, success=success,
            before_score_10=before_score_10, after_score_10=after_score_10,
            worst_axis=worst_axis, user_label=user_label, notes=notes,
            ts=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        )
        self.events.append(ev)
        self._flush()
        return ev

    def distill(self) -> DistilledInsight:
        ins = DistilledInsight(sample_size=len(self.events))
        if not self.events:
            return ins

        # Route success rate
        per_route_total: Counter = Counter()
        per_route_success: Counter = Counter()
        per_route_delta_sum: dict[str, float] = defaultdict(float)
        per_route_delta_n: dict[str, int] = defaultdict(int)
        for e in self.events:
            per_route_total[e.route] += 1
            if e.success:
                per_route_success[e.route] += 1
            if e.before_score_10 is not None and e.after_score_10 is not None:
                per_route_delta_sum[e.route] += (e.after_score_10 - e.before_score_10)
                per_route_delta_n[e.route] += 1

        for route, total in per_route_total.items():
            succ = per_route_success[route]
            ins.route_effectiveness[route] = {
                "sample": total,
                "success_rate": round(succ / total, 3),
                "avg_delta_score": round(
                    per_route_delta_sum[route] / max(per_route_delta_n[route], 1), 3
                ) if per_route_delta_n[route] else 0.0,
            }
            ins.avg_delta_score[route] = ins.route_effectiveness[route]["avg_delta_score"]

        # Per-genre × route success
        gr_total: dict[tuple[str, str], int] = defaultdict(int)
        gr_succ: dict[tuple[str, str], int] = defaultdict(int)
        for e in self.events:
            gr_total[(e.genre, e.route)] += 1
            if e.success:
                gr_succ[(e.genre, e.route)] += 1
        per_genre: dict[str, dict[str, float]] = defaultdict(dict)
        for (g, r), total in gr_total.items():
            per_genre[g][r] = round(gr_succ[(g, r)] / total, 3)
        ins.per_genre_route_success = dict(per_genre)

        # Recurring axes
        axis_counter: Counter = Counter(e.worst_axis for e in self.events if e.worst_axis)
        ins.recurring_axes_top10 = axis_counter.most_common(10)

        # Suggested addenda
        for axis, count in ins.recurring_axes_top10:
            if axis in _ADDENDUM_TEMPLATES and count >= 3:
                ins.suggested_addenda[axis] = _ADDENDUM_TEMPLATES[axis]

        return ins

    def __len__(self) -> int:
        return len(self.events)


_GLOBAL: FeedbackStore | None = None


def get_store() -> FeedbackStore:
    global _GLOBAL
    if _GLOBAL is None:
        _GLOBAL = FeedbackStore()
    return _GLOBAL


def record(**kwargs) -> FeedbackEvent:
    return get_store().add(**kwargs)


def distill() -> DistilledInsight:
    return get_store().distill()


__all__ = [
    "FeedbackEvent", "DistilledInsight", "FeedbackStore",
    "get_store", "record", "distill",
]
