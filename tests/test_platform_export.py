"""Phase 5: platform export specs + (best-effort) ffmpeg roundtrip."""
import pathlib
import shutil

from src.shell5_post_production.platform_export import PLATFORM_SPECS, export_for_platforms


def test_all_six_platforms_present():
    expected = {"douyin", "kuaishou", "wechat_video", "xiaohongshu", "bilibili", "youtube_shorts"}
    assert expected.issubset(set(PLATFORM_SPECS.keys()))


def test_specs_have_sensible_resolutions():
    for spec in PLATFORM_SPECS.values():
        assert spec.width > 0 and spec.height > 0
        assert spec.video_bitrate.endswith("M") or spec.video_bitrate.endswith("k")
        assert spec.fps in {24, 25, 30, 60}
        assert spec.audio_bitrate
        assert spec.caption_template


def test_export_for_platforms_copy_fallback(tmp_path: pathlib.Path):
    # If ffmpeg is missing or fails, we should still get target files (copied source).
    src = tmp_path / "src.mp4"
    src.write_bytes(b"FAKE")
    out_root = tmp_path / "exports"
    outs = export_for_platforms(
        src,
        out_root,
        platforms=["douyin", "wechat_video"],
        add_watermark=False,
        title="《测试》",
        episode=1,
        genre="ancient",
    )
    assert set(outs.keys()) == {"douyin", "wechat_video"}
    for spec_id, info in outs.items():
        assert pathlib.Path(info["path"]).exists()
        assert info["caption"]
        assert info["hashtags"]


def test_marketing_copy_heuristic():
    from src.shell5_post_production.marketing_copy import generate_marketing_copy

    out = generate_marketing_copy(
        title="聊斋·聂小倩",
        synopsis="少女在月夜邂逅书生，揭开千年悬案。",
        genre="ancient",
    )
    assert out["title"]
    assert out["summary"]
    assert out["hook_copy"]
    assert len(out["hashtags"]) >= 3
    assert all(h.startswith("#") for h in out["hashtags"])
