"""Phase 8 — Advanced + derivative tests."""
from __future__ import annotations

import os
import pathlib
import pytest


# ---------- 8.1 continuation: n_candidates + foreshadowing ----------

def test_continuation_single_with_foreshadowing(monkeypatch):
    monkeypatch.setenv("FORCE_MOCK_CONTINUATION", "1")
    from src.advanced.continuation import continue_story
    res = continue_story(
        prior_novel="主角穿越古代成为皇子",
        prior_episodes=[{"episode_id": "ep01", "title": "宫门初见"}],
        extra_episodes=2,
        genre="ancient",
        foreshadowing=["皇后早已知晓主角身份", "皇兄手中藏有玉佩信物"],
    )
    assert "episodes" in res
    assert len(res["episodes"]) == 2
    # foreshadowing distributed
    fs_payloads = [ep.get("foreshadowing_payload") for ep in res["episodes"]]
    fs_flat = [item for sub in fs_payloads if sub for item in sub]
    assert "皇后早已知晓主角身份" in fs_flat
    assert "皇兄手中藏有玉佩信物" in fs_flat


def test_continuation_multi_candidates(monkeypatch):
    monkeypatch.setenv("FORCE_MOCK_CONTINUATION", "1")
    from src.advanced.continuation import continue_story
    res = continue_story(
        prior_novel="豪门商战",
        prior_episodes=[{"episode_id": "ep01"}, {"episode_id": "ep02"}],
        extra_episodes=1,
        n_candidates=3,
        foreshadowing=["对手是失散多年的兄长"],
    )
    assert res.get("n_candidates") == 3
    assert len(res["candidates"]) == 3
    for cand in res["candidates"]:
        assert "summary" in cand
        assert len(cand["episodes"]) == 1
        assert "候选" in cand["episodes"][0]["title"]


# ---------- 8.1 interaction LLM injection ----------

def test_inject_skylark_prompts_basic(monkeypatch):
    from src.advanced.interaction_logic import inject_skylark_prompts
    # Disable LLM polish so we exercise the template path deterministically
    import src.advanced.interaction_logic as il
    monkeypatch.setattr(il, "_maybe_polish_with_llm", lambda eps: None)

    episodes = [{
        "episode_id": "ep01",
        "characters_in_episode": ["林辰", "苏雨"],
        "shots": [
            {"description": "林辰对苏雨拱手行礼", "skylark_prompt": "原始 prompt"},
            {"description": "两人对视良久", "skylark_prompt": "对视镜头"},
        ],
    }]
    graph = {
        "nodes": ["林辰", "苏雨"],
        "edges": [
            {"a": "林辰", "b": "苏雨", "action_key": "salute"},
            {"a": "林辰", "b": "苏雨", "action_key": "eye_lock"},
        ],
    }
    out = inject_skylark_prompts(episodes, graph, use_llm=False)
    s0 = out[0]["shots"][0]
    s1 = out[0]["shots"][1]
    assert "拱手行礼" in s0["skylark_prompt"]
    assert s0["interaction_action"] == "salute"
    assert "深情对视" in s1["skylark_prompt"]
    assert s1["interaction_action"] == "eye_lock"
    assert s0["interaction_pair"] == ["林辰", "苏雨"]


def test_inject_skylark_no_edges_is_noop():
    from src.advanced.interaction_logic import inject_skylark_prompts
    episodes = [{"shots": [{"skylark_prompt": "x"}]}]
    out = inject_skylark_prompts(episodes, {"edges": []})
    assert out[0]["shots"][0]["skylark_prompt"] == "x"


# ---------- 8.2 asset_restyle ----------

def test_asset_restyle_plan_walks_tree(tmp_path):
    from src.advanced.asset_restyle import plan_restyle
    # Build a fake job tree
    (tmp_path / "characters").mkdir()
    (tmp_path / "characters" / "linchen_front.png").write_bytes(b"\x89PNG\r\n")
    (tmp_path / "characters" / "linchen_side.png").write_bytes(b"\x89PNG\r\n")
    (tmp_path / "scenes").mkdir()
    (tmp_path / "scenes" / "palace_hall.jpg").write_bytes(b"\xff\xd8\xff")
    (tmp_path / "episodes").mkdir()
    (tmp_path / "episodes" / "ep01.mp4").write_bytes(b"\x00" * 100)
    (tmp_path / "shots").mkdir()
    (tmp_path / "shots" / "shot_001.png").write_bytes(b"\x89PNG\r\n")

    plan = plan_restyle(tmp_path, target_style="jpn_anime")
    assert plan.target_style == "jpn_anime"
    assert len(plan.assets) == 5
    cats = {a.category for a in plan.assets}
    assert "character_three_view" in cats
    assert "scene_plate" in cats
    assert "episode_video" in cats
    assert "shot_frame" in cats

    kinds = {a.asset_kind for a in plan.assets}
    assert kinds == {"image", "video"}


def test_asset_restyle_execute_mock(tmp_path, monkeypatch):
    monkeypatch.setenv("FORCE_MOCK_RESTYLE", "1")
    monkeypatch.delenv("FAL_API_KEY", raising=False)
    from src.advanced.asset_restyle import plan_restyle, execute_restyle
    (tmp_path / "characters").mkdir()
    (tmp_path / "characters" / "linchen.png").write_bytes(b"\x89PNG\r\nfake")
    (tmp_path / "episodes").mkdir()
    (tmp_path / "episodes" / "ep01.mp4").write_bytes(b"\x00" * 32)

    plan = plan_restyle(tmp_path, target_style="guoman")
    res = execute_restyle(plan, snapshot_originals=True)
    assert res.processed == 2
    assert res.failed == 0
    assert res.backend_used.get("mock") == 2
    snap = pathlib.Path(plan.snapshot_dir)
    assert (snap / "characters" / "linchen.png").exists()
    assert pathlib.Path(plan.assets[0].dst_path).exists()


