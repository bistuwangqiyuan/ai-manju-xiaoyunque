"""角色互动逻辑 — auto-link character dialogues to action library entries.

Requirement doc §9 角色互动逻辑：根据剧本自动判定角色之间的动作互动并注入分镜。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from src.shell2_character_assets.action_library import ACTIONS


_ACTION_KEYWORDS = [
    (("拱手", "行礼", "施礼", "鞠躬"), "salute"),
    (("牵手", "握手", "手心", "十指相扣"), "hand_in"),
    (("对视", "对望", "凝视", "凝望"), "eye_lock"),
    (("跪", "叩首", "跪伏"), "kneel"),
    (("打斗", "厮杀", "对决", "搏斗", "战斗"), "fight"),
    (("奔", "冲", "跑", "急赶"), "dash"),
    (("行走", "走来", "踱步"), "walk"),
]


@dataclass
class InteractionEdge:
    a: str
    b: str
    action_key: str
    evidence: str
    confidence: float = 0.7


@dataclass
class InteractionGraph:
    nodes: list[str] = field(default_factory=list)
    edges: list[InteractionEdge] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "nodes": self.nodes,
            "edges": [e.__dict__ for e in self.edges],
        }


def build_interaction_graph(
    episodes: list[dict],
    characters: list[dict] | None = None,
) -> dict[str, Any]:
    """Parse episode synopses + dialogue lines for character→character actions."""
    chars: list[str] = []
    for c in characters or []:
        name = c.get("name_zh") or c.get("char_id")
        if name and name not in chars:
            chars.append(name)
    # Also harvest from episodes
    for ep in episodes:
        for cid in ep.get("characters_in_episode", []):
            if cid not in chars:
                chars.append(cid)

    graph = InteractionGraph(nodes=chars)
    for ep in episodes:
        text = " ".join(
            [
                ep.get("synopsis", ""),
                ep.get("hook_3s", ""),
                ep.get("skylark_prompt", ""),
            ]
        )
        if not text:
            continue
        for kws, action in _ACTION_KEYWORDS:
            if any(k in text for k in kws):
                pair = _pick_pair(chars, text)
                if pair:
                    a, b = pair
                    graph.edges.append(
                        InteractionEdge(
                            a=a,
                            b=b,
                            action_key=action,
                            evidence=f"ep={ep.get('episode_id')}; keyword hit",
                            confidence=0.78,
                        )
                    )
    return graph.to_dict()


def _pick_pair(chars: list[str], text: str) -> tuple[str, str] | None:
    seen: list[str] = []
    for c in chars:
        if c in text and c not in seen:
            seen.append(c)
        if len(seen) >= 2:
            return seen[0], seen[1]
    if len(chars) >= 2:
        return chars[0], chars[1]
    return None


_SKYLARK_PROMPT_TEMPLATE = (
    "{a} 与 {b} 之间发生{action_label}互动，"
    "镜头：{shot_size}，画面氛围与情绪保持一致；"
    "动作清晰可辨，姿态自然，不出现多余手指、面部漂移或镜头穿帮。"
)

_ACTION_LABEL_ZH = {
    "salute": "拱手行礼", "hand_in": "牵手", "eye_lock": "深情对视",
    "kneel": "下跪", "fight": "肢体对抗", "dash": "并肩奔跑",
    "walk": "并行行走",
}

_ACTION_SHOT_SIZE = {
    "salute": "中景", "hand_in": "近景", "eye_lock": "近景特写",
    "kneel": "中景", "fight": "中近景", "dash": "全景",
    "walk": "中景",
}


def inject_skylark_prompts(
    episodes: list[dict],
    interaction_graph: dict | None = None,
    *, use_llm: bool = True,
) -> list[dict]:
    """Walk shots in each episode; for any character pair where the
    interaction graph has an edge, splice a Skylark prompt addendum into
    that shot's ``skylark_prompt`` field.

    Returns the (mutated in-place) ``episodes`` for chainability.
    """
    edges = (interaction_graph or {}).get("edges") or []
    if not edges:
        return episodes

    by_pair: dict[tuple[str, str], list[dict]] = {}
    for e in edges:
        pair = (e.get("a"), e.get("b"))
        by_pair.setdefault(pair, []).append(e)

    for ep in episodes:
        shots = ep.get("shots") or []
        ep_chars = ep.get("characters_in_episode") or []
        for shot in shots:
            text = " ".join([
                shot.get("description", ""),
                shot.get("skylark_prompt", ""),
                shot.get("notes", ""),
            ])
            shot_chars = [c for c in ep_chars if c in text]
            implicit_pair = (
                len(shot_chars) < 2 and len(ep_chars) >= 2
                and any(k in text for k in ("两人", "对方", "彼此", "二人", "两位"))
            )
            if implicit_pair:
                shot_chars = list(ep_chars[:2])
            if len(shot_chars) < 2:
                continue
            pair = (shot_chars[0], shot_chars[1])
            # Detect which actions appear in this shot's text
            triggered_actions: list[str] = []
            for kws, action in _ACTION_KEYWORDS:
                if any(k in text for k in kws):
                    triggered_actions.append(action)
            # Filter the graph edges that match both pair AND triggered action
            relevant_edges = (
                by_pair.get(pair, []) + by_pair.get((pair[1], pair[0]), [])
            )
            chosen = None
            if triggered_actions:
                for ed in relevant_edges:
                    if ed.get("action_key") in triggered_actions:
                        chosen = ed
                        break
            if chosen is None and relevant_edges:
                chosen = relevant_edges[0]
            if chosen is None:
                continue
            action = chosen.get("action_key", "")
            label = _ACTION_LABEL_ZH.get(action, action)
            shot_size = _ACTION_SHOT_SIZE.get(action, "中景")
            addendum = _SKYLARK_PROMPT_TEMPLATE.format(
                a=pair[0], b=pair[1],
                action_label=label, shot_size=shot_size,
            )
            shot["skylark_prompt"] = (
                (shot.get("skylark_prompt") or "") + "\n" + addendum
            ).strip()
            shot["interaction_pair"] = list(pair)
            shot["interaction_action"] = action

    if use_llm:
        _maybe_polish_with_llm(episodes)
    return episodes


def _maybe_polish_with_llm(episodes: list[dict]) -> None:
    """If `src.common.multi_provider_llm` is reachable, paraphrase each
    addendum once for higher prompt quality.  Otherwise no-op (already-good
    template still works)."""
    try:
        from ..common.multi_provider_llm import llm_complete_with_fallback
    except Exception:
        return
    for ep in episodes:
        for shot in ep.get("shots") or []:
            if not shot.get("interaction_action"):
                continue
            prompt = (
                "请把下面的镜头提示改写为更具电影感的 Skylark prompt（中文，70 字内），"
                "保持人物名与互动语义不变：\n" + (shot.get("skylark_prompt") or "")
            )
            try:
                text, _meta = llm_complete_with_fallback(
                    prompt=prompt, max_tokens=180, temperature=0.6,
                )
                if text:
                    shot["skylark_prompt"] = text.strip()
            except Exception:
                continue


__all__ = [
    "build_interaction_graph", "InteractionGraph", "InteractionEdge",
    "inject_skylark_prompts",
]
