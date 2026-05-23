"""Bilingual subtitle translator.

Requirement doc 多语言: 一键将中文字幕翻译为目标语言并叠加生成 bilingual ASS。

Backend priority:
    1. Gemini 2.5 Pro (1M context, cheap, strong multilingual)
    2. Anthropic Claude (high-quality fallback)
    3. mock (passthrough)
"""
from __future__ import annotations

import json
import logging
import os
import re
import urllib.request

from .ass_subtitle import AssLine

_log = logging.getLogger(__name__)


LANG_NAMES = {
    "en": "English",
    "ja": "Japanese",
    "ko": "Korean",
    "es": "Spanish",
    "fr": "French",
    "de": "German",
    "zh": "Chinese (Simplified)",
}


def translate_lines(
    lines: list[AssLine],
    *,
    target_lang: str = "en",
    bilingual: bool = True,
) -> list[AssLine]:
    """Return a new ``AssLine`` list with translated text on each entry.

    If ``bilingual=True`` the returned text is ``"original\\Ntranslation"`` so the
    burn-in keeps the original Chinese above the new translation.
    """
    if not lines:
        return lines
    target_name = LANG_NAMES.get(target_lang, target_lang)
    texts = [ln.text for ln in lines]

    translations: list[str]
    if os.environ.get("GEMINI_API_KEY") and os.environ.get("FORCE_MOCK_TRANSLATE") != "1":
        try:
            translations = _via_gemini(texts, target_name)
        except Exception as e:
            _log.warning("gemini translate failed: %s; falling back", e)
            translations = _heuristic(texts, target_lang)
    elif os.environ.get("ANTHROPIC_API_KEY") and os.environ.get("FORCE_MOCK_TRANSLATE") != "1":
        try:
            translations = _via_anthropic(texts, target_name)
        except Exception as e:
            _log.warning("anthropic translate failed: %s; falling back", e)
            translations = _heuristic(texts, target_lang)
    else:
        translations = _heuristic(texts, target_lang)

    out: list[AssLine] = []
    for ln, tr in zip(lines, translations):
        if bilingual:
            text = f"{ln.text}\\N{tr}"
        else:
            text = tr
        out.append(AssLine(start_seconds=ln.start_seconds, end_seconds=ln.end_seconds, text=text, style=ln.style))
    return out


def _heuristic(texts: list[str], target_lang: str) -> list[str]:
    return [f"[{target_lang}] {t}" for t in texts]


def _via_gemini(texts: list[str], target_name: str) -> list[str]:
    key = os.environ["GEMINI_API_KEY"]
    model = os.environ.get("GEMINI_MODEL", "gemini-2.5-pro")
    endpoint = (
        f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"
    )
    sep = "<<<SEP>>>"
    prompt = (
        f"Translate the following Chinese subtitle lines into {target_name}. "
        f"Keep each line concise (≤ 1 line). Separate translations with '{sep}'. "
        "Do not output anything else.\n\n"
        + sep.join(texts)
    )
    body = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.3, "maxOutputTokens": 4000},
    }
    req = urllib.request.Request(
        endpoint,
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        data = json.loads(resp.read())
    parts = data["candidates"][0]["content"]["parts"]
    raw = "".join(p.get("text", "") for p in parts)
    parts_out = raw.split(sep)
    if len(parts_out) != len(texts):
        # fall back if model failed to keep separator structure
        return _heuristic(texts, "en")
    return [p.strip() for p in parts_out]


def _via_anthropic(texts: list[str], target_name: str) -> list[str]:
    key = os.environ["ANTHROPIC_API_KEY"]
    sep = "<<<SEP>>>"
    system = f"Translate Chinese subtitles into {target_name}. One line per input. Separator: {sep}. Only output translations."
    body = {
        "model": os.environ.get("ANTHROPIC_MODEL", "claude-opus-4-7-20260413"),
        "max_tokens": 4000,
        "temperature": 0.2,
        "system": system,
        "messages": [{"role": "user", "content": sep.join(texts)}],
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
    with urllib.request.urlopen(req, timeout=120) as resp:
        data = json.loads(resp.read())
    raw = "\n".join(b.get("text", "") for b in data.get("content", []) if b.get("type") == "text")
    parts_out = raw.split(sep)
    if len(parts_out) != len(texts):
        return _heuristic(texts, "en")
    return [p.strip() for p in parts_out]


__all__ = ["translate_lines", "LANG_NAMES"]
