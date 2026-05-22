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


__all__ = ["build_interaction_graph", "InteractionGraph", "InteractionEdge"]
