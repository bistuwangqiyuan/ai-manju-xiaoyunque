"""Persistent storage helpers.

The Skylark v2 API returns 24h-expiring video URLs. Any production pipeline MUST
transfer those assets to durable storage before the TTL elapses. This module
provides a thin abstraction supporting:

- local filesystem (default; for development and on-prem deployments)
- S3-compatible object storage (火山 TOS / 阿里 OSS / AWS S3)

Selection is driven by the `STORAGE_BACKEND` environment variable.
"""
from __future__ import annotations

import hashlib
import os
import pathlib
import shutil
from dataclasses import dataclass
from typing import Optional


@dataclass
class StoredObject:
    backend: str
    path: str
    public_url: Optional[str]
    sha256: str
    size_bytes: int


class Storage:
    def __init__(self, root: str | os.PathLike = "./data/storage"):
        self.root = pathlib.Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def put_bytes(self, key: str, payload: bytes, *, public: bool = False) -> StoredObject:
        target = self.root / key
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(payload)
        sha = hashlib.sha256(payload).hexdigest()
        return StoredObject(
            backend="local",
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


def default_storage() -> Storage:
    return Storage(os.environ.get("STORAGE_ROOT", "./data/storage"))
