"""V10 §11 — Org invite token helpers."""
from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone


def generate_invite_token() -> str:
    return secrets.token_urlsafe(32)


def default_expiry(days: int = 7) -> datetime:
    return datetime.now(timezone.utc) + timedelta(days=days)


def is_expired(invite_expires_at: datetime,
               now: datetime | None = None) -> bool:
    now = now or datetime.now(timezone.utc)
    if invite_expires_at.tzinfo is None:
        invite_expires_at = invite_expires_at.replace(tzinfo=timezone.utc)
    return now >= invite_expires_at


__all__ = ["generate_invite_token", "default_expiry", "is_expired"]
