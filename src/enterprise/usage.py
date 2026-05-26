"""V10 §11 — Daily usage aggregation helpers."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def utc_day_key(when: datetime | None = None) -> str:
    when = when or datetime.now(timezone.utc)
    return when.strftime("%Y-%m-%d")


def increment_usage(session, OrgUsage_cls, *, org_id: int,
                    day: str | None = None,
                    jobs_delta: int = 0,
                    episodes_delta: int = 0,
                    minutes_delta: float = 0.0,
                    cost_cents_delta: int = 0,
                    api_calls_delta: int = 0,
                    api_4xx_delta: int = 0,
                    api_5xx_delta: int = 0):
    """Upsert (org_id, day) and apply the deltas atomically per-process."""
    day = day or utc_day_key()
    row = session.query(OrgUsage_cls).filter(
        OrgUsage_cls.org_id == org_id, OrgUsage_cls.day == day,
    ).first()
    if row is None:
        row = OrgUsage_cls(org_id=org_id, day=day)
        session.add(row)
        session.flush()
    row.jobs_count = (row.jobs_count or 0) + jobs_delta
    row.episodes_count = (row.episodes_count or 0) + episodes_delta
    row.minutes_rendered = (row.minutes_rendered or 0.0) + minutes_delta
    row.cost_cents = (row.cost_cents or 0) + cost_cents_delta
    row.api_calls = (row.api_calls or 0) + api_calls_delta
    row.api_4xx = (row.api_4xx or 0) + api_4xx_delta
    row.api_5xx = (row.api_5xx or 0) + api_5xx_delta
    session.commit()
    return row


def usage_summary(session, OrgUsage_cls, *, org_id: int,
                  days: int = 30) -> dict[str, Any]:
    """Return a 30-day rollup for the org."""
    rows = session.query(OrgUsage_cls).filter(
        OrgUsage_cls.org_id == org_id,
    ).order_by(OrgUsage_cls.day.desc()).limit(days).all()
    return {
        "org_id": org_id,
        "days": len(rows),
        "jobs": sum(r.jobs_count or 0 for r in rows),
        "episodes": sum(r.episodes_count or 0 for r in rows),
        "minutes": sum(r.minutes_rendered or 0.0 for r in rows),
        "cost_cents": sum(r.cost_cents or 0 for r in rows),
        "api_calls": sum(r.api_calls or 0 for r in rows),
        "api_4xx": sum(r.api_4xx or 0 for r in rows),
        "api_5xx": sum(r.api_5xx or 0 for r in rows),
        "per_day": [
            {"day": r.day, "jobs": r.jobs_count, "minutes": r.minutes_rendered,
             "cost_cents": r.cost_cents, "api_calls": r.api_calls}
            for r in rows
        ],
    }


__all__ = ["utc_day_key", "increment_usage", "usage_summary"]
