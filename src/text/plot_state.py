"""V10 §3.1 — Plot state graph (characters · locations · events · arcs).

A lightweight wrapper around :mod:`networkx` (optional) that tracks the
state of a novel as we generate chapters, so the chapter writer can pull
"what's true right now" before writing the next chapter.

When ``networkx`` is unavailable we fall back to a tiny in-memory adjacency
dict.  Either way the public API is identical.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from typing import Any


@dataclass
class Character:
    name: str
    role: str = "supporting"        # protagonist | antagonist | supporting | extra
    aliases: list[str] = field(default_factory=list)
    traits: list[str] = field(default_factory=list)
    arc_summary: str = ""
    status: str = "alive"           # alive | dead | unknown
    relationships: dict[str, str] = field(default_factory=dict)  # name -> relationship


@dataclass
class Location:
    name: str
    description: str = ""
    visited_in_chapters: list[int] = field(default_factory=list)
    atmosphere: str | None = None


@dataclass
class Event:
    chapter: int
    summary: str
    participants: list[str] = field(default_factory=list)
    location: str | None = None
    impact: str = ""                  # how it shifts the plot


class PlotState:
    """Stateful holder used during incremental chapter generation."""

    def __init__(self):
        self.characters: dict[str, Character] = {}
        self.locations: dict[str, Location] = {}
        self.events: list[Event] = []
        self.global_summary: str = ""

    # ------------------------------------------------------------------
    # Mutation
    # ------------------------------------------------------------------
    def add_character(self, char: Character) -> None:
        existing = self.characters.get(char.name)
        if existing:
            existing.aliases = list(set(existing.aliases + char.aliases))
            existing.traits = list(dict.fromkeys(existing.traits + char.traits))
            if char.arc_summary:
                existing.arc_summary = (existing.arc_summary + " · " + char.arc_summary).strip(" ·")
            existing.relationships.update(char.relationships)
            if char.status != "alive":
                existing.status = char.status
        else:
            self.characters[char.name] = char

    def add_location(self, loc: Location) -> None:
        existing = self.locations.get(loc.name)
        if existing:
            existing.visited_in_chapters = sorted(set(existing.visited_in_chapters + loc.visited_in_chapters))
            if loc.atmosphere and not existing.atmosphere:
                existing.atmosphere = loc.atmosphere
            if loc.description and not existing.description:
                existing.description = loc.description
        else:
            self.locations[loc.name] = loc

    def add_event(self, ev: Event) -> None:
        self.events.append(ev)
        for name in ev.participants:
            if name not in self.characters:
                self.characters[name] = Character(name=name)

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------
    def alive_characters(self) -> list[Character]:
        return [c for c in self.characters.values() if c.status == "alive"]

    def major_characters(self) -> list[Character]:
        return [c for c in self.characters.values() if c.role in ("protagonist", "antagonist")]

    def recent_events(self, n: int = 5) -> list[Event]:
        return self.events[-n:]

    def chapter_summary_for_prompt(self) -> str:
        """A compact context block ready to be injected into the LLM prompt."""
        chars = ", ".join(f"{c.name}({c.role})" for c in self.major_characters()) or "—"
        locs = ", ".join(self.locations.keys()) or "—"
        last_events = "; ".join(f"第{e.chapter}章: {e.summary}" for e in self.recent_events(3)) or "—"
        return (
            f"【角色】{chars}\n"
            f"【地点】{locs}\n"
            f"【最近事件】{last_events}\n"
            f"【概要】{self.global_summary or '—'}"
        )

    # ------------------------------------------------------------------
    # NetworkX export
    # ------------------------------------------------------------------
    def to_graph(self):
        try:
            import networkx as nx
        except Exception:
            return self.to_dict()
        g = nx.MultiDiGraph()
        for c in self.characters.values():
            g.add_node(c.name, kind="character", role=c.role, status=c.status)
        for loc in self.locations.values():
            g.add_node(loc.name, kind="location", atmosphere=loc.atmosphere)
        for c in self.characters.values():
            for other, rel in c.relationships.items():
                g.add_edge(c.name, other, kind="relationship", label=rel)
        for ev in self.events:
            ev_id = f"event:{ev.chapter}:{hash(ev.summary) & 0xFFFF:04x}"
            g.add_node(ev_id, kind="event", chapter=ev.chapter, summary=ev.summary)
            for p in ev.participants:
                g.add_edge(p, ev_id, kind="participates")
            if ev.location:
                g.add_edge(ev_id, ev.location, kind="at")
        return g

    # ------------------------------------------------------------------
    # Serialisation
    # ------------------------------------------------------------------
    def to_dict(self) -> dict[str, Any]:
        return {
            "characters": {n: asdict(c) for n, c in self.characters.items()},
            "locations": {n: asdict(l) for n, l in self.locations.items()},
            "events": [asdict(e) for e in self.events],
            "global_summary": self.global_summary,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PlotState":
        ps = cls()
        for name, c in (data.get("characters") or {}).items():
            ps.characters[name] = Character(**c)
        for name, l in (data.get("locations") or {}).items():
            ps.locations[name] = Location(**l)
        for ev in (data.get("events") or []):
            ps.events.append(Event(**ev))
        ps.global_summary = data.get("global_summary", "")
        return ps

    @classmethod
    def from_json(cls, raw: str | bytes) -> "PlotState":
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8")
        return cls.from_dict(json.loads(raw))


__all__ = ["PlotState", "Character", "Location", "Event"]