# ---------- 8.3.1 novel_to_comic ----------

def test_novel_to_comic_builds_spec():
    from src.derivative.novel_to_comic import build_spec_from_novel
    chapters = [
        {"title": "第一章", "content": '林辰走进皇宫。\n"陛下千岁。"他低声说。\n殿内一片寂静。'},
        {"title": "第二章", "content": "他做了一个奇怪的梦。\n醒来时已是黎明。"},
    ]
    spec = build_spec_from_novel(title="穿越录", author="测试作者", chapters=chapters)
    assert spec.title == "穿越录"
    assert len(spec.panels) >= 2
    assert spec.panels[0].chapter_index == 0
    # dialogue extracted
    has_dialogue = any(p.dialogue for p in spec.panels)
    assert has_dialogue


def test_novel_to_comic_render_to_text_fallback(tmp_path, monkeypatch):
    """Force text fallback when reportlab is not used."""
    from src.derivative import novel_to_comic
    monkeypatch.setattr(novel_to_comic, "_try_reportlab_render",
                        lambda spec, out: None)
    monkeypatch.setattr(novel_to_comic, "_pil_fallback_render",
                        lambda spec, out: None)
    res = novel_to_comic.novel_to_comic(
        title="测试漫画",
        chapters=[{"title": "第一章", "content": "故事开始了。\n他大声喊。"}],
        output_path=tmp_path / "comic.pdf",
    )
    assert res.backend == "text"
    assert pathlib.Path(res.output_path).exists()
    txt = pathlib.Path(res.output_path).read_text(encoding="utf-8")
    assert "测试漫画" in txt


def test_novel_to_comic_pil_fallback(tmp_path, monkeypatch):
    try:
        import PIL  # noqa: F401
    except Exception:
        pytest.skip("PIL not installed")
    from src.derivative import novel_to_comic
    monkeypatch.setattr(novel_to_comic, "_try_reportlab_render",
                        lambda spec, out: None)
    res = novel_to_comic.novel_to_comic(
        title="PIL Fallback Comic",
        chapters=[{"content": "开始。\n中场。\n结束。"}],
        output_path=tmp_path / "comic_pil.pdf",
    )
    assert res.backend == "pil"
    assert res.n_panels > 0
    for p in res.extra_paths:
        assert pathlib.Path(p).exists()


# ---------- 8.3.2 video_to_comic ----------

def test_video_to_comic_mock_extracts_keyframes(tmp_path, monkeypatch):
    """When the video doesn't exist or no backends are present, use mock keyframes."""
    from src.derivative import video_to_comic as v2c
    out_pdf = tmp_path / "from_video.pdf"
    fake_video = tmp_path / "missing.mp4"
    res = v2c.video_to_comic(fake_video, out_pdf, mode="mock", panels_per_page=2)
    assert res.backend == "mock"
    assert len(res.keyframes) > 0
    assert pathlib.Path(res.comic.output_path).exists() or \
           pathlib.Path(str(res.comic.output_path)).exists() or \
           str(res.comic.output_path).endswith("/")


# ---------- 8.3.3 comic_to_motion ----------

def test_comic_to_motion_dry_run_pipeline(tmp_path):
    try:
        from PIL import Image  # type: ignore
    except Exception:
        pytest.skip("PIL not installed")
    # Build a mock comic folder of PNGs
    comic_dir = tmp_path / "comic_input"
    comic_dir.mkdir()
    for i in range(4):
        Image.new("RGB", (128, 128), (i * 60, 100, 200 - i * 30)).save(
            comic_dir / f"panel_{i:03d}.png")

    from src.derivative.comic_to_motion import comic_to_motion
    res = comic_to_motion(
        comic_dir, tmp_path / "out.mp4",
        video_backend="mock", dry_run=True, ocr_language="ch",
    )
    assert len(res.panels) == 4
    assert len(res.motion_plan) == 4
    # OCR backend is "none" or "tesseract" or "paddleocr"
    assert res.backend_ocr in ("none", "tesseract", "paddleocr")
    # In dry_run, no clips
    assert res.clip_paths == []
    assert res.motion_plan[0].duration_sec > 0


def test_comic_to_motion_extract_panels_pdf_falls_through(tmp_path):
    from src.derivative.comic_to_motion import extract_panels
    fake_pdf = tmp_path / "fake.pdf"
    fake_pdf.write_bytes(b"%PDF-1.4\nfake")  # malformed pdf
    panels = extract_panels(fake_pdf, tmp_path / "out")
    # Should not crash; may return empty if no backend handles it
    assert isinstance(panels, list)


# ---------- 8.2 brush mask ----------

def test_restyle_brush_normalize_and_task(tmp_path):
    try:
        from PIL import Image  # type: ignore
    except Exception:
        pytest.skip("PIL not installed")
    img_path = tmp_path / "frame.png"
    Image.new("RGB", (256, 256), (180, 180, 180)).save(img_path)
    raw_mask = tmp_path / "mask_raw.png"
    m = Image.new("L", (256, 256), 0)
    for x in range(60, 200):
        for y in range(60, 200):
            m.putpixel((x, y), 255)
    m.save(raw_mask)

    from src.derivative.restyle_brush import make_brush_task
    task = make_brush_task(
        image_path=img_path, raw_mask_path=raw_mask,
        prompt="将选中区域改成日系动漫风",
        work_dir=tmp_path / "work",
        feather_px=4,
    )
    assert pathlib.Path(task.mask_path).exists()
    assert task.backend == "flux_kontext_inpaint"
    assert "日系" in task.prompt
    assert task.feather_px == 4
