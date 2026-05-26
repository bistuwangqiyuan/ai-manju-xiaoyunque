"""V10 §9.3 — Timed publishing scheduler.

Persists user-defined cron / date / interval triggers for "generate &
publish at time T" workflows. APScheduler is the primary backend; when
unavailable the module degrades to a plain JSON store + an in-process
loop that fires due tasks when polled.

Public API:

    register_job(job_id, trigger_spec, *, owner_id, description)
    list_jobs(owner_id=None, only_due=False)
    cancel_job(schedule_id)
    poll_due()         — only meaningful in the fallback backend
    start_background() — start APScheduler (no-op in fallback)
"""
from __future__ import annotations

import json
import logging
import pathlib
import threading
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any, Callable

_log = logging.getLogger(__name__)

_REPO = pathlib.Path(__file__).resolve().parents[2]
_DEFAULT_STORE = _REPO / "data" / "flow" / "schedules.json"
_DEFAULT_STORE.parent.mkdir(parents=True, exist_ok=True)


@dataclass
class ScheduleSpec:
    """Trigger description; pick ONE of cron / date / interval."""
    cron: str | None = None              # "0 9 * * *"
    date: str | None = None              # ISO-8601 UTC
    interval_seconds: int | None = None  # e.g. 3600 = hourly

    def to_dict(self) -> dict[str, Any]:
        d = {}
        if self.cron:
            d["cron"] = self.cron
        if self.date:
            d["date"] = self.date
        if self.interval_seconds:
            d["interval_seconds"] = self.interval_seconds
        return d


@dataclass
class ScheduledJob:
    schedule_id: str
    job_id: int
    owner_id: int
    spec: ScheduleSpec
    description: str = ""
    next_fire_at: str | None = None
    last_fire_at: str | None = None
    fire_count: int = 0
    enabled: bool = True
    created_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["spec"] = self.spec.to_dict()
        return d


# ---------- next-fire computation (no dependencies) ----------

def _parse_iso_utc(s: str) -> datetime | None:
    try:
        if s.endswith("Z"):
            s = s[:-1]
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


def _compute_next_fire(spec: ScheduleSpec, ref: datetime | None = None) -> datetime | None:
    ref = ref or datetime.now(timezone.utc)
    if spec.date:
        dt = _parse_iso_utc(spec.date)
        return dt if (dt and dt > ref) else None
    if spec.interval_seconds:
        return ref.fromtimestamp(
            ref.timestamp() + spec.interval_seconds, tz=timezone.utc)
    if spec.cron:
        return _next_cron_fire(spec.cron, ref)
    return None


def _next_cron_fire(cron: str, ref: datetime) -> datetime | None:
    """Tiny five-field cron parser: min hour dom mon dow.

    Supports ``*``, comma-lists ``0,15,30`` and ``*/N`` step values.
    Not a full croniter replacement but covers the daily / hourly /
    every-N-minutes cases the dashboard needs.
    """
    fields = cron.strip().split()
    if len(fields) != 5:
        return None
    try:
        minute_set = _expand_field(fields[0], 0, 59)
        hour_set = _expand_field(fields[1], 0, 23)
        dom_set = _expand_field(fields[2], 1, 31)
        mon_set = _expand_field(fields[3], 1, 12)
        dow_set = _expand_field(fields[4], 0, 6)
    except Exception:
        return None
    cursor = ref.replace(second=0, microsecond=0)
    # Search up to 4 days ahead
    from datetime import timedelta
    for _ in range(60 * 24 * 4):
        cursor = cursor + timedelta(minutes=1)
        if (cursor.minute in minute_set and cursor.hour in hour_set
                and cursor.day in dom_set and cursor.month in mon_set
                and cursor.weekday() in dow_set):
            return cursor
    return None


def _expand_field(token: str, lo: int, hi: int) -> set[int]:
    if token == "*":
        return set(range(lo, hi + 1))
    out: set[int] = set()
    for piece in token.split(","):
        if piece.startswith("*/"):
            step = int(piece[2:])
            out.update(range(lo, hi + 1, step))
        elif "-" in piece:
            a, b = piece.split("-")
            out.update(range(int(a), int(b) + 1))
        else:
            out.add(int(piece))
    return out


# ---------- registry ----------

