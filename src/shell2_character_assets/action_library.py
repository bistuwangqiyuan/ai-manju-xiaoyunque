"""Action library — pose templates for common actions.

Requirement doc §3 动作库：站立、行走、对视、牵手、行礼、打斗等常用动作。

For each action we generate one keypose sheet (image) + a brief description
that the storyboard layer can drop into Skylark prompts. When Wan-Animate is
present we also stage a tiny driving clip from the action keypose.
"""
from __future__ import annotations

import json
import logging
import pathlib
from dataclasses import dataclass, field
from typing import Any

import yaml

_log = logging.getLogger(__name__)


ACTIONS = [
    ("stand",    "站立",   "双脚分开与肩同宽，身体放松，眼神平视前方"),
    ("walk",     "行走",   "侧身行走中态，前脚刚踏地，后腿摆动"),
    ("eye_lock", "对视",   "双人面对面，目光交汇，约半臂距离"),
    ("hand_in",  "牵手",   "并肩，左右手十指交扣，重心略偏向彼此"),
    ("salute",   "行礼",   "宋明拱手礼，双手于胸前交合，身体微倾 15°"),
    ("fight",    "打斗",   "动态侧身横劈，重心后腿，前手出招，衣摆飞扬"),
    ("kneel",    "跪伏",   "单膝跪地，垂首，双手叉拳于胸前"),
    ("dash",     "急冲",   "前倾低身，发丝衣摆向后，速度线"),
]


@dataclass
class ActionEntry:
    key: str
    name_zh: str
    description: str
    prompt: str
    keypose_url: str | None = None
    driving_clip_url: str | None = None


@dataclass
class ActionSheet:
    char_id: str
    entries: list[ActionEntry] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "char_id": self.char_id,
            "entries": [
                {
                    "key": e.key,
                    "name_zh": e.name_zh,
                    "description": e.description,
                    "prompt": e.prompt,
                    "keypose_url": e.keypose_url,
                    "driving_clip_url": e.driving_clip_url,
                }
                for e in self.entries
            ],
        }


class ActionLibraryBuilder:
    def __init__(
        self,
        prompts_dir: str | pathlib.Path = "./prompts/characters",
        data_dir: str | pathlib.Path = "./data/characters",
        jimeng=None,
    ):
        self.prompts_dir = pathlib.Path(prompts_dir)
        self.data_dir = pathlib.Path(data_dir)
        self.jimeng = jimeng

    def build(self, char_id: str) -> ActionSheet:
        spec_path = self.prompts_dir / f"{char_id}.yaml"
        spec = (
            yaml.safe_load(spec_path.read_text(encoding="utf-8"))
            if spec_path.exists()
            else {}
        )
        base = spec.get("seedream_prompt_prefix", "")
        sheet = ActionSheet(char_id=char_id, entries=[])

        for key, zh, descr in ACTIONS:
            prompt = (
                f"{base}\n动作：{zh}（{descr}）\n"
                "镜头：全身或半身，9:16，前景人物 50% 画面占比；衣摆/发丝自然飘动；保持锁定符号。"
            )
            entry = ActionEntry(
                key=key,
                name_zh=zh,
                description=descr,
                prompt=prompt,
            )
            if self.jimeng is not None:
                try:
                    from .gen_jimeng import JimengRequest

                    urls = self.jimeng.generate(
                        JimengRequest(prompt=prompt, num_images=1, aspect_ratio="3:4")
                    )
                    entry.keypose_url = (urls or [None])[0]
                except Exception as e:
                    _log.warning("jimeng action gen failed: %s", e)
            sheet.entries.append(entry)

        out_dir = self.data_dir / char_id / "actions"
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "sheet.json").write_text(
            json.dumps(sheet.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return sheet


__all__ = ["ActionLibraryBuilder", "ActionSheet", "ActionEntry", "ACTIONS"]
