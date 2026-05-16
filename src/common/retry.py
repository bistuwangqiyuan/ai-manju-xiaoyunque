"""Exponential-backoff retry helpers."""
from __future__ import annotations

import functools
import logging
import random
import time
from typing import Callable, Iterable, Type, TypeVar


_T = TypeVar("_T")
_log = logging.getLogger(__name__)


def retry(
    *,
    exceptions: Iterable[Type[BaseException]] = (Exception,),
    attempts: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
    jitter: float = 0.2,
) -> Callable[[Callable[..., _T]], Callable[..., _T]]:
    exc_tuple = tuple(exceptions)

    def decorator(fn: Callable[..., _T]) -> Callable[..., _T]:
        @functools.wraps(fn)
        def wrapped(*args, **kwargs) -> _T:
            last_exc: BaseException | None = None
            for attempt in range(1, attempts + 1):
                try:
                    return fn(*args, **kwargs)
                except exc_tuple as exc:
                    last_exc = exc
                    if attempt == attempts:
                        break
                    delay = min(max_delay, base_delay * (2 ** (attempt - 1)))
                    delay *= 1.0 + random.uniform(-jitter, jitter)
                    _log.warning(
                        "%s attempt %d/%d failed: %s; sleeping %.2fs",
                        fn.__name__, attempt, attempts, exc, delay,
                    )
                    time.sleep(delay)
            assert last_exc is not None
            raise last_exc

        return wrapped

    return decorator
