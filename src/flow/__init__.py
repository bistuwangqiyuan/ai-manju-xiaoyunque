"""V10 §9 — Pipeline flow + dual-mode orchestration.

Modules:
    templates    — 10 viral short-drama templates (load + apply)
    pause_gate   — Step-by-step confirmation gating (WebSocket-friendly)
    scheduler    — APScheduler-backed timed publishing
    drafts       — Draft / branch / fork helper for job versions
"""
from __future__ import annotations

__all__ = ["templates", "pause_gate", "scheduler", "drafts"]
