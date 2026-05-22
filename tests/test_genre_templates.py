"""Phase 2: genre templates load + valid Skylark prompt."""
from src.genres import list_genre_ids, load_genres


def test_5_canonical_genres_present():
    ids = list_genre_ids()
    for required in ("ancient", "modern", "sweet_pet", "suspense", "xuanhuan"):
        assert required in ids, f"genre {required} missing"


def test_each_genre_has_style_lock_and_negative_prompts():
    for g in load_genres().values():
        assert g.style_lock_prompt, f"{g.id} missing style_lock_prompt"
        assert g.negative_prompt, f"{g.id} missing negative_prompt"
        assert g.character_archetypes, f"{g.id} missing archetypes"
        assert g.scenes, f"{g.id} missing scenes"
        assert g.aspect_ratio in {"9:16", "3:4", "16:9", "1:1"}
        assert g.sample_themes


def test_style_lock_includes_required_anchor_phrases():
    g = load_genres()["ancient"]
    assert "古风" in g.style_lock_prompt or "古风3D" in g.style_lock_prompt
    g_modern = load_genres()["modern"]
    assert "现代" in g_modern.style_lock_prompt or "cinematic" in g_modern.style_lock_prompt.lower()


def test_theme_to_novel_mock_returns_text():
    from src.shell1_screenwriter.theme_to_novel import theme_to_novel

    body = theme_to_novel(
        "山雨欲来，少年遇见少女", genre="ancient", length_words=500, backend="mock"
    )
    assert len(body) > 100
    assert "ancient" in body or "古风" in body or "山雨" in body
