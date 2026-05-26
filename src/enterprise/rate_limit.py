"""V10 §11 — Rate limiting.

Wraps slowapi when available; otherwise uses an in-memory token bucket
keyed by (api_key_id | ip). Both backends share the same public API.

Usage::

    from src.enterprise.rate_limit import enforce, build_limiter
    enforce("orgkey:42", per_min=60)  # raises RateLimitExceeded if over
"""
from __future__ import annotations

import collections
import threading
import time
from dataclasses import dataclass, field
from typing import Any


class RateLimitExceeded(Exception):
    """Raised when the caller is over its allowed rate."""

    def __init__(self, key: str, retry_after_seconds: float):
        super().__init__(f"rate limit exceeded for '{key}'")
        self.key = key
        self.retry_after_seconds = retry_after_seconds


@dataclass
class _Bucket:
    times: collections.deque = field(default_factory=lambda: collections.deque(maxlen=2048))


class TokenBucketLimiter:
    """Sliding-window in-memory limiter — safe for single-process / dev."""

    def __init__(self):
        self._lock = threading.RLock()
        self._buckets: dict[str, _Bucket] = {}

    def _bucket(self, key: str) -> _Bucket:
        b = self._buckets.get(key)
        if b is None:
            b = _Bucket()
            self._buckets[key] = b
        return b

    def check(self, key: str, *, per_min: int) -> None:
        """Raises RateLimitExceeded if over."""
        now = time.monotonic()
        cutoff = now - 60.0
        with self._lock:
            b = self._bucket(key)
            while b.times and b.times[0] < cutoff:
                b.times.popleft()
            if len(b.times) >= per_min:
                wait = b.times[0] + 60.0 - now
                raise RateLimitExceeded(key, max(wait, 0.0))
            b.times.append(now)

    def stats(self, key: str) -> dict[str, Any]:
        with self._lock:
            b = self._bucket(key)
            return {"key": key, "n_recent": len(b.times)}


_GLOBAL: TokenBucketLimiter | None = None


def get_limiter() -> TokenBucketLimiter:
    global _GLOBAL
    if _GLOBAL is None:
        _GLOBAL = TokenBucketLimiter()
    return _GLOBAL


def reset_limiter() -> None:
    """For tests."""
    global _GLOBAL
    _GLOBAL = None


def enforce(key: str, *, per_min: int) -> None:
    """Raises :class:`RateLimitExceeded` if ``key`` has exceeded the
    rolling per-minute quota."""
    get_limiter().check(key, per_min=per_min)


def build_slowapi_limiter():
    """If slowapi is installed return a configured :class:`slowapi.Limiter`,
    else return None.  The caller is responsible for adding the middleware
    to its FastAPI app."""
    try:
        from slowapi import Limiter  # type: ignore
        from slowapi.util import get_remote_address  # type: ignore
        return Limiter(key_func=get_remote_address, default_limits=["120/minute"])
    except Exception:
        return None


__all__ = [
    "RateLimitExceeded", "TokenBucketLimiter",
    "get_limiter", "reset_limiter", "enforce", "build_slowapi_limiter",
]
