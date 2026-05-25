"""Persistent storage helpers.

The Skylark v2 API returns 24h-expiring video URLs. Any production pipeline MUST
transfer those assets to durable storage before the TTL elapses. This module
provides a thin abstraction supporting:

- local filesystem (default; for development and on-prem deployments)
- S3-compatible object storage (火山 TOS / 阿里 OSS / AWS S3)

Selection is driven by the ``STORAGE_BACKEND`` environment variable:

==============  ====================================================
value           backend
==============  ====================================================
``local``       local filesystem under ``STORAGE_ROOT``
``tos``         火山引擎 TOS (S3-compatible) via :mod:`tos_storage`
``oss``         alias of ``tos`` for阿里云 OSS (same protocol)
``s3``          alias of ``tos`` for AWS S3 / 任意 S3-compat
==============  ====================================================

If unset and ``TOS_BUCKET`` / ``S3_BUCKET`` env exists, will auto-pick ``tos``.
"""
from __future__ import annotations

import hashlib
import logging
import os
import pathlib
import shutil
from dataclasses import dataclass
from typing import Optional, Protocol

_log = logging.getLogger(__name__)


@dataclass
class StoredObject:
    backend: str
    path: str
    public_url: Optional[str]
    sha256: str
    size_bytes: int


class _StorageProto(Protocol):
    """Minimal interface needed by downstream code (Skylark client, etc.)."""

    def put_bytes(self, key: str, payload: bytes, *, public: bool = False) -> StoredObject: ...
    def put_file(self, key: str, src_path: str | os.PathLike, *, public: bool = False) -> StoredObject: ...
    def archive_url(self, key: str, url: str, *, timeout: float = 600.0) -> StoredObject: ...


class Storage:
    """Local filesystem implementation (default for development)."""

    backend_name = "local"

    def __init__(self, root: str | os.PathLike = "./data/storage"):
        self.root = pathlib.Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def put_bytes(self, key: str, payload: bytes, *, public: bool = False) -> StoredObject:
        target = self.root / key
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(payload)
        sha = hashlib.sha256(payload).hexdigest()
        return StoredObject(
            backend=self.backend_name,
            path=str(target.resolve()),
            public_url=None if not public else target.as_uri(),
            sha256=sha,
            size_bytes=len(payload),
        )

    def put_file(self, key: str, src_path: str | os.PathLike, *, public: bool = False) -> StoredObject:
        target = self.root / key
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src_path, target)
        return self.put_bytes(key, target.read_bytes(), public=public)

    def archive_url(self, key: str, url: str, *, timeout: float = 600.0) -> StoredObject:
        import urllib.request

        req = urllib.request.Request(url, headers={"User-Agent": "skylark-archive/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            payload = resp.read()
        return self.put_bytes(key, payload)


def _detect_backend() -> str:
    explicit = (os.environ.get("STORAGE_BACKEND") or "").strip().lower()
    if explicit in ("tos", "oss", "s3"):
        return "tos"
    if explicit == "local":
        return "local"
    # auto-detect: if TOS_BUCKET/S3_BUCKET set + creds present, prefer TOS
    if (
        (os.environ.get("TOS_BUCKET") or os.environ.get("S3_BUCKET"))
        and (os.environ.get("TOS_ACCESS_KEY") or os.environ.get("S3_ACCESS_KEY")
             or os.environ.get("VOLC_ACCESS_KEY") or os.environ.get("VOLC_AK"))
    ):
        return "tos"
    return "local"


def default_storage() -> _StorageProto:
    backend = _detect_backend()
    if backend == "tos":
        try:
            from .tos_storage import TosStorage
            return TosStorage()
        except Exception as e:  # noqa: BLE001
            _log.warning(
                "TOS storage init failed (%s); falling back to local filesystem", e,
            )
    return Storage(os.environ.get("STORAGE_ROOT", "./data/storage"))


__all__ = ["Storage", "StoredObject", "default_storage"]
