"""Wardrobe & dynasty costume swap (requirement doc §3 角色换肤).

Use FLUX Kontext for image-level wardrobe edits (preferred), or a prompt-only
manifest entry as a fallback. Common presets cover modern + 6 Chinese dynasties.
"""
from __future__ import annotations

import json
import logging
import pathlib
from dataclasses import dataclass, field
from typing import Any

_log = logging.getLogger(__name__)


COSTUME_PRESETS = [
    ("modern_casual",  "现代休闲",  "T 恤 + 牛仔 + 帆布鞋"),
    ("modern_formal",  "现代正装",  "高定西装 + 衬衫 + 领带"),
    ("ancient_song",   "宋朝服饰",  "宋制襦裙 + 广袖 + 缎带"),
    ("ancient_tang",   "唐朝服饰",  "唐制襦裙 + 披帛 + 鲜艳色彩"),
    ("ancient_ming",   "明朝服饰",  "明制立领长袄 + 马面裙"),
    ("ancient_qing",   "清朝服饰",  "清制旗装 + 领花 + 长盘扣"),
    ("ancient_qin",    "秦汉服饰",  "曲裾深衣 + 玉佩"),
    ("ancient_wuxia",  "武侠服饰",  "粗布长袍 + 革带 + 包袱剑"),
    ("xianxia_robe",   "仙侠袍",    "白色仙袍 + 玉冠 + 灵纹纹样"),
    ("japanese_yukata","日式浴衣",  "夏季浴衣 + 木屐 + 团扇"),
    ("korean_hanbok",  "韩式韩服",  "韩服上衣 + 长裙 + 蝶结"),
]


@dataclass
class CostumeEntry:
    key: str
    name_zh: str
    description: str
    prompt: str
    image_url: str | None = None


@dataclass
class WardrobeSheet:
    char_id: str
    entries: list[CostumeEntry] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "char_id": self.char_id,
            "entries": [e.__dict__ for e in self.entries],
        }


class WardrobeBuilder:
    def __init__(
        self,
        data_dir: str | pathlib.Path = "./data/characters",
        flux_kontext=None,
    ):
        self.data_dir = pathlib.Path(data_dir)
        self.flux = flux_kontext

    def build(self, char_id: str, canonical_image_url: str | None = None) -> WardrobeSheet:
        sheet = WardrobeSheet(char_id=char_id, entries=[])
        for key, zh, descr in COSTUME_PRESETS:
            prompt = f"将角色更换为「{descr}」，保留五官、发型、锁定符号；服饰风格仍写实可考。"
            entry = CostumeEntry(key=key, name_zh=zh, description=descr, prompt=prompt)
            if self.flux is not None and canonical_image_url:
                try:
                    entry.image_url = self.flux.edit(
                        base_image_url=canonical_image_url,
                        instruction=prompt,
                    )
                except Exception as e:
                    _log.warning("flux wardrobe edit failed: %s", e)
            sheet.entries.append(entry)

        out_dir = self.data_dir / char_id / "wardrobe"
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "sheet.json").write_text(
            json.dumps(sheet.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return sheet


__all__ = ["WardrobeBuilder", "WardrobeSheet", "CostumeEntry", "COSTUME_PRESETS"]
