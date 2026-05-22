"""Expression library — generate 喜怒哀惊羞冷 sheets per character.

Requirement doc §3 表情库：喜怒哀惊羞冷等全自动情绪切换。

For each emotion we produce 1 close-up sheet via Jimeng (or fall back to a
prompt-only manifest entry when no API key is present). The manifest is
self-contained so downstream Skylark prompts can pull e.g.
``data/characters/{cid}/expressions/sad.jpg`` directly.
"""
from __future__ import annotations

import json
import logging
import pathlib
from dataclasses import dataclass, field
from typing import Any

import yaml

_log = logging.getLogger(__name__)


# Requirement-doc canonical 6 emotions + a few extras the libraries commonly want.
EMOTIONS = [
    ("happy", "喜", "嘴角上扬，眼眶弯出温暖弧度，眉宇松开"),
    ("angry", "怒", "眉头紧锁，瞳孔收缩，唇线紧抿，鼻翼略张"),
    ("sad",   "哀", "睫毛微颤，眼眶含泪，唇角下垂，下巴轻收"),
    ("shock", "惊", "瞳孔放大，嘴唇半张，肩部紧绷"),
    ("shy",   "羞", "微低头，红晕扫过两颊，目光斜飘"),
    ("cold",  "冷", "下颌微抬，眼神锐利，唇线平直"),
    ("smile_soft", "温笑", "唇角上扬幅度小，眼睛眯成弯月"),
    ("smirk",      "得意", "嘴角斜挑，眉毛微抬"),
]


@dataclass
class ExpressionEntry:
    key: str
    name_zh: str
    description: str
    prompt: str
    image_url: str | None = None


@dataclass
class ExpressionSheet:
    char_id: str
    entries: list[ExpressionEntry] = field(default_factory=list)
    sheet_image_url: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "char_id": self.char_id,
            "sheet_image_url": self.sheet_image_url,
            "entries": [
                {
                    "key": e.key,
                    "name_zh": e.name_zh,
                    "description": e.description,
                    "prompt": e.prompt,
                    "image_url": e.image_url,
                }
                for e in self.entries
            ],
        }


class ExpressionLibraryBuilder:
    def __init__(
        self,
        prompts_dir: str | pathlib.Path = "./prompts/characters",
        data_dir: str | pathlib.Path = "./data/characters",
        jimeng=None,
        seedream=None,
    ):
        self.prompts_dir = pathlib.Path(prompts_dir)
        self.data_dir = pathlib.Path(data_dir)
        self.jimeng = jimeng
        self.seedream = seedream

    def build(self, char_id: str) -> ExpressionSheet:
        spec_path = self.prompts_dir / f"{char_id}.yaml"
        spec = (
            yaml.safe_load(spec_path.read_text(encoding="utf-8"))
            if spec_path.exists()
            else {}
        )
        base_prompt = spec.get("seedream_prompt_prefix", "")
        sheet = ExpressionSheet(char_id=char_id, entries=[])

        for key, zh, descr in EMOTIONS:
            prompt = (
                f"{base_prompt}\n"
                f"表情：{zh}（{descr}）\n"
                "镜头：胸口以上特写，9:16，前景人物 60% 占比，背景虚化。"
            )
            entry = ExpressionEntry(key=key, name_zh=zh, description=descr, prompt=prompt)
            if self.jimeng is not None:
                try:
                    from .gen_jimeng import JimengRequest

                    urls = self.jimeng.generate(
                        JimengRequest(prompt=prompt, num_images=1, aspect_ratio="3:4")
                    )
                    entry.image_url = (urls or [None])[0]
                except Exception as e:
                    _log.warning("jimeng expression gen failed: %s", e)
            elif self.seedream is not None:
                try:
                    from .gen_seedream import SeedreamRequest

                    urls = self.seedream.generate(
                        SeedreamRequest(prompt=prompt, num_images=1, aspect_ratio="3:4")
                    )
                    entry.image_url = (urls or [None])[0]
                except Exception as e:
                    _log.warning("seedream expression gen failed: %s", e)
            sheet.entries.append(entry)

        # Persist
        out_dir = self.data_dir / char_id / "expressions"
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "sheet.json").write_text(
            json.dumps(sheet.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return sheet


__all__ = ["ExpressionLibraryBuilder", "ExpressionSheet", "ExpressionEntry", "EMOTIONS"]
