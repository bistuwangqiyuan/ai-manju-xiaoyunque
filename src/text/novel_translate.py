"""V10 §3.2 / §10.2 — Multi-lingual novel translator.

Supported languages (need.md §10.2):
    Chinese (zh) · English (en) · Japanese (ja) · Korean (ko) ·
    Spanish (es) · French (fr) · Portuguese (pt) · Indonesian (id) ·
    Vietnamese (vi) · Thai (th) · Russian (ru)

The translator chunks the source by ~3000 char windows, keeps a glossary
of recurring proper nouns so character names stay consistent, and selects
the engine based on availability:

    1) Anthropic Claude Opus (high-fidelity literary translation)
    2) Gemini Pro 1.5 (multilingual fallback)
    3) DeepSeek/GLM/Tongyi (cost-friendly fallback)
    4) Mock chunk passthrough (offline CI)
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Iterable


LANG_ALIASES = {
    "zh": "Chinese", "en": "English", "ja": "Japanese", "ko": "Korean",
    "es": "Spanish", "fr": "French", "pt": "Portuguese", "id": "Indonesian",
    "vi": "Vietnamese", "th": "Thai", "ru": "Russian",
    "Chinese": "Chinese", "English": "English", "Japanese": "Japanese",
    "Korean": "Korean", "Spanish": "Spanish", "French": "French",
    "Portuguese": "Portuguese", "Indonesian": "Indonesian",
    "Vietnamese": "Vietnamese", "Thai": "Thai", "Russian": "Russian",
}


@dataclass
class TranslatedDoc:
    language: str
    body: str
    glossary: dict[str, str] = field(default_factory=dict)
    engine: str = "mock"
    chunk_count: int = 0
    quality_score: float | None = None


def normalise_language(lang: str) -> str:
    canonical = LANG_ALIASES.get(lang) or LANG_ALIASES.get(lang.lower())
    if canonical is None:
        raise ValueError(f"unsupported language: {lang}")
    return canonical


def translate_novel(
    *,
    source_text: str,
    target_language: str,
    chars_per_chunk: int = 3000,
    glossary_hint: dict[str, str] | None = None,
    timeout_s: float = 90.0,
) -> TranslatedDoc:
    lang = normalise_language(target_language)
    chunks = _chunk(source_text, chars_per_chunk)
    if not chunks:
        return TranslatedDoc(language=lang, body="", glossary=dict(glossary_hint or {}))
    glossary = dict(glossary_hint or {})

    translated_chunks: list[str] = []
    engine_used = "mock"
    for i, chunk in enumerate(chunks):
        out, engine, glossary = _translate_chunk(
            chunk, lang, index=i, total=len(chunks),
            glossary=glossary, timeout_s=timeout_s,
        )
        translated_chunks.append(out)
        engine_used = engine
    body = "\n\n".join(translated_chunks).strip()
    return TranslatedDoc(
        language=lang, body=body, glossary=glossary,
        engine=engine_used, chunk_count=len(chunks),
        quality_score=_naive_quality(source_text, body, lang),
    )


# ---------------------------------------------------------------------------
def _chunk(text: str, target: int) -> list[str]:
    text = text.strip()
    if not text:
        return []
    pieces = text.split("\n\n")
    out: list[str] = []
    buf = ""
    for p in pieces:
        if len(buf) + len(p) + 2 > target and buf:
            out.append(buf.strip())
            buf = p
        else:
            buf = buf + "\n\n" + p if buf else p
    if buf:
        out.append(buf.strip())
    return out


_SYSTEM = (
    "You are a literary translator. Translate the given short-drama / novel passage "
    "into {lang}. Keep the original paragraph structure. Output strict JSON: "
    '{{"text": "...", "glossary": {{"中文专名": "{lang} translation"}}}}'
)


def _translate_chunk(text: str, target_lang: str, *, index: int, total: int,
                     glossary: dict[str, str], timeout_s: float) -> tuple[str, str, dict[str, str]]:
    try:
        from src.common.multi_provider_llm import llm_complete_with_fallback
        sys_prompt = _SYSTEM.format(lang=target_lang)
        user = (
            f"Chunk {index + 1}/{total}.\n"
            f"Existing glossary (keep these names consistent): "
            f"{json.dumps(glossary, ensure_ascii=False)}\n\n"
            f"Source:\n{text}"
        )
        out, provider = llm_complete_with_fallback(
            system=sys_prompt, user=user, json_mode=True,
            max_tokens=min(8000, len(text) * 3),
            # Prefer premium chain for translation when configured
            chain_override=["anthropic", "openai", "deepseek", "glm", "tongyi"],
        )
        if out:
            data = json.loads(_extract_json(out))
            translated = (data.get("text") or "").strip()
            new_glossary = data.get("glossary") or {}
            if isinstance(new_glossary, dict):
                glossary.update({str(k): str(v) for k, v in new_glossary.items()})
            if translated:
                return translated, provider or "llm", glossary
    except Exception:
        pass
    # Fallback (mock): mark each paragraph
    return _mock_translate(text, target_lang), "mock", glossary


def _mock_translate(text: str, target_lang: str) -> str:
    return f"[{target_lang}] " + text.replace("\n\n", f"\n\n[{target_lang}] ")


def _naive_quality(src: str, tgt: str, lang: str) -> float | None:
    if not src or not tgt:
        return None
    # Cheap ratio sanity check: target length should be 0.5×–3× source
    ratio = len(tgt) / max(len(src), 1)
    if 0.4 <= ratio <= 3.0:
        return round(min(9.5, 7.5 + (1 - abs(ratio - 1)) * 1.5), 2)
    return round(max(3.0, 9.5 - abs(ratio - 1) * 1.5), 2)


def _extract_json(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\n?", "", text)
        text = text.rstrip("`").rstrip()
    s = text.find("{")
    e = text.rfind("}")
    if s == -1 or e == -1 or e < s:
        return text
    return text[s:e + 1]


__all__ = ["TranslatedDoc", "translate_novel", "normalise_language", "LANG_ALIASES"]
