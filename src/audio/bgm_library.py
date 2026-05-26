"""V10 §7.2 — BGM library loader.

Loads ``config/bgm_library.yaml`` and exposes:

    list_entries()                                   -> list[BgmEntry]
    find_by_id(bgm_id)                               -> BgmEntry | None
    filter(genres=..., moods=..., bpm_range=...)     -> list[BgmEntry]

Each entry has a deterministic id, label, tags (genre + mood), bpm and a
``path`` that the worker can pull from disk or remote.
"""
from __future__ import annotations

import logging
import pathlib
from dataclasses import dataclass, field
from typing import Any

_log = logging.getLogger(__name__)

_REPO = pathlib.Path(__file__).resolve().parents[2]
_BGM_YAML = _REPO / "config" / "bgm_library.yaml"


@dataclass
class BgmEntry:
    id: str
    label: str
    genre: list[str] = field(default_factory=list)
    mood: list[str] = field(default_factory=list)
    bpm: int = 100
    duration_sec: int = 90
    license: str = "CC0"
    path: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id, "label": self.label,
            "genre": list(self.genre), "mood": list(self.mood),
            "bpm": self.bpm, "duration_sec": self.duration_sec,
            "license": self.license, "path": self.path,
        }


def _load_yaml(path: pathlib.Path) -> dict[str, Any]:
    try:
        import yaml  # type: ignore
        return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception:
        from .voice_library import _mini_yaml_parse
        return _mini_yaml_parse(path.read_text(encoding="utf-8"))


class BgmLibrary:
    def __init__(self, path: pathlib.Path | str | None = None):
        self.path = pathlib.Path(path) if path else _BGM_YAML
        self._entries: list[BgmEntry] = []
        self._by_id: dict[str, BgmEntry] = {}
        self._loaded = False

    def _ensure_loaded(self) -> None:
        if self._loaded:
            return
        if not self.path.exists():
            _log.warning("BGM library not found at %s", self.path)
            self._loaded = True
            return
        data = _load_yaml(self.path)
        for raw in data.get("entries") or []:
            entry = BgmEntry(
                id=raw.get("id", ""),
                label=raw.get("label", ""),
                genre=list(raw.get("genre") or []),
                mood=list(raw.get("mood") or []),
                bpm=int(raw.get("bpm") or 100),
                duration_sec=int(raw.get("duration_sec") or 90),
                license=raw.get("license") or "CC0",
                path=raw.get("path") or "",
            )
            if entry.id:
                self._entries.append(entry)
                self._by_id[entry.id] = entry
        self._loaded = True

    def list_entries(self) -> list[BgmEntry]:
        self._ensure_loaded()
        return list(self._entries)

    def find_by_id(self, bgm_id: str) -> BgmEntry | None:
        self._ensure_loaded()
        return self._by_id.get(bgm_id)

    def filter(self, *, genres: list[str] | None = None,
               moods: list[str] | None = None,
               bpm_range: tuple[int, int] | None = None) -> list[BgmEntry]:
        self._ensure_loaded()
        result = list(self._entries)
        if genres:
            gset = {g.lower() for g in genres}
            result = [e for e in result if any(g.lower() in gset for g in e.genre)]
        if moods:
            mset = {m.lower() for m in moods}
            result = [e for e in result if any(m.lower() in mset for m in e.mood)]
        if bpm_range:
            lo, hi = bpm_range
            result = [e for e in result if lo <= e.bpm <= hi]
        return result


_GLOBAL: BgmLibrary | None = None


def get_library() -> BgmLibrary:
    global _GLOBAL
    if _GLOBAL is None:
        _GLOBAL = BgmLibrary()
    return _GLOBAL


__all__ = ["BgmEntry", "BgmLibrary", "get_library"]
