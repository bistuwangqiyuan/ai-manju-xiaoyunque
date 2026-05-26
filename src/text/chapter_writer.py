"""V10 §3.1 — Chapter writer for novel generation / continuation.

Workflow::

    novel  ────────────────►  plot_state (extracted from existing chapters)
                                          │
                                          ▼
                       chapter_writer.write_next_chapter(
                           novel,
                           target_chars,
                           plot_state,
                       )
                                          │
                                          ▼
                            new chapter (text + summary + beats)
                                          │
                                          ▼
                       plot_state.add_event(...)  (auto-extracted)

The writer is LLM-agnostic — it goes through ``llm_complete_with_fallback``
so any keyed provider works.  Includes mock fallback for offline CI.
"""
from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass

from .plot_state import PlotState, Event, Character, Location


@dataclass
class GeneratedChapter:
    title: str
    body: str
    summary: str
    chars: int
    beats: list[dict]
    pov: str | None = None


# ---------------------------------------------------------------------------
# Mock fallback (offline, deterministic)
# ---------------------------------------------------------------------------
def _mock_chapter(index: int, theme: str, target_chars: int,
                  plot: PlotState) -> GeneratedChapter:
    chars_context = ", ".join(c.name for c in plot.major_characters()[:3]) or "陌生人"
    body_segments = []
    # Generate a deterministic but legible body that scales with target_chars.
    seed = (
        f"【第{index}章】{theme}\n\n"
        f"夜色降临，{chars_context}走过青石板。\n\n"
    )
    while len(seed) < target_chars:
        seed += (
            f"她想起昨日发生的事，决心再向前一步。月光照在屋脊上，远处犬吠声断续。"
            f"{chars_context}停下脚步，呼吸渐缓，握紧了手中的物件。\n\n"
            f"风过，廊下灯笼摇曳。她终于低声说出那个名字，仿佛压在心头多年。\n\n"
        )
    body = seed[:target_chars].strip()
    summary = f"第{index}章梗概：{chars_context}在夜色中作出关键决定。"
    beats = [
        {"beat": 1, "summary": "开场：夜色中的场景", "tension": 3},
        {"beat": 2, "summary": "中段：决定与暗示", "tension": 6},
        {"beat": 3, "summary": "结尾：留白", "tension": 4},
    ]
    return GeneratedChapter(
        title=f"第{index}章 · {theme[:20] if theme else '夜色'}",
        body=body,
        summary=summary,
        chars=len(body),
        beats=beats,
        pov=chars_context.split(",")[0].strip() if chars_context else None,
    )


# ---------------------------------------------------------------------------
# LLM-backed
# ---------------------------------------------------------------------------
SYSTEM_PROMPT = (
    "你是一位资深网文作家，擅长爽文、玄幻、古言。读取剧情状态后续写下一章。"
    "严格按 JSON 返回 {title, body, summary, beats:[{beat,summary,tension}], pov}。"
    "body 控制在目标字数 ±10% 以内，禁止重复上一章原文。"
)


def write_next_chapter(
    *,
    novel_title: str,
    genre: str,
    theme: str,
    index: int,
    target_chars: int,
    plot: PlotState,
    previous_summary: str = "",
    language: str = "Chinese",
    timeout_s: float = 60.0,
) -> GeneratedChapter:
    """Generate one new chapter."""
    user_prompt = (
        f"小说：{novel_title} ({genre} 体裁，{language})\n"
        f"主题：{theme}\n"
        f"目标字数：{target_chars}\n"
        f"已有剧情状态：\n{plot.chapter_summary_for_prompt()}\n"
        f"上一章梗概：{previous_summary or '（首章无）'}\n\n"
        f"请用 JSON 返回第 {index} 章。"
    )
    try:
        from src.common.multi_provider_llm import llm_complete_with_fallback
        text, _ = llm_complete_with_fallback(
            system=SYSTEM_PROMPT,
            user=user_prompt,
            json_mode=True,
            max_tokens=min(8000, max(2000, target_chars * 2)),
        )
    except Exception:
        text = None

    if text:
        try:
            data = json.loads(_extract_json(text))
            body = (data.get("body") or "").strip()
            if body:
                return GeneratedChapter(
                    title=data.get("title", f"第{index}章"),
                    body=body,
                    summary=(data.get("summary") or "").strip() or body[:120],
                    chars=len(body),
                    beats=list(data.get("beats") or []),
                    pov=data.get("pov"),
                )
        except Exception:
            pass
    return _mock_chapter(index=index, theme=theme, target_chars=target_chars, plot=plot)