class ScheduleRegistry:
    def __init__(self, path: pathlib.Path | str = _DEFAULT_STORE):
        self.path = pathlib.Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._jobs: dict[str, ScheduledJob] = {}
        self._scheduler = None
        self._fire_callback: Callable[[ScheduledJob], None] | None = None
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            return
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            for j in raw.get("jobs", []):
                spec = ScheduleSpec(**j.get("spec", {}))
                job = ScheduledJob(
                    schedule_id=j["schedule_id"], job_id=j["job_id"],
                    owner_id=j["owner_id"], spec=spec,
                    description=j.get("description", ""),
                    next_fire_at=j.get("next_fire_at"),
                    last_fire_at=j.get("last_fire_at"),
                    fire_count=j.get("fire_count", 0),
                    enabled=j.get("enabled", True),
                    created_at=j.get("created_at", ""),
                )
                self._jobs[job.schedule_id] = job
        except Exception as exc:
            _log.debug("schedule load failed: %s", exc)

    def _flush(self) -> None:
        with self._lock:
            data = {"jobs": [j.to_dict() for j in self._jobs.values()],
                    "saved_at": datetime.now(timezone.utc).isoformat()}
            self.path.write_text(json.dumps(data, ensure_ascii=False, indent=2),
                                 encoding="utf-8")

    def register_job(
        self, job_id: int, spec: ScheduleSpec, *,
        owner_id: int, description: str = "",
    ) -> ScheduledJob:
        with self._lock:
            schedule_id = f"sched_{uuid.uuid4().hex[:12]}"
            now = datetime.now(timezone.utc)
            next_fire = _compute_next_fire(spec, now)
            job = ScheduledJob(
                schedule_id=schedule_id, job_id=job_id, owner_id=owner_id,
                spec=spec, description=description,
                next_fire_at=next_fire.isoformat() if next_fire else None,
                created_at=now.isoformat(),
            )
            self._jobs[schedule_id] = job
            self._flush()
        return job

    def list_jobs(self, owner_id: int | None = None,
                  only_due: bool = False) -> list[ScheduledJob]:
        now = datetime.now(timezone.utc)
        with self._lock:
            out = list(self._jobs.values())
            if owner_id is not None:
                out = [j for j in out if j.owner_id == owner_id]
            if only_due:
                def _due(j: ScheduledJob) -> bool:
                    if not j.enabled or not j.next_fire_at:
                        return False
                    nf = _parse_iso_utc(j.next_fire_at)
                    return bool(nf and nf <= now)
                out = [j for j in out if _due(j)]
        return out

    def cancel_job(self, schedule_id: str) -> bool:
        with self._lock:
            if schedule_id not in self._jobs:
                return False
            del self._jobs[schedule_id]
            self._flush()
            return True

    def mark_fired(self, schedule_id: str) -> None:
        with self._lock:
            job = self._jobs.get(schedule_id)
            if job is None:
                return
            now = datetime.now(timezone.utc)
            job.last_fire_at = now.isoformat()
            job.fire_count += 1
            next_fire = _compute_next_fire(job.spec, now)
            job.next_fire_at = next_fire.isoformat() if next_fire else None
            if next_fire is None and job.spec.date:
                job.enabled = False
            self._flush()

    def poll_due(self) -> list[ScheduledJob]:
        due = self.list_jobs(only_due=True)
        for job in due:
            if self._fire_callback is not None:
                try:
                    self._fire_callback(job)
                except Exception as exc:
                    _log.warning("scheduler callback failed for %s: %s",
                                 job.schedule_id, exc)
            self.mark_fired(job.schedule_id)
        return due

    def set_fire_callback(self, cb: Callable[[ScheduledJob], None]) -> None:
        self._fire_callback = cb

    def start_background(self) -> bool:
        """If APScheduler is installed, register all jobs with it and start.
        Otherwise return False; callers should fall back to `poll_due`."""
        try:
            from apscheduler.schedulers.background import BackgroundScheduler  # type: ignore
            from apscheduler.triggers.cron import CronTrigger  # type: ignore
            from apscheduler.triggers.date import DateTrigger  # type: ignore
            from apscheduler.triggers.interval import IntervalTrigger  # type: ignore
        except Exception:
            return False
        sched = BackgroundScheduler(timezone="UTC")
        for job in self._jobs.values():
            if not job.enabled:
                continue
            trig = None
            if job.spec.cron:
                m, h, dom, mon, dow = job.spec.cron.split()
                trig = CronTrigger(minute=m, hour=h, day=dom, month=mon, day_of_week=dow)
            elif job.spec.date:
                dt = _parse_iso_utc(job.spec.date)
                if dt:
                    trig = DateTrigger(run_date=dt)
            elif job.spec.interval_seconds:
                trig = IntervalTrigger(seconds=job.spec.interval_seconds)
            if trig is None:
                continue
            sid = job.schedule_id
            sched.add_job(
                lambda sid=sid: self._fire_callback and self._fire_callback(
                    self._jobs[sid]),
                trigger=trig, id=sid, replace_existing=True,
            )
        sched.start()
        self._scheduler = sched
        return True


_GLOBAL: ScheduleRegistry | None = None


def get_registry() -> ScheduleRegistry:
    global _GLOBAL
    if _GLOBAL is None:
        _GLOBAL = ScheduleRegistry()
    return _GLOBAL


def reset_registry() -> None:
    """For tests."""
    global _GLOBAL
    _GLOBAL = None


__all__ = [
    "ScheduleSpec", "ScheduledJob", "ScheduleRegistry",
    "get_registry", "reset_registry",
]
