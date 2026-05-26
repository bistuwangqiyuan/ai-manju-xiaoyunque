"""V10 §3.2 — Novel → screenplay (episodes + scenes + dialogue).

Produces a structured ``ScreenplayDoc`` that contains a Markdown-formatted
full screenplay plus per-scene metadata ready for direct insertion into the
``xyq_screenplays`` / ``xyq_scenes`` tables.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field


@dataclass
class ParsedDialogue:
    speaker: str
    line: str
    emotion: str = "neutral"
    direction: str | None = None


@dataclass
class ParsedScene:
    episode: int
    index: int
    heading: str
    location: str
    time_of_day: str
    atmosphere: str
    action_text: str
    dialogue: list[ParsedDialogue] = field(default_factory=list)
    pov_character: str | None = None
    duration_estimate_s: int = 8


@dataclass
class ScreenplayDoc:
    title: str
    episode_count: int
    target_duration_per_episode_s: int
    formatted_md: str
    scenes: list[ParsedScene]
    characters: list[dict]


# ---------------------------------------------------------------------------
SYSTEM_PROMPT = (
    "你是一名擅长短剧编剧的资深编剧。将提供的章节内容改编成结构化短剧剧本，"
    "返回严格 JSON：{episodes:[{number, scenes:[{heading, location, time_of_day, "
    "atmosphere, action, dialogue:[{speaker, line, emotion}], pov, duration_s}]}], "
    "characters:[{name, role, description}]}。"
    "保持画面感强、台词精炼、每场戏 6-12 秒。"
)


def novel_to_screenplay(
    *,
    novel_title: str,
    chapters: list[dict],
    episode_count: int = 10,
    target_duration_per_episode_s: int = 80,
    language: str = "Chinese",
    timeout_s: float = 90.0,
) -> ScreenplayDoc:
    user_prompt = (
        f"作品标题：{novel_title}\n"
        f"目标剧集数：{episode_count}\n"
        f"每集目标时长：{target_duration_per_episode_s}s\n"
        f"语言：{language}\n\n"
        f"以下是 {len(chapters)} 章原文（已浓缩）：\n\n"
    )
    for c in chapters[:20]:
        body = c.get("body", "")
        if len(body) > 2000:
            body = body[:2000] + "…"
        user_prompt += f"## {c.get('title', '章')}\n{body}\n\n"

    try:
        from src.common.multi_provider_llm import llm_complete_with_fallback
        text, _ = llm_complete_with_fallback(
            system=SYSTEM_PROMPT,
            user=user_prompt,
            json_mode=True,
            max_tokens=12000,
        )
    except Exception:
        text = None

    if text:
        try:
            data = json.loads(_extract_json(text))
            return _build_from_llm(data, novel_title, episode_count,
                                   target_duration_per_episode_s)
        except Exception:
            pass

    return _build_mock(novel_title, chapters, episode_count,
                       target_duration_per_episode_s)


# ---------------------------------------------------------------------------
def _build_from_llm(data: dict, title: str, episode_count: int,
                    target_duration: int) -> ScreenplayDoc:
    scenes: list[ParsedScene] = []
    md_chunks = [f"# {title}\n"]
    for ep in (data.get("episodes") or [])[:episode_count]:
        epn = int(ep.get("number") or len(md_chunks))
        md_chunks.append(f"\n## 第 {epn} 集\n")
        for i, sc in enumerate(ep.get("scenes") or [], start=1):
            location = (sc.get("location") or "未指定").strip()
            time_of_day = (sc.get("time_of_day") or "白天").strip()
            atmosphere = (sc.get("atmosphere") or "中性").strip()
            heading = sc.get("heading") or f"{location} · {time_of_day}"
            action = (sc.get("action") or "").strip()
            dialogue = []
            for d in sc.get("dialogue") or []:
                dialogue.append(ParsedDialogue(
                    speaker=str(d.get("speaker") or "旁白"),
                    line=str(d.get("line") or "").strip(),
                    emotion=str(d.get("emotion") or "neutral"),
                    direction=d.get("direction"),
                ))
            duration_s = int(sc.get("duration_s") or 8)
            scenes.append(ParsedScene(
                episode=epn, index=i,
                heading=heading, location=location,
                time_of_day=time_of_day, atmosphere=atmosphere,
                action_text=action, dialogue=dialogue,
                pov_character=sc.get("pov"),
                duration_estimate_s=duration_s,
            ))
            md_chunks.append(f"\n### 场景 {i} · {heading}\n")
            md_chunks.append(f"*{atmosphere} · {time_of_day}*\n\n{action}\n")
            for d in dialogue:
                md_chunks.append(f"\n**{d.speaker}** ({d.emotion}): {d.line}")
    chars = list(data.get("characters") or [])
    return ScreenplayDoc(
        title=title,
        episode_count=episode_count,
        target_duration_per_episode_s=target_duration,
        formatted_md="\n".join(md_chunks).strip(),
        scenes=scenes,
        characters=chars,
    )


def _build_mock(title: str, chapters: list[dict], episode_count: int,
                target_duration: int) -> ScreenplayDoc:
    scenes: list[ParsedScene] = []
    md = [f"# {title}\n"]
    chapter_per_ep = max(1, len(chapters) // max(episode_count, 1))
    for ep in range(1, episode_count + 1):
        md.append(f"\n## 第 {ep} 集\n")
        chs = chapters[(ep - 1) * chapter_per_ep: ep * chapter_per_ep] or chapters[:1]
        for i, ch in enumerate(chs, start=1):
            text = ch.get("body", "")[:300]
            md.append(f"\n### 场景 {i} · 内景\n*中性 · 白天*\n\n{text}\n")
            scenes.append(ParsedScene(
                episode=ep, index=i,
                heading="内景", location="不知名场所",
                time_of_day="白天", atmosphere="中性",
                action_text=text,
                dialogue=[
                    ParsedDialogue(speaker="角色甲", line="此局已变。", emotion="冷静"),
                    ParsedDialogue(speaker="角色乙", line="可有破解之法？", emotion="忧虑"),
                ],
                duration_estimate_s=target_duration // max(len(chs), 1),
            ))
    return ScreenplayDoc(
        title=title,
        episode_count=episode_count,
        target_duration_per_episode_s=target_duration,
        formatted_md="\n".join(md).strip(),
        scenes=scenes,
        characters=[{"name": "角色甲", "role": "protagonist", "description": "主角"},
                    {"name": "角色乙", "role": "supporting", "description": "配角"}],
    )


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


def screenplay_to_json(doc: ScreenplayDoc) -> str:
    return json.dumps({
        "title": doc.title,
        "episode_count": doc.episode_count,
        "scenes": [
            {
                "episode": s.episode, "index": s.index, "heading": s.heading,
                "location": s.location, "time_of_day": s.time_of_day,
                "atmosphere": s.atmosphere, "action": s.action_text,
                "dialogue": [
                    {"speaker": d.speaker, "line": d.line, "emotion": d.emotion}
                    for d in s.dialogue
                ],
                "pov": s.pov_character,
                "duration_estimate_s": s.duration_estimate_s,
            } for s in doc.scenes
        ],
        "characters": doc.characters,
    }, ensure_ascii=False, indent=2)


__all__ = [
    "novel_to_screenplay",
    "ScreenplayDoc",
    "ParsedScene",
    "ParsedDialogue",
    "screenplay_to_json",
]
