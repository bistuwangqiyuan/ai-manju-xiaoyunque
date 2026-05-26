"""V10 §3 — Text creation layer.

Submodules:
    novel_import          — txt / docx / pdf → unicode text
    chapter_writer        — LLM-driven novel→chapters with budget control
    plot_state            — networkx-backed character / location / event graph
    novel_to_screenplay   — novel chapters → episode screenplay (Markdown)
    dialogue_polish       — punch up dialogue & emotion tagging
    novel_translate       — multi-lingual translation (incl. Thai)
"""
from . import novel_import, chapter_writer, plot_state, novel_to_screenplay, dialogue_polish, novel_translate

__all__ = [
    "novel_import",
    "chapter_writer",
    "plot_state",
    "novel_to_screenplay",
    "dialogue_polish",
    "novel_translate",
]
