"""Resolve Volcengine Visual AK/SK from common .env naming variants.

Supports:
  VOLC_ACCESS_KEY / VOLC_SECRET_KEY (canonical)
  VOLC_AK / VOLC_SK (project .env convention)

Some teams store VOLC_SK as Base64 of the plaintext secret; others store plaintext.
Use `volc_secret_key_candidates()` to obtain [raw, decoded?] for retry-on-401.
"""
from __future__ import annotations

import base64
import os


def resolve_volc_access_key(explicit: str | None = None) -> str:
    if explicit:
        return explicit.strip()
    return (
        os.environ.get("VOLC_ACCESS_KEY", "").strip()
        or os.environ.get("VOLC_AK", "").strip()
    )


def volc_secret_key_candidates(explicit: str | None = None) -> list[str]:
    """Return ordered unique candidates for signing (usually length 1–2)."""

    raw = (explicit or "").strip()
    if not raw:
        raw = os.environ.get("VOLC_SECRET_KEY", "").strip() or os.environ.get("VOLC_SK", "").strip()
    if not raw:
        return []

    out: list[str] = [raw]
    if os.environ.get("VOLC_SK_BASE64", "").strip().lower() in {"1", "true", "yes"}:
        try:
            pad = (-len(raw)) % 4
            decoded = base64.b64decode(raw + "=" * pad, validate=False).decode("utf-8").strip()
            if decoded and decoded not in out:
                out.insert(0, decoded)  # prefer decoded when user explicitly flags base64
        except Exception:  # noqa: BLE001
            pass
        return out

    try:
        pad = (-len(raw)) % 4
        decoded = base64.b64decode(raw + "=" * pad, validate=False).decode("utf-8").strip()
        if decoded and decoded not in out and 8 <= len(decoded) <= 256:
            out.append(decoded)
    except Exception:  # noqa: BLE001
        pass
    return out


def resolve_volc_secret_key(explicit: str | None = None) -> str:
    """Backward-compat: first signing candidate."""

    cands = volc_secret_key_candidates(explicit)
    return cands[0] if cands else ""
