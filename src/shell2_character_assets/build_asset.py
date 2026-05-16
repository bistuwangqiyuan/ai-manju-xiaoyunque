"""Top-level orchestrator that builds a 14-image character asset library.

Pipeline:
    1. Read prompts/characters/{char_id}.yaml
    2. Seedream 5.0 Lite → 8 multi-angle主图
    3. 即梦 4.6 → 6 pose/wardrobe variants (referencing #1's first 2 images)
    4. Manual or automated curation → keep 10-14 high-quality
    5. InfiniteYou → extract 512-d ID embedding
    6. Persist to data/characters/{char_id}/ and a manifest JSON
"""
from __future__ import annotations

import json
import logging
import pathlib
from dataclasses import dataclass, field
from typing import Mapping, Sequence

import yaml

from ..common.storage import Storage, default_storage
from .gen_seedream import SeedreamClient, SeedreamRequest
from .gen_jimeng import JimengImageClient, JimengRequest
from .id_lock_infiniteyou import InfiniteYouClient, IdEmbedding


_log = logging.getLogger(__name__)


@dataclass
class CharacterAsset:
    char_id: str
    name_zh: str
    reference_image_urls: list[str]
    canonical_image_url: str
    id_embedding: IdEmbedding | None = None
    metadata: dict = field(default_factory=dict)

    def to_manifest(self) -> dict:
        return {
            "char_id": self.char_id,
            "name_zh": self.name_zh,
            "reference_image_urls": self.reference_image_urls,
            "canonical_image_url": self.canonical_image_url,
            "id_embedding_dim": len(self.id_embedding.embedding) if self.id_embedding else 0,
            "metadata": self.metadata,
        }


class CharacterAssetBuilder:
    def __init__(self,
                 prompts_dir: str | pathlib.Path = "./prompts/characters",
                 data_dir: str | pathlib.Path = "./data/characters",
                 storage: Storage | None = None,
                 seedream: SeedreamClient | None = None,
                 jimeng: JimengImageClient | None = None,
                 infiniteyou: InfiniteYouClient | None = None):
        self.prompts_dir = pathlib.Path(prompts_dir)
        self.data_dir = pathlib.Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.storage = storage or default_storage()
        self.seedream = seedream
        self.jimeng = jimeng
        self.infiniteyou = infiniteyou

    def build(self, char_id: str) -> CharacterAsset:
        spec = self._load_spec(char_id)

        seedream_imgs = self._gen_seedream(spec)
        jimeng_imgs = self._gen_jimeng(spec, anchor_refs=seedream_imgs[:2])

        all_imgs = seedream_imgs + jimeng_imgs
        canonical = seedream_imgs[0]

        id_embedding = None
        if self.infiniteyou:
            id_embedding = self.infiniteyou.extract_id(char_id, canonical)

        asset = CharacterAsset(
            char_id=char_id,
            name_zh=spec["name_zh"],
            reference_image_urls=all_imgs,
            canonical_image_url=canonical,
            id_embedding=id_embedding,
            metadata=spec,
        )
        self._persist(asset)
        return asset

    # ------------------------------------------------------------------

    def _load_spec(self, char_id: str) -> dict:
        path = self.prompts_dir / f"{char_id}.yaml"
        if not path.exists():
            raise FileNotFoundError(path)
        return yaml.safe_load(path.read_text(encoding="utf-8"))

    def _gen_seedream(self, spec: Mapping) -> list[str]:
        if not self.seedream:
            return list(spec.get("preset_canonical_images", []))[:8]
        prompt = "\n".join([
            spec.get("seedream_prompt_prefix", ""),
            "生成角色设定图组：正面 / 45 度 / 侧面 / 背面 全身 + 4 个表情特写（喜怒哀惧）",
            "古风3D国漫风：60% 白蛇缘起 + 30% 狐妖小红娘月红篇 + 10% 雾山五行",
            "9:16 竖屏构图，前景人物 50% 画面占比，景深虚化背景。",
            self._signature_lock_line(spec),
        ])
        return self.seedream.generate(SeedreamRequest(
            prompt=prompt, num_images=8, aspect_ratio="3:4", deep_thinking=True,
        ))

    def _gen_jimeng(self, spec: Mapping, anchor_refs: Sequence[str]) -> list[str]:
        if not self.jimeng:
            return list(spec.get("preset_variant_images", []))[:6]
        prompt = "\n".join([
            spec.get("jimeng_variant_prompt", ""),
            "姿态 / 服装变体 6 张：日常装、出行装、雨中、月夜、战斗式、坐姿端立",
            self._signature_lock_line(spec),
        ])
        return self.jimeng.generate(JimengRequest(
            prompt=prompt, reference_images=list(anchor_refs),
            num_images=6, aspect_ratio="3:4", reference_weight=0.85,
        ))

    @staticmethod
    def _signature_lock_line(spec: Mapping) -> str:
        marks = spec.get("signature_marks", [])
        if not marks:
            return ""
        if isinstance(marks, list):
            marks = "; ".join(marks)
        return f"锁定符号（必须可见）：{marks}"

    def _persist(self, asset: CharacterAsset) -> None:
        char_dir = self.data_dir / asset.char_id
        char_dir.mkdir(parents=True, exist_ok=True)
        manifest = char_dir / "manifest.json"
        manifest.write_text(
            json.dumps(asset.to_manifest(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        if asset.id_embedding:
            (char_dir / "id_embedding.json").write_text(
                json.dumps({
                    "char_id": asset.char_id,
                    "embedding": asset.id_embedding.embedding,
                    "canonical": asset.id_embedding.canonical_image_url,
                }, ensure_ascii=False),
                encoding="utf-8",
            )
        _log.info("persisted asset %s → %s", asset.char_id, manifest)
