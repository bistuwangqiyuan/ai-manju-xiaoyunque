"""V10 §10.3 — Per-platform copy presets (tone × format × hashtag).

Generates a complete "ready-to-post" caption for each platform that goes
beyond the basic ``platform_export.PLATFORM_SPECS.caption_template``:

    - tone (active / cute / professional)
    - 3-line storytelling hook
    - hashtag block (≤8, deduped, capped to platform limits)
    - call-to-action variant
    - text length advisor (returns a warning if too long for the
       platform's caption box)

Backends:
    1. multi_provider_llm.llm_complete_with_fallback (true LLM copy)
    2. deterministic template (no external call required)
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any

_log = logging.getLogger(__name__)


PLATFORM_TONE = {
    "douyin":         {"tone": "energetic", "max_caption": 1000, "max_hashtags": 8},
    "kuaishou":       {"tone": "friendly_local", "max_caption": 800, "max_hashtags": 8},
    "wechat_video":   {"tone": "warm", "max_caption": 1000, "max_hashtags": 6},
    "xiaohongshu":    {"tone": "cute_share", "max_caption": 1000, "max_hashtags": 10},
    "bilibili":       {"tone": "fandom_explainer", "max_caption": 2000, "max_hashtags": 12},
    "youtube_shorts": {"tone": "english_concise", "max_caption": 200, "max_hashtags": 5},
}

_BASE_TEMPLATES = {
    "douyin": (
        "🎬{title} · 第 {episode} 集\n"
        "{hook}\n"
        "👉 关注主页追更完整剧情"
    ),
    "kuaishou": (
        "🌶️{title} 第 {episode} 集来了\n"
        "{hook}\n"
        "求一波双击 + 关注"
    ),
    "wechat_video": (
        "《{title}》第 {episode} 集\n{hook}\n点开看完整版"
    ),
    "xiaohongshu": (
        "宝子们看过来！《{title}》上头剧情第 {episode} 集来啦～\n"
        "{hook}\n"
        "💬 评论区告诉我你最喜欢的桥段"
    ),
    "bilibili": (
        "【AI 国漫】《{title}》第 {episode} 集\n"
        "本集看点：{hook}\n"
        "支持点击下方三连，剧情持续更新~"
    ),
    "youtube_shorts": (
        "{title} · Episode {episode}\n{hook}\n#Shorts #AIanime"
    ),
}

_HASHTAGS = {
    "douyin": ["AI漫剧", "短剧推荐", "古风漫剧", "国漫", "二创", "AIGC"],
    "kuaishou": ["AI漫剧", "古风", "国漫", "短剧", "甜宠"],
    "wechat_video": ["AI漫剧", "国漫"],
    "xiaohongshu": ["AI漫剧", "漫剧推荐", "甜宠", "古风", "动漫", "国创"],
    "bilibili": ["AI国漫", "国漫", "漫剧", "AIGC", "原创动画"],
    "youtube_shorts": ["AIanime", "shortdrama", "AIstory", "ai_animation", "shorts"],
}

_GENRE_TAGS = {
    "ancient":  ["古风", "古装", "宫斗"],
    "romance":  ["甜宠", "言情"],
    "modern":   ["都市", "现代"],
    "suspense": ["悬疑", "推理"],
    "comedy":   ["搞笑"],
    "horror":   ["惊悚"],
    "scifi":    ["科幻"],
    "wuxia":    ["武侠"],
    "fantasy":  ["玄幻", "仙侠"],
}


@dataclass
class PlatformCopy:
    platform: str
    tone: str
    caption: str
    hashtags: list[str] = field(default_factory=list)
    char_count: int = 0
    too_long: bool = False
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "platform": self.platform, "tone": self.tone,
            "caption": self.caption, "hashtags": list(self.hashtags),
            "char_count": self.char_count, "too_long": self.too_long,
            "warnings": list(self.warnings),
        }


def _llm_copy(platform: str, *, title: str, episode: int | str,
              hook: str, genre: str, tone: str,
              max_caption: int) -> str | None:
    try:
        from ..common.multi_provider_llm import llm_complete_with_fallback
    except Exception:
        return None
    prompt = (
        f"为平台「{platform}」写一段短剧推广文案。\n"
        f"剧名：{title}，集数：{episode}，题材：{genre}，调性：{tone}。\n"
        f"必须包含 3 行：抓眼球开头、剧情钩子、行动召唤。\n"
        f"中文（YouTube 用英文），字数 ≤ {max_caption // 4}，不要 hashtags。\n"
        f"剧情钩子：{hook}"
    )
    try:
        text, _meta = llm_complete_with_fallback(
            prompt=prompt, max_tokens=400, temperature=0.7,
        )
        return text.strip() if text else None
    except Exception:
        return None


def generate_copy(
    platforms: list[str],
    *, title: str, episode: int | str = 1,
    hook: str = "",
    genre: str = "modern",
    use_llm: bool = False,
) -> dict[str, PlatformCopy]:
    """Generate per-platform caption + hashtags."""
    out: dict[str, PlatformCopy] = {}
    genre_hashtags = _GENRE_TAGS.get(genre, [])

    for pid in platforms:
        tone_info = PLATFORM_TONE.get(pid, {"tone": "neutral",
                                            "max_caption": 1000,
                                            "max_hashtags": 8})
        tone = tone_info["tone"]
        max_caption = int(tone_info["max_caption"])
        max_hashtags = int(tone_info["max_hashtags"])

        text: str | None = None
        if use_llm:
            text = _llm_copy(pid, title=title, episode=episode,
                             hook=hook, genre=genre, tone=tone,
                             max_caption=max_caption)
        if not text:
            tmpl = _BASE_TEMPLATES.get(pid, "{title} · Episode {episode}\n{hook}")
            text = tmpl.format(
                title=title, episode=episode,
                hook=(hook or "这一集会有反转").strip(),
            )

        # Hashtags
        base_tags = list(_HASHTAGS.get(pid, []))
        merged = []
        for t in (genre_hashtags + base_tags):
            if t not in merged:
                merged.append(t)
        hashtags = [f"#{t}" for t in merged[:max_hashtags]]

        # Caption length
        char_count = len(text)
        too_long = char_count > max_caption
        warnings: list[str] = []
        if too_long:
            warnings.append(
                f"caption length {char_count} > platform max {max_caption}"
            )

        # Add hashtags after caption for platforms where in-line is convention
        if pid in ("xiaohongshu", "douyin", "kuaishou"):
            caption_with_tags = text + "\n" + " ".join(hashtags)
        elif pid == "bilibili":
            caption_with_tags = text  # B 站习惯把标签放在标题区
        else:
            caption_with_tags = text + "\n" + " ".join(hashtags)

        out[pid] = PlatformCopy(
            platform=pid, tone=tone, caption=caption_with_tags,
            hashtags=hashtags, char_count=len(caption_with_tags),
            too_long=len(caption_with_tags) > max_caption,
            warnings=warnings,
        )
    return out


def shorten_caption(caption: str, max_chars: int) -> str:
    """Trim a caption to ``max_chars`` while preserving hashtag lines."""
    if len(caption) <= max_chars:
        return caption
    parts = caption.split("\n")
    if len(parts) > 1:
        # try removing middle lines first
        head, tail = parts[0], parts[-1]
        remaining = max_chars - len(head) - len(tail) - 2
        if remaining > 0:
            return f"{head}…\n{tail}"
    return caption[: max_chars - 1] + "…"


__all__ = [
    "PLATFORM_TONE", "PlatformCopy",
    "generate_copy", "shorten_caption",
]
