"""Phase 3 — text creation layer."""
from __future__ import annotations

import json
import os

import pytest

os.environ.setdefault("FORCE_MOCK_LLM_CHAIN", "1")  # deterministic for CI


def test_novel_import_txt():
    from src.text import novel_import

    body1 = "正文内容很长很长。" * 20
    body2 = "新一章的正文同样长长长。" * 20
    raw = (
        f"第一章 风起\n\n{body1}\n\n"
        f"第二章 雨落\n\n{body2}\n"
    ).encode("utf-8")
    novel = novel_import.import_txt(raw)
    assert novel.source_format == "txt"
    assert novel.total_chars > 0
    assert novel.encoding_used == "utf-8"
    chapters = novel_import.split_into_chapters(novel.text)
    assert len(chapters) == 2
    assert chapters[0]["title"].startswith("第一章")
    assert chapters[1]["title"].startswith("第二章")


def test_novel_import_unsupported_format_raises():
    from src.text import novel_import
    with pytest.raises(ValueError):
        novel_import.import_any("foo.epub", b"...")


def test_plot_state_roundtrip():
    from src.text.plot_state import PlotState, Character, Event, Location

    ps = PlotState()
    ps.add_character(Character(name="林清", role="protagonist", arc_summary="少年成长"))
    ps.add_character(Character(name="林清", role="protagonist", arc_summary="觉醒"))
    ps.add_location(Location(name="青云山", description="主要场所"))
    ps.add_event(Event(chapter=1, summary="初登场",
                       participants=["林清"], location="青云山"))
    ps.global_summary = "测试"

    raw = ps.to_json()
    back = PlotState.from_json(raw)
    assert "林清" in back.characters
    assert back.characters["林清"].arc_summary  # merged
    assert back.locations["青云山"].name == "青云山"
    assert back.events[0].summary == "初登场"


def _force_mock_llm(monkeypatch):
    """Force every llm_complete_with_fallback call to return (None, None) so the
    mock branches fire deterministically regardless of which keys CI sets."""
    monkeypatch.setattr(
        "src.common.multi_provider_llm.llm_complete_with_fallback",
        lambda *a, **kw: (None, None),
    )


def test_chapter_writer_mock_offline(monkeypatch):
    _force_mock_llm(monkeypatch)
    from src.text import chapter_writer
    from src.text.plot_state import PlotState

    ps = PlotState()
    ch = chapter_writer.write_next_chapter(
        novel_title="测试", genre="ancient", theme="花开夜雨",
        index=1, target_chars=500, plot=ps, previous_summary="",
    )
    assert ch.chars >= 400
    assert ch.body
    assert ch.summary
    assert ch.beats


def test_novel_to_screenplay_mock_offline(monkeypatch):
    _force_mock_llm(monkeypatch)
    from src.text import novel_to_screenplay

    doc = novel_to_screenplay.novel_to_screenplay(
        novel_title="测试",
        chapters=[
            {"index": 1, "title": "第一章", "body": "啊" * 200},
            {"index": 2, "title": "第二章", "body": "嗯" * 200},
        ],
        episode_count=3,
    )
    assert doc.scenes
    assert doc.formatted_md.startswith("# 测试")
    assert all(s.episode in (1, 2, 3) for s in doc.scenes)


def test_dialogue_polish_offline(monkeypatch):
    _force_mock_llm(monkeypatch)
    from src.text import dialogue_polish

    polished = dialogue_polish.polish_dialogue([
        {"speaker": "甲", "line": "哈哈，太可笑了！"},
        {"speaker": "乙", "line": "你说什么？"},
    ])
    assert len(polished) == 2
    assert polished[0].emotion == "joyful"
    assert polished[1].emotion in ("questioning", "neutral")
    assert all(p.estimated_seconds > 0 for p in polished)


def test_novel_translate_thai_offline(monkeypatch):
    _force_mock_llm(monkeypatch)
    from src.text import novel_translate as nt
    doc = nt.translate_novel(
        source_text="第一章 风起\n\n这是测试。" * 20,
        target_language="Thai",
    )
    assert doc.language == "Thai"
    assert "[Thai]" in doc.body
    assert doc.engine == "mock"


def test_unsupported_language():
    from src.text import novel_translate
    with pytest.raises(ValueError):
        novel_translate.normalise_language("Klingon")


def test_db_new_tables_exist():
    from backend.app.db import Novel, Chapter, Screenplay, Scene, TranslatedNovel

    assert Novel.__tablename__ == "xyq_novels"
    assert Chapter.__tablename__ == "xyq_chapters"
    assert Screenplay.__tablename__ == "xyq_screenplays"
    assert Scene.__tablename__ == "xyq_scenes"
    assert TranslatedNovel.__tablename__ == "xyq_translated_novels"


def test_chapter_extraction_from_existing_chapters():
    from src.text.chapter_writer import extract_plot_from_chapters

    chapters = [
        {"index": 1, "title": "第1章", "body": "林清道：'走。'  林清看向窗外。  林清说：'好。'  雨落"},
        {"index": 2, "title": "第2章", "body": "林清道：'到了。' 阿福笑。" * 5},
    ]
    ps = extract_plot_from_chapters(chapters)
    assert ps.events
    # At least one character should be detected from the heuristic
    assert any(name == "林清" for name in ps.characters)
