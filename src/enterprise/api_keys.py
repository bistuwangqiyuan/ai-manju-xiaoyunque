"""V10 §11 — Public API key helpers.

Key format: ``xyq_live_<24 random url-safe chars>`` (32 chars total).
Storage: ``prefix = first 8 chars (excluding xyq_)`` + ``secret_hash =
SHA-256(raw_token)``.
"""
from __future__ import annotations

import hashlib
import hmac
import secrets
from dataclasses import dataclass
from typing import Any


_PREFIX_LIVE = "xyq_live_"
_PREFIX_TEST = "xyq_test_"


@dataclass
class IssuedApiKey:
    """Returned ONCE to the caller; the raw token must be stored client-side."""
    raw_token: str
    prefix: str
    secret_hash: str
    is_test: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "raw_token": self.raw_token, "prefix": self.prefix,
            "secret_hash": self.secret_hash, "is_test": self.is_test,
        }


def generate(*, test: bool = False) -> IssuedApiKey:
    body = secrets.token_urlsafe(24)
    raw = (_PREFIX_TEST if test else _PREFIX_LIVE) + body
    prefix = body[:8]
    return IssuedApiKey(
        raw_token=raw, prefix=prefix,
        secret_hash=hash_secret(raw),
        is_test=test,
    )


def hash_secret(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def verify(raw_token: str, stored_hash: str) -> bool:
    return hmac.compare_digest(hash_secret(raw_token), stored_hash)


def extract_prefix(raw_token: str) -> str | None:
    """Return the 8-char prefix used to look up the row."""
    for p in (_PREFIX_LIVE, _PREFIX_TEST):
        if raw_token.startswith(p):
            body = raw_token[len(p):]
            return body[:8] if len(body) >= 8 else None
    return None


def is_test_key(raw_token: str) -> bool:
    return raw_token.startswith(_PREFIX_TEST)


def lookup_key(session, ApiKey_cls, raw_token: str):
    """Find an ApiKey row by raw token (using the prefix index)."""
    prefix = extract_prefix(raw_token)
    if not prefix:
        return None
    candidate = session.query(ApiKey_cls).filter(
        ApiKey_cls.prefix == prefix,
    ).first()
    if candidate is None or not candidate.enabled:
        return None
    if not verify(raw_token, candidate.secret_hash):
        return None
    return candidate


__all__ = [
    "IssuedApiKey", "generate", "hash_secret", "verify",
    "extract_prefix", "is_test_key", "lookup_key",
]
