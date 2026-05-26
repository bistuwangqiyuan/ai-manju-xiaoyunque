"""Multi-genre template registry.

Genre templates live under ``config/genres/<id>.yaml`` and bundle:

- style anchor + style lock prompt
- default aspect ratio / episodes / duration
- character archetypes & scene library
- voice pack / BGM mood / platform presets
- sample themes (for the theme→novel wizard on the SaaS front-end)

The registry is the single source of truth for the ``GET /api/genres`` endpoint
and the orchestrator's style/character/scene injection.
"""
from __future__ import annotations

import functools
import pathlib
from dataclasses import dataclass, field
from typing import Any

import yaml


_REPO = pathlib.Path(__file__).resolve().parents[2]
GENRE_DIR = _REPO / "config" / "genres"


@dataclass
class GenreTemplate:
    id: str
    name_zh: str
    name_en: str
    description: str
    style_id: str
    aspect_ratio: str = "9:16"
    default_episodes: int = 10
    default_duration_per_episode_s: int = 80
    preferred_resolution: str = "1080x1920"
    language: str = "Chinese"
    voice_pack: str = "default"
    bgm_mood: str = "default"
    platform_preset: list[str] = field(default_factory=list)
    palette: dict[str, list[str]] = field(default_factory=dict)
    character_archetypes: list[dict[str, Any]] = field(default_factory=list)
    scenes: list[dict[str, Any]] = field(default_factory=list)
    signature_marks: list[str] = field(default_factory=list)
    sample_themes: list[str] = field(default_factory=list)
    style_lock_prompt: str = ""
    negative_prompt: str = ""
    preview_video_url: str | None = None
    preview_cover_url: str | None = None

    def to_summary(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name_zh": self.name_zh,
            "name_en": self.name_en,
            "description": self.description,
            "style_id": self.style_id,
            "aspect_ratio": self.aspect_ratio,
            "default_episodes": self.default_episodes,
            "sample_themes": self.sample_themes,
            "preview_video_url": self.preview_video_url,
            "preview_cover_url": self.preview_cover_url,
        }


@functools.lru_cache(maxsize=1)
def load_genres() -> dict[str, GenreTemplate]:
    out: dict[str, GenreTemplate] = {}
    if not GENRE_DIR.exists():
        return out
    for path in sorted(GENRE_DIR.rglob("*.yaml")):
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except Exception:
            continue
        gid = data.get("id") or path.stem
        out[gid] = GenreTemplate(
            id=gid,
            name_zh=data.get("name_zh", gid),
            name_en=data.get("name_en", gid.title()),
            description=data.get("description", ""),
            style_id=data.get("style_id", f"{gid}_default"),
            aspect_ratio=data.get("aspect_ratio", "9:16"),
            default_episodes=int(data.get("default_episodes", 10)),
            default_duration_per_episode_s=int(data.get("default_duration_per_episode_s", 80)),
            preferred_resolution=data.get("preferred_resolution", "1080x1920"),
            language=data.get("language", "Chinese"),
            voice_pack=data.get("voice_pack", "default"),
            bgm_mood=data.get("bgm_mood", "default"),
            platform_preset=list(data.get("platform_preset", [])),
            palette=data.get("palette", {}) or {},
            character_archetypes=list(data.get("character_archetypes", []) or []),
            scenes=list(data.get("scenes", []) or []),
            signature_marks=list(data.get("signature_marks", []) or []),
            sample_themes=list(data.get("sample_themes", []) or []),
            style_lock_prompt=data.get("style_lock_prompt", ""),
            negative_prompt=data.get("negative_prompt", ""),
            preview_video_url=data.get("preview_video_url"),
            preview_cover_url=data.get("preview_cover_url"),
        )
    return out


def get_genre(genre_id: str) -> GenreTemplate:
    g = load_genres().get(genre_id)
    if g is None:
        # graceful fall-back to ancient (flagship)
        g = load_genres().get("ancient")
    if g is None:
        raise KeyError(f"no genre template found and no 'ancient' fallback (dir={GENRE_DIR})")
    return g


def list_genre_ids() -> list[str]:
    return sorted(load_genres().keys())


__all__ = ["GenreTemplate", "load_genres", "get_genre", "list_genre_ids"]
