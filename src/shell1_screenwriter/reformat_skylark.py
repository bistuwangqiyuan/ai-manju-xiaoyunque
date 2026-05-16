"""Doubao Seed 1.6 Thinking — reformat episode JSON into Skylark-friendly prompt.

The Skylark Agent 2.0 archive system is unreliable across episodes. The
canonical workaround (cf. tech.md §3) is to repeat the full 「人物设定块 +
场景设定块」 at the head of every episode prompt. This formatter generates
those blocks deterministically from the canonical YAML character + scene
locks, and concatenates them with the shot-level breakdown.
"""
from __future__ import annotations

import json
import logging
import os
import pathlib
from typing import Iterable, Mapping

import urllib.request

import yaml

from .write_episodes import Episode


_log = logging.getLogger(__name__)


# Style anchor + character + scene YAMLs live under prompts/
_REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
_PROMPTS_DIR = _REPO_ROOT / "prompts"


def _load_yaml(path: pathlib.Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _render_character_block(char: Mapping) -> str:
    lines = [f"- {char['name_zh']}（UID #{char['id']}）"]
    fields = [
        ("age", "年龄"), ("height_cm", "身高"), ("body", "体型"),
        ("hair", "发型"), ("eye", "眼神"), ("attire", "服装"),
        ("accessories", "佩饰"), ("weapon", "持物"),
        ("signature_marks", "锁定符号"), ("voice", "音色"),
    ]
    for key, label in fields:
        if char.get(key):
            value = char[key] if isinstance(char[key], str) else "; ".join(char[key])
            lines.append(f"  · {label}：{value}")
    return "\n".join(lines)


def _render_scene_block(scene: Mapping) -> str:
    lines = [f"- {scene['name_zh']}（loc_id {scene['id']}）"]
    if scene.get("palette"):
        lines.append(f"  · 整体色调：{scene['palette']}")
    if scene.get("description"):
        lines.append(f"  · 描述：{scene['description']}")
    if scene.get("lighting"):
        lines.append(f"  · 灯光：{scene['lighting']}")
    return "\n".join(lines)


_PROMPT_TEMPLATE = """【画风设定（全集生效）】
{style_block}

【人物设定（必填，全集生效）】
{character_block}

【场景设定】
{scene_block}

【三大原创锁定符号（每镜必须保持）】
- 聂小倩眉间一点朱砂痣（圆点直径约 3mm，颜色 #C5283D）
- 聂小倩左肩黑色藤纹束缚标记（visibility {black_vine_vis}）
- 革囊中伸出的苍白剑客之手（{white_hand}）

【第 {ep_num} 集分镜】
标题：{title}
时长：{duration}s   节拍：钩子-铺垫-高潮-反转-悬念
{shot_block}

【字幕规范】不要由 AI 渲染字幕，画面中禁止出现任何文字。
"""


_SYSTEM_PROMPT = """你是漫剧渲染 prompt 工程师，正在为小云雀 Agent 2.0「有参考」接口重写剧本。

规则：
1. 保留每个镜头的 shot_id / duration / camera_motion / action_desc。
2. 把对白、旁白、音效合并到 action_desc 之后用「| 对白 | 旁白 | 音效」标签隔开。
3. 删除所有"画面中文字"指令——字幕由本地 ASS 渲染。
4. 在 action_desc 里强化「眉间朱砂痣」「左肩黑藤」「革囊苍白手」三大锁定符号的镜头可见性。
5. 输出 JSON，键为 shot_block，值为完整的多行字符串。"""


class SkylarkFormatter:
    """Render Skylark-friendly episode prompts."""

    def __init__(self,
                 api_key: str | None = None,
                 base_url: str = "https://ark.cn-beijing.volces.com/api/v3",
                 model: str = "doubao-seed-1-6-thinking-250615",
                 prompts_dir: pathlib.Path = _PROMPTS_DIR):
        self.api_key = api_key or os.environ.get("DOUBAO_API_KEY") or os.environ.get("VOLC_ARK_API_KEY", "")
        if not self.api_key:
            raise RuntimeError("Missing DOUBAO_API_KEY / VOLC_ARK_API_KEY")
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.prompts_dir = prompts_dir
        self._style = _load_yaml(prompts_dir / "style" / "ancient_3d_guoman.yaml")
        self._characters = {
            p.stem: _load_yaml(p)
            for p in (prompts_dir / "characters").glob("*.yaml")
        }
        self._scenes = {
            p.stem: _load_yaml(p)
            for p in (prompts_dir / "scenes").glob("*.yaml")
        }

    def format_episode(self, episode: Episode) -> str:
        raw = episode.raw
        ep_num = int(raw["episode_id"].lstrip("ep"))

        char_block = "\n".join(
            _render_character_block(self._characters[cid])
            for cid in raw.get("characters_in_episode", [])
            if cid in self._characters
        )
        scene_block = "\n".join(
            _render_scene_block(self._scenes[sid])
            for sid in raw.get("scenes_in_episode", [])
            if sid in self._scenes
        )

        signatures = raw.get("signatures_check", {}) or {}
        shot_block = self._rewrite_shots(raw.get("shots", []))

        return _PROMPT_TEMPLATE.format(
            style_block=self._style.get("prompt_lock", ""),
            character_block=char_block,
            scene_block=scene_block,
            black_vine_vis=signatures.get("black_vine_visibility", 0.0),
            white_hand="本集出现" if signatures.get("white_hand_appears") else "本集不出现",
            ep_num=ep_num,
            title=raw["title"],
            duration=raw["duration_seconds"],
            shot_block=shot_block,
        )

    # ------------------------------------------------------------------

    def _rewrite_shots(self, shots: Iterable[dict]) -> str:
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": json.dumps(list(shots), ensure_ascii=False)},
            ],
            "temperature": 0.4,
            "response_format": {"type": "json_object"},
            "max_tokens": 8000,
        }
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(
            f"{self.base_url}/chat/completions",
            data=body,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=180) as resp:
            raw = json.loads(resp.read())
        content = raw["choices"][0]["message"]["content"]
        parsed = json.loads(content)
        return parsed.get("shot_block", "")
