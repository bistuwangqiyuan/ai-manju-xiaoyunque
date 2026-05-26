"""V10 §5.2 — Bounded-concurrency parallel scheduler.

Wraps an arbitrary "render one task" coroutine in asyncio.gather with a
configurable concurrency limit.  Designed for ≤ ``MANJU_PARALLEL`` Manju
Agent calls or any other producer-task pattern.
"""
from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Iterable, TypeVar

_log = logging.getLogger(__name__)

T = TypeVar("T")
R = TypeVar("R")


@dataclass
class TaskResult:
    task_id: str
    ok: bool
    value: Any | None = None
    error: str | None = None
    elapsed_s: float = 0.0
    attempts: int = 1


@dataclass
class SchedulerStats:
    total: int = 0
    succeeded: int = 0
    failed: int = 0
    elapsed_s: float = 0.0
    per_task: list[TaskResult] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "total": self.total,
            "succeeded": self.succeeded,
            "failed": self.failed,
            "elapsed_s": round(self.elapsed_s, 2),
            "throughput_per_s": round(self.succeeded / max(self.elapsed_s, 1e-3), 3),
            "per_task": [
                {"task_id": t.task_id, "ok": t.ok, "error": t.error,
                 "elapsed_s": round(t.elapsed_s, 2), "attempts": t.attempts}
                for t in self.per_task
            ],
        }


async def run_bounded(
    tasks: Iterable[tuple[str, Awaitable]],
    *,
    concurrency: int = 3,
    max_retries: int = 1,
    retry_backoff_s: float = 2.0,
    on_progress: Callable[[TaskResult], None] | None = None,
) -> SchedulerStats:
    """Execute ``tasks`` (an iterable of ``(task_id, coroutine_factory)``).

    Each coroutine factory is a *callable returning a fresh coroutine* — we
    cannot reuse coroutines on retry. So pass functions, not pre-awaitable
    objects.
    """
    sem = asyncio.Semaphore(concurrency)
    stats = SchedulerStats()
    task_list = list(tasks)
    stats.total = len(task_list)
    start = time.monotonic()

    async def _run_one(task_id: str, factory: Callable[[], Awaitable]):
        async with sem:
            t0 = time.monotonic()
            attempts = 0
            last_err: str | None = None
            while attempts < max_retries + 1:
                attempts += 1
                try:
                    value = await factory()
                    elapsed = time.monotonic() - t0
                    res = TaskResult(task_id=task_id, ok=True, value=value,
                                     elapsed_s=elapsed, attempts=attempts)
                    if on_progress:
                        try:
                            on_progress(res)
                        except Exception:
                            pass
                    stats.succeeded += 1
                    stats.per_task.append(res)
                    return
                except Exception as exc:
                    last_err = f"{type(exc).__name__}: {exc}"
                    if attempts <= max_retries:
                        await asyncio.sleep(retry_backoff_s * attempts)
            elapsed = time.monotonic() - t0
            res = TaskResult(task_id=task_id, ok=False, error=last_err,
                             elapsed_s=elapsed, attempts=attempts)
            if on_progress:
                try:
                    on_progress(res)
                except Exception:
                    pass
            stats.failed += 1
            stats.per_task.append(res)

    await asyncio.gather(*[_run_one(tid, fac) for tid, fac in task_list])
    stats.elapsed_s = time.monotonic() - start
    return stats


__all__ = ["TaskResult", "SchedulerStats", "run_bounded"]
