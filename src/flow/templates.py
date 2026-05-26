"""V10 §9.1 — Viral template loader & applier.

Loads ``config/hot_templates.yaml`` and exposes:

    list_templates()                  -> list of (id, label, genre, ...)
    get_template(tid)                 -> HotTemplate
    apply_template(template, payload) -> dict (job_create payload patched
                                         with template defaults)

Use case: the wizard mode lets the user pick a template card; this module
patches the job-create payload so the generator inherits genre / hook /
duration / subtitle style / BGM seed without manual configuration.
"""
from __future__ import annotations

import logging
import pathlib
from dataclasses import dataclass, field
from typing import Any

_log = logging.getLogger(__name__)

_REPO = pathlib.Path(__file__).resolve().parents[2]
_TEMPLATES_YAML = _REPO / "config" / "hot_templates.yaml"


@dataclass
class StructureBeat:
    beat: str
    seconds: int
    note: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {"beat": self.beat, "seconds": self.seconds, "note": self.note}


@dataclass
class HotTemplate:
    id: str
    label: str
    genre: str
    sub_genre: str = ""
    aspect_ratio: str = "9:16"
    resolution: str = "1080p"
    duration_per_episode_s: int = 75
    hook_template: str = ""
    structure: list[StructureBeat] = field(default_factory=list)
    bgm_query: str = ""
    subtitle_style: str = "modern_sans"
    cover_prompt: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id, "label": self.label, "genre": self.genre,
            "sub_genre": self.sub_genre, "aspect_ratio": self.aspect_ratio,
            "resolution": self.resolution,
            "duration_per_episode_s": self.duration_per_episode_s,
            "hook_template": self.hook_template,
            "structure": [s.to_dict() for s in self.structure],
            "bgm_query": self.bgm_query, "subtitle_style": self.subtitle_style,
            "cover_prompt": self.cover_prompt,
        }


def _load_yaml(path: pathlib.Path) -> dict[str, Any]:
    try:
        import yaml  # type: ignore
        return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception:
        from ..audio.voice_library import _mini_yaml_parse
        return _mini_yaml_parse(path.read_text(encoding="utf-8"))


class TemplateRegistry:
    def __init__(self, path: pathlib.Path | str | None = None):
        self.path = pathlib.Path(path) if path else _TEMPLATES_YAML
        self._items: dict[str, HotTemplate] = {}
        self._loaded = False

    def _ensure_loaded(self) -> None:
        if self._loaded:
            return
        if not self.path.exists():
            _log.warning("template yaml missing: %s", self.path)
            self._loaded = True
            return
        data = _load_yaml(self.path)
        for raw in data.get("templates") or []:
            tid = raw.get("id")
            if not tid:
                continue
            structure = [
                StructureBeat(
                    beat=str(s.get("beat", "")),
                    seconds=int(s.get("seconds") or 0),
                    note=str(s.get("note", "")),
                )
                for s in (raw.get("structure") or [])
            ]
            self._items[tid] = HotTemplate(
                id=tid,
                label=raw.get("label", tid),
                genre=raw.get("genre") or "modern",
                sub_genre=raw.get("sub_genre") or "",
                aspect_ratio=raw.get("aspect_ratio") or "9:16",
                resolution=raw.get("resolution") or "1080p",
                duration_per_episode_s=int(raw.get("duration_per_episode_s") or 75),
                hook_template=raw.get("hook_template") or "",
                structure=structure,
                bgm_query=raw.get("bgm_query") or "",
                subtitle_style=raw.get("subtitle_style") or "modern_sans",
                cover_prompt=raw.get("cover_prompt") or "",
            )
        self._loaded = True

    def list_templates(self) -> list[HotTemplate]:
        self._ensure_loaded()
        return list(self._items.values())

    def get(self, tid: str) -> HotTemplate | None:
        self._ensure_loaded()
        return self._items.get(tid)


_GLOBAL: TemplateRegistry | None = None


def get_registry() -> TemplateRegistry:
    global _GLOBAL
    if _GLOBAL is None:
        _GLOBAL = TemplateRegistry()
    return _GLOBAL


def apply_template(template: HotTemplate,
                   payload: dict[str, Any],
                   *, lead_name: str = "主角") -> dict[str, Any]:
    """Return a new payload dict with template defaults applied (no override
    of user-set fields).
    """
    result = dict(payload)
    defaults = {
        "genre": template.genre,
        "aspect_ratio": template.aspect_ratio,
        "resolution": template.resolution,
        "duration_per_episode_s": template.duration_per_episode_s,
        "template_id": template.id,
        "hook": template.hook_template.format(lead=lead_name),
        "bgm_query": template.bgm_query,
        "subtitle_style": template.subtitle_style,
        "cover_prompt": template.cover_prompt,
        "beat_structure": [b.to_dict() for b in template.structure],
    }
    for k, v in defaults.items():
        result.setdefault(k, v)
    return result


__all__ = [
    "StructureBeat", "HotTemplate", "TemplateRegistry",
    "get_registry", "apply_template",
]
