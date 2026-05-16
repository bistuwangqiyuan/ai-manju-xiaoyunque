"""Shell 1 — Screenwriter brain (4-model pipeline).

Pipeline:
    novel (~2400 words classical Chinese)
        -> DeepSeek V4-Pro (1M ctx, event extraction)
        -> Claude Opus 4.7 (master screenwriter, 10 episodes)
        -> Doubao Seed 1.6 Thinking (Skylark-friendly reformat)
        -> Gemini 2.5 Pro (JSON schema strict validation)
"""

from .extract_events import EventExtractor
from .write_episodes import EpisodeWriter
from .reformat_skylark import SkylarkFormatter
from .schema_validate import SchemaValidator, EPISODE_JSON_SCHEMA

__all__ = [
    "EventExtractor",
    "EpisodeWriter",
    "SkylarkFormatter",
    "SchemaValidator",
    "EPISODE_JSON_SCHEMA",
]
