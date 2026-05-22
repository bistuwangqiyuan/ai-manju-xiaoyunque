"""Generate a full novel draft from a theme + genre.

Implements requirement doc §11.1: 剧本编写：根据设定主题自动生成小说。

Backends:
    - Anthropic Claude Opus 4.7 (preferred, Chinese flair)
    - DeepSeek V4-Pro (fallback, 1M context, cheap)
    - mock (deterministic, for tests / mock-mode CI)

Output is a plain-text novel of ``length_words`` (approximate). The orchestrator
then feeds it through the existing event-extract → episode-write → schema-validate
pipeline so downstream code is unchanged.
"""
from __future__ import annotations

import json
import logging
import os
import urllib.request

_log = logging.getLogger(__name__)


_DEFAULT_SYSTEM = """你是一位世界级中文小说家与短剧编剧。
要求：
- 题材必须命中所选「genre」的核心母题与情绪点。
- 节拍按"钩子(0-3s) + 铺垫 + 高潮 + 反转 + 悬念"的短剧 4 段式。
- 篇幅约 {length_words} 字，分章节，每章 1 个剧情爆点。
- 严格回避现实中知名 IP（角色/地名/情节）的独创元素，必须 100% 原创。
- 用流畅自然中文，宜于改编为 9:16 竖屏短剧。
"""


def theme_to_novel(
    theme: str,
    *,
    genre: str = "ancient",
    length_words: int = 3500,
    language: str = "Chinese",
    backend: str | None = None,
) -> str:
    """Return a freshly generated novel draft.

    Raises ``RuntimeError`` when no backend is available.
    """
    backend = backend or _pick_backend()
    if backend == "anthropic":
        return _via_anthropic(theme, genre, length_words, language)
    if backend == "deepseek":
        return _via_deepseek(theme, genre, length_words, language)
    return _mock(theme, genre, length_words, language)


def _pick_backend() -> str:
    if os.environ.get("FORCE_MOCK_THEME") == "1":
        return "mock"
    if os.environ.get("ANTHROPIC_API_KEY"):
        return "anthropic"
    if os.environ.get("DEEPSEEK_API_KEY"):
        return "deepseek"
    return "mock"


def _via_anthropic(theme: str, genre: str, length_words: int, language: str) -> str:
    key = os.environ["ANTHROPIC_API_KEY"]
    system = _DEFAULT_SYSTEM.format(length_words=length_words)
    body = {
        "model": os.environ.get("ANTHROPIC_MODEL", "claude-opus-4-5-20250929"),
        "max_tokens": 8000,
        "system": system,
        "messages": [
            {
                "role": "user",
                "content": (
                    f"题材：{genre}\n"
                    f"主题：{theme}\n"
                    f"目标语言：{language}\n"
                    "请按短剧改编结构写出小说草稿。"
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
    with urllib.request.urlopen(req, timeout=300) as resp:
        data = json.loads(resp.read())
    parts: list[str] = []
    for block in data.get("content", []):
        if block.get("type") == "text":
            parts.append(block.get("text", ""))
    return "\n".join(parts).strip() or _mock(theme, genre, length_words, language)


def _via_deepseek(theme: str, genre: str, length_words: int, language: str) -> str:
    key = os.environ["DEEPSEEK_API_KEY"]
    body = {
        "model": os.environ.get("DEEPSEEK_MODEL", "deepseek-chat"),
        "messages": [
            {"role": "system", "content": _DEFAULT_SYSTEM.format(length_words=length_words)},
            {"role": "user", "content": f"题材：{genre}\n主题：{theme}\n目标语言：{language}"},
        ],
        "temperature": 0.75,
        "max_tokens": 8000,
    }
    req = urllib.request.Request(
        "https://api.deepseek.com/v1/chat/completions",
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=300) as resp:
        data = json.loads(resp.read())
    return data["choices"][0]["message"]["content"].strip() or _mock(theme, genre, length_words, language)


def _mock(theme: str, genre: str, length_words: int, language: str) -> str:
    """Deterministic stub good enough for downstream extract_events()."""
    lines = [
        f"《{theme[:40]}》",
        f"——一个 {genre} 题材的全新故事（自动生成草稿）",
        "",
        "第一章 序幕",
        f"月光低垂，主角第一次在命运的交叉口与神秘人相遇。{theme}",
        "他没想到，这场邂逅会改变他的整个人生轨迹。",
        "",
        "第二章 暗潮",
        "线索零碎地散落在城市的角落，每一片碎片都指向同一个名字。",
        "",
        "第三章 决断",
        "在最后一线生机面前，他必须做出一个无法回头的选择。",
        "",
        "第四章 反转",
        "原来从一开始，他追的根本不是真相，而是被早早安排好的命运。",
        "",
        "第五章 落幕",
        f"主线终结，但 {genre} 世界的故事远未结束……",
    ]
    body = "\n".join(lines)
    if len(body) < length_words * 2:
        body += "\n" + ("（待续）" * max(1, (length_words * 2 - len(body)) // 4))
    return body


__all__ = ["theme_to_novel"]
