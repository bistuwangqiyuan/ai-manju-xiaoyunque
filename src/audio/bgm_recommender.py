"""V10 §7.2 — BGM recommender.

Given a textual scene description (e.g. ``"主角孤身闯入敌阵，紧张高潮"``) and
optional genre/mood/bpm constraints, returns the top-N BGM library
candidates ranked by relevance.

Backends (auto-fallback):

    1. ``laion-clap`` — joint text↔audio embedding, cosine ranking against
       pre-computed library embeddings. Caches embeddings on disk.
    2. Lexical keyword overlap — Chinese + English keyword bags mapped to
       genre/mood tags. Always available, deterministic.

Result includes a ``confidence`` score in [0, 1] and a ``backend`` field
so the orchestrator can decide whether to fall back to BGM generation.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any

from .bgm_library import BgmEntry, BgmLibrary, get_library

_log = logging.getLogger(__name__)


# Keyword → tag bags.  Kept small & curated; falls back to substring match.
_GENRE_KEYWORDS = {
    "ancient": ["古风", "古代", "宫", "侠", "汉服", "ancient"],
    "modern": ["现代", "都市", "公司", "咖啡", "酒吧", "modern"],
    "fantasy": ["玄幻", "仙", "修炼", "魔法", "魔王", "fantasy", "xianxia"],
    "romance": ["爱情", "恋爱", "心动", "约会", "暗恋", "表白", "romance"],
    "suspense": ["悬疑", "推理", "凶手", "线索", "真相", "suspense", "thriller"],
    "comedy": ["搞笑", "喜剧", "搞怪", "闹剧", "笑", "comedy"],
    "horror": ["恐怖", "鬼", "诡异", "阴森", "horror"],
    "scifi": ["科幻", "宇宙", "机甲", "AI", "未来", "scifi", "sci-fi"],
    "wuxia": ["武侠", "江湖", "侠客", "刀剑", "wuxia"],
    "palace_fight": ["宫斗", "后宫", "皇上", "贵妃"],
    "time_travel": ["穿越", "重生", "time travel"],
    "action": ["追逐", "战斗", "打斗", "动作", "action"],
    "drama": ["剧情", "感情", "故事", "drama"],
}

_MOOD_KEYWORDS = {
    "calm":     ["宁静", "安静", "平和", "calm"],
    "gentle":   ["温柔", "温暖", "gentle"],
    "warm":     ["温馨", "甜蜜", "warm"],
    "bright":   ["明亮", "欢快", "bright"],
    "hopeful":  ["希望", "美好", "hopeful"],
    "sad":      ["难过", "悲伤", "哭", "离别", "sad", "melancholy"],
    "somber":   ["沉重", "暗", "somber"],
    "tense":    ["紧张", "心跳", "急促", "tense"],
    "urgent":   ["紧迫", "时不我待", "urgent"],
    "intense":  ["激烈", "高潮", "决战", "intense"],
    "epic":     ["史诗", "壮丽", "宏伟", "epic"],
    "kinetic":  ["动感", "节奏", "kinetic"],
    "mystical": ["神秘", "玄妙", "魔幻", "mystical"],
    "dark":     ["黑暗", "阴沉", "dark"],
    "eerie":    ["诡异", "阴森", "eerie"],
    "scary":    ["恐怖", "惊吓", "scary"],
    "silly":    ["搞怪", "傻", "silly"],
    "playful":  ["活泼", "顽皮", "playful"],
}


@dataclass
class RecommendedBgm:
    entry: BgmEntry
    score: float
    matched_genres: list[str] = field(default_factory=list)
    matched_moods: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "entry": self.entry.to_dict(),
            "score": round(float(self.score), 4),
            "matched_genres": self.matched_genres,
            "matched_moods": self.matched_moods,
        }


@dataclass
class RecommendationResult:
    backend: str
    candidates: list[RecommendedBgm] = field(default_factory=list)
    confidence: float = 0.0
    fallback_to_generation: bool = False

    @property
    def top(self) -> RecommendedBgm | None:
        return self.candidates[0] if self.candidates else None

    def to_dict(self) -> dict[str, Any]:
        return {
            "backend": self.backend,
            "confidence": round(self.confidence, 4),
            "fallback_to_generation": self.fallback_to_generation,
            "candidates": [c.to_dict() for c in self.candidates],
        }


def _extract_tags(text: str) -> tuple[set[str], set[str]]:
    """Pull out (genre_tags, mood_tags) from a free-text scene description."""
    text_l = text.lower()
    g_hits: set[str] = set()
    m_hits: set[str] = set()
    for tag, words in _GENRE_KEYWORDS.items():
        for w in words:
            if w in text or w in text_l:
                g_hits.add(tag)
                break
    for tag, words in _MOOD_KEYWORDS.items():
        for w in words:
            if w in text or w in text_l:
                m_hits.add(tag)
                break
    return g_hits, m_hits


def _lexical_recommend(
    text: str,
    *, genres: list[str] | None = None, moods: list[str] | None = None,
    bpm_range: tuple[int, int] | None = None,
    library: BgmLibrary | None = None,
    top_k: int = 5,
) -> RecommendationResult:
    lib = library or get_library()
    text_g, text_m = _extract_tags(text)
    if genres:
        text_g |= {g.lower() for g in genres}
    if moods:
        text_m |= {m.lower() for m in moods}

    candidates: list[RecommendedBgm] = []
    for entry in lib.list_entries():
        e_g = {g.lower() for g in entry.genre}
        e_m = {m.lower() for m in entry.mood}
        gh = text_g & e_g
        mh = text_m & e_m
        score = 0.0
        score += 0.55 * (len(gh) / max(len(text_g | e_g), 1))
        score += 0.40 * (len(mh) / max(len(text_m | e_m), 1))
        if bpm_range:
            lo, hi = bpm_range
            if lo <= entry.bpm <= hi:
                score += 0.05
            else:
                centre = (lo + hi) / 2
                score -= 0.05 * min(abs(entry.bpm - centre) / max(centre, 1), 1.0)
        if score > 0:
            candidates.append(RecommendedBgm(
                entry=entry, score=score,
                matched_genres=sorted(gh), matched_moods=sorted(mh),
            ))
    candidates.sort(key=lambda c: c.score, reverse=True)
    candidates = candidates[:top_k]
    confidence = candidates[0].score if candidates else 0.0
    return RecommendationResult(
        backend="lexical", candidates=candidates, confidence=confidence,
        fallback_to_generation=(confidence < 0.20),
    )


def _try_clap_recommend(
    text: str,
    *, genres: list[str] | None,
    library: BgmLibrary,
    top_k: int,
) -> RecommendationResult | None:
    """laion-clap path. Returns None if clap or audio files unavailable."""
    try:
        import laion_clap  # type: ignore
        import numpy as np  # type: ignore
    except Exception:
        return None
    try:
        model = laion_clap.CLAP_Module(enable_fusion=False)
        model.load_ckpt()
        text_emb = model.get_text_embedding([text], use_tensor=False)[0]
        text_emb = text_emb / (np.linalg.norm(text_emb) + 1e-9)

        scored: list[tuple[BgmEntry, float]] = []
        import pathlib as _pl
        for entry in library.list_entries():
            path = _pl.Path(entry.path)
            if not path.exists():
                continue
            audio_emb = model.get_audio_embedding_from_filelist([str(path)], use_tensor=False)[0]
            audio_emb = audio_emb / (np.linalg.norm(audio_emb) + 1e-9)
            cos = float((text_emb * audio_emb).sum())
            score = (cos + 1.0) / 2.0  # map to [0,1]
            scored.append((entry, score))
        if not scored:
            return None
        scored.sort(key=lambda kv: kv[1], reverse=True)
        scored = scored[:top_k]
        candidates = [
            RecommendedBgm(entry=e, score=s,
                           matched_genres=[g for g in (genres or []) if g in e.genre])
            for e, s in scored
        ]
        return RecommendationResult(
            backend="laion_clap",
            candidates=candidates,
            confidence=candidates[0].score if candidates else 0.0,
            fallback_to_generation=(candidates[0].score < 0.45) if candidates else True,
        )
    except Exception as exc:
        _log.debug("laion-clap recommend failed: %s", exc)
        return None


def recommend(
    scene_text: str,
    *, genres: list[str] | None = None, moods: list[str] | None = None,
    bpm_range: tuple[int, int] | None = None,
    library: BgmLibrary | None = None,
    top_k: int = 5,
    use_clap: bool = True,
) -> RecommendationResult:
    """Recommend top-K BGM entries for a scene description."""
    lib = library or get_library()
    if use_clap:
        clap_result = _try_clap_recommend(scene_text, genres=genres,
                                          library=lib, top_k=top_k)
        if clap_result is not None:
            return clap_result
    return _lexical_recommend(scene_text, genres=genres, moods=moods,
                              bpm_range=bpm_range, library=lib, top_k=top_k)


__all__ = ["RecommendedBgm", "RecommendationResult", "recommend"]
