"""V10 §7.2 — Automatic SFX injection.

Walks a list of timed scene actions / dialogue lines, matches keywords to
the SFX library (``config/sfx_library.yaml``) and produces a sequence of
ffmpeg-ready ``SfxCue`` insertion points (path, start, volume).
"""
from __future__ import annotations

import logging
import pathlib
import re
from dataclasses import dataclass, field
from typing import Any

_log = logging.getLogger(__name__)

_REPO = pathlib.Path(__file__).resolve().parents[2]
_SFX_YAML = _REPO / "config" / "sfx_library.yaml"


@dataclass
class SfxEntry:
    id: str
    label: str
    keywords: list[str] = field(default_factory=list)
    duration_sec: float = 1.0
    path: str = ""
    suggested_volume: float = 0.5

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id, "label": self.label,
            "keywords": list(self.keywords),
            "duration_sec": self.duration_sec,
            "path": self.path, "suggested_volume": self.suggested_volume,
        }


@dataclass
class SfxCue:
    sfx_id: str
    label: str
    path: str
    start_sec: float
    duration_sec: float
    volume: float
    triggered_by: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "sfx_id": self.sfx_id, "label": self.label, "path": self.path,
            "start_sec": round(self.start_sec, 3),
            "duration_sec": round(self.duration_sec, 3),
            "volume": round(self.volume, 3),
            "triggered_by": self.triggered_by,
        }


def _load_yaml(path: pathlib.Path) -> dict[str, Any]:
    try:
        import yaml  # type: ignore
        return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception:
        from .voice_library import _mini_yaml_parse
        return _mini_yaml_parse(path.read_text(encoding="utf-8"))


class SfxLibrary:
    def __init__(self, path: pathlib.Path | str | None = None):
        self.path = pathlib.Path(path) if path else _SFX_YAML
        self._entries: list[SfxEntry] = []
        self._loaded = False

    def _ensure_loaded(self) -> None:
        if self._loaded:
            return
        if not self.path.exists():
            _log.warning("SFX library not found at %s", self.path)
            self._loaded = True
            return
        data = _load_yaml(self.path)
        for raw in data.get("entries") or []:
            self._entries.append(SfxEntry(
                id=raw.get("id", ""),
                label=raw.get("label", ""),
                keywords=list(raw.get("keywords") or []),
                duration_sec=float(raw.get("duration_sec") or 1.0),
                path=raw.get("path") or "",
                suggested_volume=float(raw.get("suggested_volume") or 0.5),
            ))
        self._loaded = True

    def list_entries(self) -> list[SfxEntry]:
        self._ensure_loaded()
        return list(self._entries)


def _match_keywords(text: str, entries: list[SfxEntry]) -> list[tuple[SfxEntry, str]]:
    text_l = text.lower()
    hits: list[tuple[SfxEntry, str]] = []
    seen_ids: set[str] = set()
    for entry in entries:
        for kw in entry.keywords:
            if not kw:
                continue
            if kw in text or (kw.isascii() and re.search(rf"\b{re.escape(kw)}\b", text_l)):
                if entry.id not in seen_ids:
                    hits.append((entry, kw))
                    seen_ids.add(entry.id)
                break
    return hits


def auto_inject(
    timed_actions: list[dict[str, Any]],
    *, library: SfxLibrary | None = None,
    volume_scale: float = 1.0,
    min_gap_sec: float = 0.5,
) -> list[SfxCue]:
    """Build SFX cues from scene actions / dialogue.

    Each ``timed_actions`` entry should provide:
        ``text``       — action description or dialogue line
        ``start``      — start time in seconds (defaults to 0)
        ``end``        — end time in seconds (optional)
    """
    lib = library or SfxLibrary()
    entries = lib.list_entries()
    cues: list[SfxCue] = []
    last_start_per_id: dict[str, float] = {}
    for raw in timed_actions:
        text = (raw.get("text") or "").strip()
        if not text:
            continue
        start = float(raw.get("start") or 0.0)
        end = float(raw.get("end") or (start + 3.0))
        for entry, kw in _match_keywords(text, entries):
            last = last_start_per_id.get(entry.id, -10.0)
            if (start - last) < min_gap_sec:
                continue
            cue = SfxCue(
                sfx_id=entry.id, label=entry.label, path=entry.path,
                start_sec=start,
                duration_sec=min(entry.duration_sec, max(end - start, 0.2)),
                volume=round(entry.suggested_volume * volume_scale, 3),
                triggered_by=kw,
            )
            cues.append(cue)
            last_start_per_id[entry.id] = start
    return cues


__all__ = ["SfxEntry", "SfxCue", "SfxLibrary", "auto_inject"]
