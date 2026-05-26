"""V10 §3.2 — Dialogue polishing + emotion tagging.

Given a list of raw dialogue lines we return punched-up versions with
inferred emotion tags (used downstream by TTS to pick prosody) and per-line
duration estimates for the subtitle timeline.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass


@dataclass
class PolishedLine:
    speaker: str
    original: str
    polished: str
    emotion: str
    intensity: int       # 1..5
    direction: str | None = None
    estimated_seconds: float = 0.0


# Emotion classification — used as a fallback when the LLM is offline
_EMOTION_MAP = [
    (r"(哈哈|笑|乐|喜)", ("joyful", 4)),
    (r"(哭|泪|呜)",      ("sad", 4)),
    (r"(怒|气|滚|混蛋)", ("angry", 5)),
    (r"(怕|抖|寒)",      ("fearful", 3)),
    (r"(爱|想你|依恋)",  ("loving", 4)),
    (r"(冷|哼)",         ("cold", 3)),
    (r"(\?|？)",         ("questioning", 2)),
    (r"(！|!)",          ("emphatic", 3)),
]


_SYSTEM_PROMPT = (
    "你是台词润色师。对每句台词做：1) 口语化润色不超过 20% 字数 2) 标注 emotion "
    "(joyful/sad/angry/fearful/loving/cold/questioning/emphatic/neutral) 3) intensity 1-5 "
    "4) 添加可选 direction (动作或语气提示)。严格 JSON 返回 [{speaker, original, polished, "
    "emotion, intensity, direction}]。"
)


def polish_dialogue(
    lines: list[dict],
    *,
    speaking_speed_cps: float = 5.5,
    timeout_s: float = 60.0,
) -> list[PolishedLine]:
    """``lines`` is a list of ``{"speaker", "line"}`` dicts."""
    if not lines:
        return []
    try:
        from src.common.multi_provider_llm import llm_complete_with_fallback
        text, _ = llm_complete_with_fallback(
            system=_SYSTEM_PROMPT,
            user=json.dumps(lines, ensure_ascii=False),
            json_mode=True,
            max_tokens=8000,
        )
    except Exception:
        text = None

    polished: list[PolishedLine] = []
    if text:
        try:
            data = json.loads(_extract_json(text))
            for item in data:
                polished.append(_to_polished(item, speaking_speed_cps))
        except Exception:
            polished = []
    if not polished:
        polished = [_fallback_polish(d, speaking_speed_cps) for d in lines]
    return polished


# ---------------------------------------------------------------------------
def _to_polished(item: dict, cps: float) -> PolishedLine:
    polished_text = (item.get("polished") or item.get("line") or "").strip()
    speaker = item.get("speaker") or "旁白"
    emotion = item.get("emotion") or _detect_emotion(polished_text)[0]
    intensity = int(item.get("intensity") or _detect_emotion(polished_text)[1])
    return PolishedLine(
        speaker=speaker,
        original=item.get("original") or polished_text,
        polished=polished_text,
        emotion=emotion,
        intensity=max(1, min(5, intensity)),
        direction=item.get("direction"),
        estimated_seconds=round(_estimate_duration(polished_text, cps), 2),
    )


def _fallback_polish(item: dict, cps: float) -> PolishedLine:
    speaker = item.get("speaker") or "旁白"
    raw = item.get("line", "").strip()
    polished = _light_polish(raw)
    emo, intensity = _detect_emotion(polished)
    return PolishedLine(
        speaker=speaker, original=raw, polished=polished,
        emotion=emo, intensity=intensity,
        direction=None,
        estimated_seconds=round(_estimate_duration(polished, cps), 2),
    )


def _light_polish(text: str) -> str:
    # collapse weird whitespace + strip stage directions in 【】
    text = re.sub(r"\s+", "", text)
    text = re.sub(r"【[^】]*】", "", text)
    return text or "（无台词）"


def _detect_emotion(text: str) -> tuple[str, int]:
    for pat, (emo, intensity) in _EMOTION_MAP:
        if re.search(pat, text):
            return emo, intensity
    return "neutral", 2


def _estimate_duration(text: str, cps: float) -> float:
    # Chinese characters @ cps + minimum 0.6s; ASCII words count as 0.7 char
    chinese = sum(1 for c in text if "\u4e00" <= c <= "\u9fff")
    ascii_w = len(re.findall(r"[A-Za-z]+", text))
    effective = chinese + ascii_w * 1.2
    return max(0.6, effective / max(cps, 0.1))


def _extract_json(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\n?", "", text)
        text = text.rstrip("`").rstrip()
    s = text.find("[")
    e = text.rfind("]")
    if s == -1 or e == -1 or e < s:
        return text
    return text[s:e + 1]


__all__ = ["PolishedLine", "polish_dialogue"]
