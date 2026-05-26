"""Phase 10 — Export adapters tests."""
from __future__ import annotations

import pathlib
import pytest


# ---------- §10.1 GIF / multi-image ----------

def test_video_to_gif_no_backend(tmp_path, monkeypatch):
    from src.export import gif_export
    monkeypatch.setattr(gif_export, "_imageio_gif", lambda *a, **k: None)
    monkeypatch.setattr(gif_export, "_ffmpeg_gif", lambda *a, **k: None)
    res = gif_export.video_to_gif(tmp_path / "missing.mp4", tmp_path / "out.gif")
    assert res.backend == "none"
    assert "no backend" in res.notes[0]


def test_frames_to_gif_pil(tmp_path):
    try:
        from PIL import Image
    except Exception:
        pytest.skip("PIL not installed")
    frame_paths = []
    for i in range(4):
        p = tmp_path / f"frame_{i}.png"
        Image.new("RGB", (32, 32), (i * 60, 100, 200)).save(p)
        frame_paths.append(p)
    from src.export.gif_export import frames_to_gif
    res = frames_to_gif(frame_paths, tmp_path / "anim.gif", fps=8)
    assert res.backend == "pil"
    assert res.n_frames == 4
    assert pathlib.Path(res.output_path).exists()
    assert res.size == (32, 32)


def test_export_frame_sequence_no_backend(tmp_path, monkeypatch):
    from src.export import frame_sequence
    monkeypatch.setattr(frame_sequence, "_imageio_sequence", lambda *a, **k: None)
    monkeypatch.setattr(frame_sequence, "_ffmpeg_sequence", lambda *a, **k: None)
    res = frame_sequence.export_frame_sequence(
        tmp_path / "missing.mp4", tmp_path / "frames", fps=1, ext="png",
    )
    assert res.backend == "none"


# ---------- §10.1 storyboard grid export ----------

def test_export_storyboard_pil(tmp_path):
    try:
        from PIL import Image
    except Exception:
        pytest.skip("PIL not installed")
    cells = []
    for i in range(6):
        p = tmp_path / f"shot_{i:03d}.png"
        Image.new("RGB", (480, 270), (40, 40, 40 + i * 30)).save(p)
        cells.append({
            "path": str(p),
            "shot_id": i + 1,
            "duration_s": 3.0 + i * 0.5,
            "shot_type": ["wide", "medium", "close"][i % 3],
            "description": f"镜头{i + 1} 描述",
        })
    from src.export.storyboard_export import export_storyboard
    res = export_storyboard(cells, tmp_path / "sb.png", cols=3, title="测试分镜")
    assert pathlib.Path(res.output_path).exists()
    assert pathlib.Path(res.sidecar_path).exists()
    assert res.rows == 2
    assert res.cols == 3
    assert res.n_cells == 6
    sidecar_text = pathlib.Path(res.sidecar_path).read_text(encoding="utf-8")
    assert "测试分镜" in sidecar_text
    assert "镜头1 描述" in sidecar_text


# ---------- §10.2 cover composer ----------

def test_cover_preview_layout_ratios():
    from src.export.cover_compose import CoverLayout, preview_layout
    layout = CoverLayout(title="测试封面", subtitle="副标题")
    prev = preview_layout((1080, 1920), layout)
    assert prev.canvas_size == (1080, 1920)
    # title near bottom-left
    assert prev.title_position[0] < 200
    assert prev.title_position[1] > 1400
    assert prev.title_font_size > 100  # 8.5% of 1920 ≈ 163
    # AIGC label + watermark present
    assert prev.aigc_position is not None
    assert prev.watermark_position is not None


def test_cover_compose_writes_png(tmp_path):
    try:
        from PIL import Image
    except Exception:
        pytest.skip("PIL not installed")
    base = tmp_path / "base.jpg"
    Image.new("RGB", (1080, 1920), (90, 30, 60)).save(base)
    from src.export.cover_compose import compose_cover, CoverLayout
    layout = CoverLayout(title="《长安雨夜》", subtitle="第 1 集",
                         watermark_text="@xiaoyunque")
    res = compose_cover(base, tmp_path / "cover.png", layout=layout,
                        canvas_size=(1080, 1920))
    assert pathlib.Path(res.output_path).exists()
    assert res.backend == "pil"
    assert "aigc" in res.preview.to_dict()


def test_cover_compose_without_base_works(tmp_path):
    try:
        from PIL import Image  # noqa: F401
    except Exception:
        pytest.skip("PIL not installed")
    from src.export.cover_compose import compose_cover
    res = compose_cover(None, tmp_path / "cover_nobase.png",
                        canvas_size=(540, 960))
    assert pathlib.Path(res.output_path).exists()


# ---------- §10.3 platform copy presets ----------

def test_platform_copy_default_template():
    from src.export.platform_copy_presets import generate_copy, PLATFORM_TONE
    out = generate_copy(
        list(PLATFORM_TONE.keys()),
        title="星河奇缘", episode=3,
        hook="女主穿越唐朝竟成为太子妃",
        genre="ancient", use_llm=False,
    )
    assert set(out) == set(PLATFORM_TONE)
    for pid, c in out.items():
        assert "星河奇缘" in c.caption or "Episode" in c.caption
        assert c.platform == pid
        assert len(c.hashtags) > 0
        assert all(h.startswith("#") for h in c.hashtags)


def test_platform_copy_per_genre_hashtags():
    from src.export.platform_copy_presets import generate_copy
    out = generate_copy(["xiaohongshu"], title="霸总", episode=1,
                        hook="穿越成豪门弃妇", genre="romance")
    cap = out["xiaohongshu"]
    assert any("甜宠" in h for h in cap.hashtags) or any("言情" in h for h in cap.hashtags)


def test_platform_copy_long_caption_warning():
    from src.export.platform_copy_presets import generate_copy
    long_hook = "x" * 1500
    out = generate_copy(["youtube_shorts"], title="long", episode=1,
                        hook=long_hook, genre="modern")
    cap = out["youtube_shorts"]
    assert cap.too_long is True
    assert cap.warnings


def test_shorten_caption_trims():
    from src.export.platform_copy_presets import shorten_caption
    txt = "abcdef\nxyz"
    out = shorten_caption(txt, 100)
    assert out == txt
    out2 = shorten_caption(txt, 4)
    assert len(out2) <= 5
