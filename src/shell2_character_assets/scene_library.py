"""Scene library — categorized + reusable scenes.

Requirement doc §4 场景环境:
    场景分类：室内闺房、庭院、朝堂、江湖、都市校园等一键生成
    场景复用：常用场景存档调用，降低重复生成成本
    镜头场景联动：近景 / 中景 / 远景随剧情自动切换

The library mirrors ``config/genres/*.yaml`` scenes section but adds a
process for storyboard-time camera-distance selection.
"""
from __future__ import annotations

import json
import logging
import pathlib
import random
from dataclasses import dataclass, field
from typing import Any

_log = logging.getLogger(__name__)


CAMERA_DISTANCES = ("wide", "medium", "close_up", "extreme_close_up")


@dataclass
class SceneAsset:
    id: str
    name_zh: str
    category: str
    keywords: list[str] = field(default_factory=list)
    image_urls: list[str] = field(default_factory=list)
    genre_tags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name_zh": self.name_zh,
            "category": self.category,
            "keywords": self.keywords,
            "image_urls": self.image_urls,
            "genre_tags": self.genre_tags,
        }


class SceneLibrary:
    """In-memory + on-disk scene catalog, seeded from genre YAML."""

    def __init__(self, data_dir: str | pathlib.Path = "./data/scenes"):
        self.data_dir = pathlib.Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self._scenes: dict[str, SceneAsset] = {}

    # ------------------------------------------------------------------

    def seed_from_genres(self) -> None:
        try:
            from src.genres import load_genres

            for g in load_genres().values():
                for sc in g.scenes:
                    scene_id = sc.get("id") or sc.get("name_zh", "")
                    if not scene_id:
                        continue
                    self.add(
                        SceneAsset(
                            id=f"{g.id}__{scene_id}",
                            name_zh=sc.get("name_zh", scene_id),
                            category=g.id,
                            keywords=list(sc.get("keywords", [])),
                            genre_tags=[g.id],
                        )
                    )
        except Exception as e:
            _log.warning("scene seed failed: %s", e)

    def add(self, scene: SceneAsset) -> None:
        self._scenes[scene.id] = scene
        path = self.data_dir / f"{scene.id}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(scene.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def list(self, category: str | None = None) -> list[SceneAsset]:
        # Hot-load from disk
        for p in self.data_dir.glob("*.json"):
            sid = p.stem
            if sid in self._scenes:
                continue
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
                self._scenes[sid] = SceneAsset(**data)
            except Exception:
                continue
        if category is None:
            return sorted(self._scenes.values(), key=lambda s: (s.category, s.id))
        return [s for s in self._scenes.values() if s.category == category]

    def get(self, scene_id: str) -> SceneAsset | None:
        if scene_id in self._scenes:
            return self._scenes[scene_id]
        path = self.data_dir / f"{scene_id}.json"
        if not path.exists():
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
        sc = SceneAsset(**data)
        self._scenes[scene_id] = sc
        return sc

    # ------------------------------------------------------------------
    # Shot/scene linkage (requirement doc §4 镜头场景联动)
    # ------------------------------------------------------------------

    @staticmethod
    def suggest_camera_distance(beat_kind: str, *, intensity: float = 0.5) -> str:
        """Pick a camera distance from beat kind.

        ``beat_kind`` ∈ {hook, buildup, climax, twist, cliff}; ``intensity`` 0-1.
        Returns one of CAMERA_DISTANCES. Deterministic-ish (rng with hash seed).
        """
        mapping = {
            "hook": ("close_up", "extreme_close_up", "medium"),
            "buildup": ("medium", "wide", "medium"),
            "climax": ("close_up", "medium", "wide"),
            "twist": ("close_up", "extreme_close_up", "medium"),
            "cliff": ("extreme_close_up", "close_up", "medium"),
        }
        choices = mapping.get(beat_kind, CAMERA_DISTANCES)
        # weight by intensity: high intensity → tighter
        idx = min(len(choices) - 1, int(intensity * len(choices)))
        return choices[idx]

    @staticmethod
    def suggest_distances_for_shotlist(shots: list[dict]) -> list[dict]:
        """Enrich a shot list with camera_distance + scene_anchor."""
        out: list[dict] = []
        for i, shot in enumerate(shots):
            kind = shot.get("beat_kind") or _infer_beat(i, len(shots))
            intensity = shot.get("intensity", 0.4 + 0.6 * (i / max(len(shots), 1)))
            dist = SceneLibrary.suggest_camera_distance(kind, intensity=intensity)
            sc = dict(shot)
            sc.setdefault("camera_distance", dist)
            out.append(sc)
        return out


def _infer_beat(i: int, n: int) -> str:
    pct = i / max(n - 1, 1)
    if pct < 0.10:
        return "hook"
    if pct < 0.60:
        return "buildup"
    if pct < 0.80:
        return "climax"
    if pct < 0.92:
        return "twist"
    return "cliff"


__all__ = ["SceneLibrary", "SceneAsset", "CAMERA_DISTANCES"]
