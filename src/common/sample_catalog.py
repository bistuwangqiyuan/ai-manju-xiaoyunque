"""Load official sample catalog and resolve playable video URLs."""
from __future__ import annotations

import os
import pathlib
from functools import lru_cache
from typing import Any

import yaml

_REPO = pathlib.Path(__file__).resolve().parents[2]
_CATALOG_PATH = _REPO / "config" / "sample_catalog.yaml"


@lru_cache(maxsize=1)
def _load_raw() -> dict[str, Any]:
    with _CATALOG_PATH.open(encoding="utf-8") as f:
        return yaml.safe_load(f)


def repo_root() -> pathlib.Path:
    return _REPO


def catalog_samples() -> list[dict[str, Any]]:
    data = _load_raw()
    out: list[dict[str, Any]] = []
    for s in data.get("samples", []):
        slug = s["slug"]
        out.append(
            {
                **s,
                "video_url": f"/samples/{slug}.mp4",
                "cover_url": f"/samples/{slug}.jpg",
            }
        )
    return out


def author_label() -> str:
    return str(_load_raw().get("author_label", "官方示例 · R40 实测"))


def official_gallery_items() -> list[dict[str, Any]]:
    label = author_label()
    items: list[dict[str, Any]] = []
    for s in catalog_samples():
        items.append(
            {
                "id": s["id"],
                "kind": "official",
                "title": s["title"],
                "subtitle": s.get("subtitle"),
                "genre": s.get("genre", "ancient"),
                "style": s.get("style", ""),
                "video_url": s["video_url"],
                "cover_url": s.get("cover_url"),
                "quality_score": s.get("quality_score"),
                "episodes": s.get("episodes", 1),
                "author_label": label,
            }
        )
    return items


def sample_bundles() -> list[tuple[str, str]]:
    return [(s["video_url"], s["cover_url"]) for s in catalog_samples()]


def sample_video_paths() -> list[pathlib.Path]:
    """Absolute paths to synced mp4 under web/public/samples/."""
    pub = _REPO / "web" / "public" / "samples"
    paths: list[pathlib.Path] = []
    for s in catalog_samples():
        p = pub / f"{s['slug']}.mp4"
        if p.is_file():
            paths.append(p)
    if paths:
        return sorted(paths)
    # Fallback: any mp4 in repo sample/ or public/samples
    for base in (_REPO / "sample", pub):
        found = sorted(base.glob("*.mp4"))
        if found:
            return found
    return []


def is_playable_video_url(url: str | None) -> bool:
    if not url:
        return False
    u = url.strip()
    if not u:
        return False
    if "mock.tos.local" in u:
        return False
    if u.startswith("/samples/"):
        rel = u.removeprefix("/samples/")
        return (_REPO / "web" / "public" / "samples" / rel).is_file()
    if u.startswith("/storage/"):
        storage = os.environ.get("STORAGE_DIR", "data/storage")
        local = pathlib.Path(storage) / u.removeprefix("/storage/")
        return local.is_file()
    if u.startswith("http://") or u.startswith("https://"):
        return True
    return False


def resolve_playable_url(
    video_url: str | None,
    cover_url: str | None,
    *,
    seed: int = 0,
) -> tuple[str, str | None]:
    """Map mock or missing URLs to a real catalog sample."""
    bundles = sample_bundles()
    if not bundles:
        return video_url or "", cover_url

    fallback_video, fallback_cover = bundles[seed % len(bundles)]

    if not video_url or not is_playable_video_url(video_url):
        return fallback_video, fallback_cover

    if video_url.startswith("/samples/"):
        slug = pathlib.Path(video_url).stem
        for s in catalog_samples():
            if s["slug"] == slug:
                return s["video_url"], cover_url or s.get("cover_url")
        return fallback_video, fallback_cover

    return video_url, cover_url
