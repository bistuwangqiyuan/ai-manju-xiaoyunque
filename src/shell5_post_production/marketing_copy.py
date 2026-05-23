"""Marketing copy generator.

Requirement doc §8 文案配套:
    根据每集自动生成短视频文案、标题、引流文案、5 个 #hashtag。
"""
from __future__ import annotations

import json
import logging
import os
import re
import urllib.request

_log = logging.getLogger(__name__)


GENRE_HASHTAGS = {
    "ancient":  ["古风", "国漫", "聊斋", "仙侠", "AI漫剧"],
    "modern":   ["都市", "甜宠", "霸总", "短剧", "AI漫剧"],
    "sweet_pet": ["甜宠", "校园", "撒糖", "恋爱", "AI漫剧"],
    "suspense": ["悬疑", "推理", "短剧", "反转", "AI漫剧"],
    "xuanhuan": ["玄幻", "修仙", "国漫", "热血", "AI漫剧"],
}


def generate_marketing_copy(
    *,
    title: str,
    synopsis: str,
    genre: str = "ancient",
    language: str = "Chinese",
) -> dict:
    """Return ``{title, summary, hook_copy, hashtags, language}``."""

    if os.environ.get("ANTHROPIC_API_KEY") and os.environ.get("FORCE_MOCK_MARKETING") != "1":
        try:
            return _via_anthropic(title, synopsis, genre, language)
        except Exception as e:
            _log.warning("anthropic marketing copy failed: %s; falling back", e)
    return _heuristic(title, synopsis, genre, language)


def _heuristic(title: str, synopsis: str, genre: str, language: str) -> dict:
    seed = synopsis.strip()[:120] or title
    hooks = [
        f"⚡ {title}：第 3 秒就停不下来",
        f"🔥 你以为是看个 AI 漫剧？{title} 直接给我看哭了",
        f"📺 一口气追完《{title}》，{genre} 题材天花板",
        f"💔 整个朋友圈都在催更《{title}》",
    ]
    summary = (seed[:80] + "…") if len(seed) > 80 else seed
    tags = GENRE_HASHTAGS.get(genre, ["AI漫剧", "短剧", "国漫"])[:5]
    return {
        "title": title,
        "summary": summary,
        "hook_copy": hooks[hash(title) % len(hooks)],
        "hashtags": [f"#{t}" for t in tags],
        "language": language,
    }


def _via_anthropic(title: str, synopsis: str, genre: str, language: str) -> dict:
    key = os.environ["ANTHROPIC_API_KEY"]
    system = (
        "你是短视频流量营销专家。基于剧情简介，返回严格 JSON：\n"
        "{\"title\": str, \"summary\": str (<=80 字), \"hook_copy\": str (<=40 字的引流文案), "
        "\"hashtags\": [str] (5 个中文 hashtag，需 # 开头)}\n"
        "风格：钩子前置，制造好奇，避免敏感词"
    )
    body = {
        "model": os.environ.get("ANTHROPIC_MODEL", "claude-opus-4-7-20260413"),
        "max_tokens": 600,
        "temperature": 0.7,
        "system": system,
        "messages": [
            {
                "role": "user",
                "content": (
                    f"标题：{title}\n题材：{genre}\n语言：{language}\n"
                    f"剧情：{synopsis[:1500]}\n请输出 JSON。"
                ),
            }
        ],
    }
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "x-api-key": key,
            "anthropic-version": "2023-06-01",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = json.loads(resp.read())
    raw = "\n".join(b.get("text", "") for b in data.get("content", []) if b.get("type") == "text")
    parsed = _parse_json_safely(raw) or {}
    return {
        "title": parsed.get("title", title),
        "summary": parsed.get("summary", "")[:120],
        "hook_copy": parsed.get("hook_copy", ""),
        "hashtags": list(parsed.get("hashtags", []))[:5],
        "language": language,
    }


def _parse_json_safely(raw: str) -> dict:
    raw = raw.strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```[a-zA-Z]*\n?", "", raw)
        raw = re.sub(r"\n?```$", "", raw)
    try:
        return json.loads(raw)
    except Exception:
        m = re.search(r"\{.*\}", raw, re.DOTALL)
        if m:
            try:
                return json.loads(m.group(0))
            except Exception:
                pass
    return {}


__all__ = ["generate_marketing_copy"]