def write_full_novel(
    *,
    novel_title: str,
    genre: str,
    theme: str,
    target_total_chars: int,
    chars_per_chapter: int = 3000,
    language: str = "Chinese",
    on_chapter=None,
) -> tuple[list[GeneratedChapter], PlotState]:
    plot = PlotState()
    plot.global_summary = f"{novel_title}（{theme}）"
    chapters: list[GeneratedChapter] = []
    n_target = max(1, target_total_chars // chars_per_chapter)
    previous_summary = ""
    for i in range(1, n_target + 1):
        ch = write_next_chapter(
            novel_title=novel_title, genre=genre, theme=theme,
            index=i, target_chars=chars_per_chapter, plot=plot,
            previous_summary=previous_summary, language=language,
        )
        chapters.append(ch)
        previous_summary = ch.summary
        # Auto-extract event into plot
        plot.add_event(Event(chapter=i, summary=ch.summary,
                             participants=[ch.pov] if ch.pov else []))
        if on_chapter is not None:
            try:
                on_chapter(i, ch)
            except Exception:
                pass
    return chapters, plot


def extract_plot_from_chapters(chapters: list[dict],
                               existing: PlotState | None = None) -> PlotState:
    """Cheap NER-free heuristic extractor — looks for quoted names / locations.

    For robustness during LLM offline mode we use a frequency cutoff to
    identify recurring entities.  Real production also adds LLM-based NER
    via ``llm_complete_with_fallback`` when keys are present.
    """
    ps = existing or PlotState()
    text = "\n".join(c.get("body", "") for c in chapters)

    # Heuristic CJK name extractor: 2-4 char run preceded by 道|说|对|看|向
    name_re = re.compile(r"(?:[“”\"' ]?)([\u4e00-\u9fff]{2,4})(?=(?:[“”\"' ]?)(?:道|说|笑|对|看|向|问|叹))")
    counts: dict[str, int] = {}
    for m in name_re.finditer(text):
        counts[m.group(1)] = counts.get(m.group(1), 0) + 1
    for name, n in sorted(counts.items(), key=lambda kv: -kv[1])[:10]:
        if n >= 3:
            role = "protagonist" if n == max(counts.values()) else "supporting"
            ps.add_character(Character(name=name, role=role))

    # Heuristic location: 地名通常以 山|寺|楼|阁|坊|街|府|城 结尾
    loc_re = re.compile(r"([\u4e00-\u9fff]{1,5}(?:山|寺|楼|阁|坊|街|府|城|宫|苑|院))")
    loc_counts: dict[str, int] = {}
    for m in loc_re.finditer(text):
        loc_counts[m.group(1)] = loc_counts.get(m.group(1), 0) + 1
    for name, _ in sorted(loc_counts.items(), key=lambda kv: -kv[1])[:8]:
        ps.add_location(Location(name=name))

    # Each chapter gets a coarse event
    for c in chapters:
        summary = (c.get("summary") or c.get("body", "")[:60]).strip()
        ps.add_event(Event(chapter=int(c.get("index", 1)),
                           summary=summary,
                           participants=[n for n in list(counts)[:2]]))
    return ps


def _extract_json(text: str) -> str:
    """Strip code-fence wrappers and return the JSON body."""
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\n?", "", text)
        text = text.rstrip("`").rstrip()
    # find first { ... last }
    s = text.find("{")
    e = text.rfind("}")
    if s == -1 or e == -1 or e < s:
        return text
    return text[s:e + 1]


__all__ = [
    "GeneratedChapter",
    "write_next_chapter",
    "write_full_novel",
    "extract_plot_from_chapters",
]
