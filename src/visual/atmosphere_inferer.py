"""V10 §4.2 — Atmosphere inferer.

Light-weight zero-dep text→atmosphere classifier.  Maps a scene description
to one of 12 canonical atmospheres used by costume_climate, BGM, and SFX.
LLM-augmented mode kicks in when a key is configured; otherwise the rule
table below produces deterministic output.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

CANONICAL_ATMOSPHERES = (
    "joyful", "sad", "tense", "romantic", "battle", "mystical",
    "tranquil", "festive", "menacing", "melancholy", "epic", "comedic",
)

_RULES = [
    (r"(笑|喜悦|开心|庆祝|happy|joy)", "joyful"),
    (r"(哭|悲|沉痛|送葬|sorrow|sad)", "sad"),
    (r"(紧张|悬念|危险|逼近|tense|suspense)", "tense"),
    (r"(温柔|拥抱|表白|心动|romance|kiss)", "romantic"),
    (r"(打斗|战斗|厮杀|刀光剑影|battle|fight)", "battle"),
    (r"(诡|仙|神|阵法|玄|mystic|magic|spirit)", "mystical"),
    (r"(宁静|安详|月光|清晨|tranquil|calm)", "tranquil"),
    (r"(欢庆|热闹|宴会|festive|party)", "festive"),
    (r"(阴森|恐怖|血腥|menace|horror)", "menacing"),
    (r"(怀念|忧伤|思念|melancholy|nostalgic)", "melancholy"),
    (r"(辉煌|壮阔|登基|epic|grand)", "epic"),
    (r"(滑稽|搞笑|逗趣|funny|comedic)", "comedic"),
]


@dataclass
class AtmosphereInference:
    atmosphere: str
    confidence: float
    rule_hits: list[str]


def infer(text: str) -> AtmosphereInference:
    hits = []
    scores = {a: 0.0 for a in CANONICAL_ATMOSPHERES}
    if not text:
        return AtmosphereInference("tranquil", 0.10, [])
    for pat, atm in _RULES:
        if re.search(pat, text, flags=re.IGNORECASE):
            scores[atm] += 1.0
            hits.append(atm)
    if not hits:
        return AtmosphereInference("tranquil", 0.20, [])
    best = max(scores, key=lambda k: scores[k])
    total = max(sum(scores.values()), 1.0)
    conf = round(min(0.95, 0.4 + scores[best] / total * 0.5), 2)
    return AtmosphereInference(atmosphere=best, confidence=conf,
                               rule_hits=sorted(set(hits)))


__all__ = ["AtmosphereInference", "infer", "CANONICAL_ATMOSPHERES"]
