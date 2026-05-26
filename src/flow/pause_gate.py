"""V10 §9.2 — Per-step pause / confirm gating.

The orchestrator's long-running pipeline can be paused after each step
listed in ``Job.confirm_required_at_steps``. While paused, a WebSocket
client (or polling REST consumer) can either:

    - approve()   — resume the pipeline
    - reject()    — mark the step's output as needing redo
    - modify()    — replace the step's output blob then resume

State is persisted to an in-memory + JSON-on-disk store keyed by
``(job_id, step_name)``. The orchestrator never touches a paused step's
output without an explicit ``approve`` / ``modify`` event.
"""
from __future__ import annotations

import json
import logging
import pathlib
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

_log = logging.getLogger(__name__)

_REPO = pathlib.Path(__file__).resolve().parents[2]
_DEFAULT_STORE = _REPO / "data" / "flow" / "pause_state.json"
_DEFAULT_STORE.parent.mkdir(parents=True, exist_ok=True)


_KNOWN_STEPS = (
    "novel", "screenplay", "characters", "scenes", "storyboard",
    "frames", "qa", "tts", "compose",
)


@dataclass
class PauseEvent:
    job_id: int
    step: str
    status: str            # pending | approved | rejected | modified
    summary: dict[str, Any] = field(default_factory=dict)
    user_payload: dict[str, Any] = field(default_factory=dict)
    created_at: str = ""
    updated_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "job_id": self.job_id, "step": self.step, "status": self.status,
            "summary": self.summary, "user_payload": self.user_payload,
            "created_at": self.created_at, "updated_at": self.updated_at,
        }


class PauseGate:
    def __init__(self, path: pathlib.Path | str = _DEFAULT_STORE):
        self.path = pathlib.Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._events: dict[tuple[int, str], PauseEvent] = {}
        self._waiters: dict[tuple[int, str], threading.Event] = {}
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            return
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            for ev in raw.get("events", []):
                e = PauseEvent(**ev)
                self._events[(e.job_id, e.step)] = e
        except Exception as exc:
            _log.debug("pause gate load failed: %s", exc)

    def _flush(self) -> None:
        with self._lock:
            data = {"events": [ev.to_dict() for ev in self._events.values()],
                    "saved_at": datetime.now(timezone.utc).isoformat()}
            self.path.write_text(json.dumps(data, ensure_ascii=False, indent=2),
                                 encoding="utf-8")

    def request_pause(self, job_id: int, step: str,
                      summary: dict[str, Any] | None = None) -> PauseEvent:
        if step not in _KNOWN_STEPS:
            _log.warning("pause requested for unknown step '%s'", step)
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        with self._lock:
            ev = PauseEvent(
                job_id=job_id, step=step, status="pending",
                summary=summary or {},
                created_at=ts, updated_at=ts,
            )
            self._events[(job_id, step)] = ev
            self._waiters[(job_id, step)] = threading.Event()
            self._flush()
        return ev

    def status(self, job_id: int, step: str) -> PauseEvent | None:
        with self._lock:
            return self._events.get((job_id, step))

    def list_pending(self, job_id: int | None = None) -> list[PauseEvent]:
        with self._lock:
            out = [e for e in self._events.values() if e.status == "pending"]
            if job_id is not None:
                out = [e for e in out if e.job_id == job_id]
            return out

    def approve(self, job_id: int, step: str,
                user_payload: dict[str, Any] | None = None) -> PauseEvent:
        return self._mutate(job_id, step, "approved", user_payload, signal=True)

    def reject(self, job_id: int, step: str,
               user_payload: dict[str, Any] | None = None) -> PauseEvent:
        return self._mutate(job_id, step, "rejected", user_payload, signal=True)

    def modify(self, job_id: int, step: str,
               user_payload: dict[str, Any]) -> PauseEvent:
        return self._mutate(job_id, step, "modified", user_payload, signal=True)

    def _mutate(self, job_id: int, step: str, status: str,
                user_payload: dict[str, Any] | None, *, signal: bool) -> PauseEvent:
        with self._lock:
            ev = self._events.get((job_id, step))
            if ev is None:
                raise KeyError(f"no pause event for job {job_id} step {step}")
            ev.status = status
            ev.user_payload = user_payload or {}
            ev.updated_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            self._flush()
            if signal:
                waiter = self._waiters.get((job_id, step))
                if waiter is not None:
                    waiter.set()
        return ev

    def wait_for_decision(self, job_id: int, step: str,
                          timeout_seconds: float = 300.0) -> PauseEvent | None:
        with self._lock:
            waiter = self._waiters.get((job_id, step))
            if waiter is None:
                waiter = threading.Event()
                self._waiters[(job_id, step)] = waiter
        ok = waiter.wait(timeout=timeout_seconds)
        if not ok:
            return None
        return self.status(job_id, step)

    def clear_job(self, job_id: int) -> int:
        with self._lock:
            keys = [k for k in self._events if k[0] == job_id]
            for k in keys:
                self._events.pop(k, None)
                w = self._waiters.pop(k, None)
                if w is not None:
                    w.set()
            self._flush()
            return len(keys)


_GLOBAL: PauseGate | None = None


def get_gate() -> PauseGate:
    global _GLOBAL
    if _GLOBAL is None:
        _GLOBAL = PauseGate()
    return _GLOBAL


def reset_gate() -> None:
    """For tests."""
    global _GLOBAL
    _GLOBAL = None


__all__ = ["PauseEvent", "PauseGate", "get_gate", "reset_gate"]
