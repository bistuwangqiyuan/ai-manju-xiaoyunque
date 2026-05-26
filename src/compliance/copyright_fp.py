"""V10 §11.3 Copyright fingerprint library — pHash (images) + simhash (text).

A persistent JSON-on-disk database that protects users from accidentally
re-uploading copyrighted material.  We support two registries:

    1. Image pHash (64-bit perceptual hash, Hamming distance < 8 ⇒ match)
    2. Text SimHash (64-bit, Hamming distance < 6 ⇒ match)

For deployments with cloud Postgres/Redis the JSON file can be replaced by
plugging in a different ``Registry`` backend implementing the same protocol.

Falls back to deterministic SHA-1 based hashing when optional deps
(``imagehash`` / ``simhash`` / PIL) are not installed — still useful for
exact-duplicate detection but with much lower recall.
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import re
from dataclasses import dataclass, asdict
from typing import Iterable

_REPO = pathlib.Path(__file__).resolve().parents[2]
DEFAULT_DB = _REPO / "data" / "copyright_fp" / "registry.json"
DEFAULT_DB.parent.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# Hash primitives
# ---------------------------------------------------------------------------
def image_phash(image_path: str | pathlib.Path) -> str:
    """Return 16-hex (64-bit) pHash.  Fallback: SHA-1 of raw bytes."""
    try:
        from PIL import Image  # type: ignore
        import imagehash  # type: ignore
        return str(imagehash.phash(Image.open(image_path)))
    except Exception:
        return hashlib.sha1(pathlib.Path(image_path).read_bytes()).hexdigest()[:16]


def text_simhash(text: str, *, dim: int = 64) -> str:
    """64-bit simhash. Pure-Python fallback works without external simhash dep."""
    if not text:
        return "0" * (dim // 4)
    try:
        from simhash import Simhash  # type: ignore
        return f"{Simhash(text).value:016x}"
    except Exception:
        return _fallback_simhash(text, dim=dim)


def _fallback_simhash(text: str, *, dim: int = 64) -> str:
    tokens = re.findall(r"[\u4e00-\u9fff]|[A-Za-z0-9]+", text)
    if not tokens:
        return "0" * (dim // 4)
    v = [0] * dim
    for tok in tokens:
        h = int(hashlib.sha1(tok.encode("utf-8")).hexdigest(), 16)
        for i in range(dim):
            v[i] += 1 if (h >> i) & 1 else -1
    out = 0
    for i in range(dim):
        if v[i] > 0:
            out |= 1 << i
    return f"{out:016x}"


def hex_to_bits(h: str) -> int:
    return int(h, 16)


def hamming(a: str, b: str) -> int:
    return bin(hex_to_bits(a) ^ hex_to_bits(b)).count("1")


# ---------------------------------------------------------------------------
# Registry record + on-disk store
# ---------------------------------------------------------------------------
@dataclass
class Record:
    fp: str
    kind: str          # "image" | "text"
    label: str         # human-readable copyright owner / title
    user_id: int | None = None
    added_at: str = ""
    source_url: str | None = None


class CopyrightRegistry:
    """JSON-backed copyright fingerprint registry."""

    def __init__(self, path: pathlib.Path | str = DEFAULT_DB):
        self.path = pathlib.Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._records: list[Record] = []
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            return
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except Exception:
            return
        self._records = [Record(**r) for r in data.get("records", [])]

    def _save(self) -> None:
        payload = {"records": [asdict(r) for r in self._records]}
        self.path.write_text(json.dumps(payload, ensure_ascii=False, indent=2),
                             encoding="utf-8")

    # -- write ----------------------------------------------------------
    def add(self, *, fp: str, kind: str, label: str,
            user_id: int | None = None, source_url: str | None = None) -> Record:
        from datetime import datetime, timezone
        rec = Record(
            fp=fp.lower(), kind=kind, label=label, user_id=user_id,
            added_at=datetime.now(timezone.utc).isoformat(),
            source_url=source_url,
        )
        self._records.append(rec)
        self._save()
        return rec

    def add_image(self, image_path: str | pathlib.Path, label: str, **kw) -> Record:
        return self.add(fp=image_phash(image_path), kind="image", label=label, **kw)

    def add_text(self, text: str, label: str, **kw) -> Record:
        return self.add(fp=text_simhash(text), kind="text", label=label, **kw)

    # -- query ----------------------------------------------------------
    def find(self, *, fp: str, kind: str, threshold: int) -> list[tuple[Record, int]]:
        out: list[tuple[Record, int]] = []
        for r in self._records:
            if r.kind != kind:
                continue
            try:
                dist = hamming(fp, r.fp)
            except Exception:
                continue
            if dist <= threshold:
                out.append((r, dist))
        out.sort(key=lambda x: x[1])
        return out

    def check_image(self, image_path: str | pathlib.Path, *, threshold: int = 8) -> dict:
        fp = image_phash(image_path)
        hits = self.find(fp=fp, kind="image", threshold=threshold)
        return {
            "fp": fp,
            "hits": [{"label": r.label, "distance": d,
                      "user_id": r.user_id, "source_url": r.source_url}
                     for r, d in hits],
            "threshold": threshold,
            "is_match": bool(hits),
        }

    def check_text(self, text: str, *, threshold: int = 6) -> dict:
        fp = text_simhash(text)
        hits = self.find(fp=fp, kind="text", threshold=threshold)
        return {
            "fp": fp,
            "hits": [{"label": r.label, "distance": d,
                      "user_id": r.user_id, "source_url": r.source_url}
                     for r, d in hits],
            "threshold": threshold,
            "is_match": bool(hits),
        }

    def __len__(self) -> int:
        return len(self._records)


_GLOBAL: CopyrightRegistry | None = None


def get_registry() -> CopyrightRegistry:
    global _GLOBAL
    if _GLOBAL is None:
        _GLOBAL = CopyrightRegistry()
    return _GLOBAL


__all__ = [
    "image_phash", "text_simhash", "hamming",
    "CopyrightRegistry", "Record", "get_registry",
]
