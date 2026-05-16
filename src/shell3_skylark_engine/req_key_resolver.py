"""req_key for Skylark Agent 2.0 with vinput — locked from official 2026-05 docs.

The pre-launch "3-candidate fallback"探测 logic from earlier revisions is no longer
necessary now that the official documentation has been confirmed. We keep this
module purely as a backwards-compatible re-export so callers that import
`REQ_KEY_CANDIDATES` or `ReqKeyResolver` still work.
"""
from __future__ import annotations

from .client import SKYLARK_REQ_KEY


# Backwards-compatibility shims
REQ_KEY_CANDIDATES: tuple[str, ...] = (SKYLARK_REQ_KEY,)


class ReqKeyResolver:
    """Trivial resolver — always returns the single canonical req_key."""

    confirmed: str = SKYLARK_REQ_KEY

    def __init__(self, *, initial: str | None = None) -> None:
        if initial and initial != SKYLARK_REQ_KEY:
            # Fall back to official; do not honour stale guesses
            pass

    def ordered_candidates(self):
        yield SKYLARK_REQ_KEY

    def confirm(self, req_key: str) -> None:  # noqa: D401 — backwards compat
        return None
