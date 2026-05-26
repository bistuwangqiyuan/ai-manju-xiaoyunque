"""Phase 2 — tree-path naming, project bundle, version diff, copyright fp."""
from __future__ import annotations

import pathlib
import zipfile

import pytest

from src.common.artifact_store import ArtifactStore
from src.common import version_diff
from src.compliance import copyright_fp, post_vlm_review


# ---------------------------------------------------------------------------
def test_tree_path_naming(tmp_path: pathlib.Path):
    store = ArtifactStore(tmp_path / "job1")
    k = store.tree_key(kind="ep", episode=1, shot=3, filename="mp4")
    assert k == "ep01/shot003.mp4"

    k = store.tree_key(kind="ep", episode=1, shot=3, version=2, filename="mp4")
    assert k == "ep01/shot003_v2.mp4"

    k = store.tree_key(kind="script", episode=1, filename="screenplay.txt")
    assert k == "script/ep01_screenplay.txt"

    k = store.tree_key(kind="asset", subdir="character", filename="protagonist_front.png")
    assert k == "asset/character/protagonist_front.png"


# ---------------------------------------------------------------------------
def test_project_bundle_export(tmp_path):
    store = ArtifactStore(tmp_path / "job2")
    store.put("ep01/shot001.mp4", b"video-bytes-1234")
    store.put("script/ep01_screenplay.txt", "螺旋花开\n第一集".encode("utf-8"))
    store.put("asset/character/hero_front.png", b"\x89PNG\r\n\x1a\nfake-png-data")
    store.snapshot(1, notes="first cut")
    out_zip = tmp_path / "out.zip"
    result = store.export_project_bundle(dst=out_zip, include_versions=False)
    assert result == out_zip
    assert out_zip.exists()
    with zipfile.ZipFile(out_zip) as zf:
        names = zf.namelist()
        assert "bundle_manifest.json" in names
        assert "ep01/shot001.mp4" in names
        assert "script/ep01_screenplay.txt" in names
        manifest = zf.read("bundle_manifest.json").decode("utf-8")
        assert "files" in manifest


# ---------------------------------------------------------------------------
def test_version_diff_text(tmp_path):
    a = tmp_path / "a"
    b = tmp_path / "b"
    (a / "script").mkdir(parents=True)
    (b / "script").mkdir(parents=True)
    (a / "script/ep01.txt").write_text("Alpha\nLine 2\nLine 3", encoding="utf-8")
    (b / "script/ep01.txt").write_text("Alpha\nLine 2 changed\nLine 3", encoding="utf-8")
    (b / "script/ep02.txt").write_text("brand new", encoding="utf-8")

    diff = version_diff.diff_directories(a, b)
    assert diff["stats"]["files_changed"] == 1
    assert diff["stats"]["files_added"] == 1
    text = diff["text"]
    assert "script/ep01.txt" in text
    assert text["script/ep01.txt"]["status"] == "changed"
    assert any("Line 2 changed" in line for line in text["script/ep01.txt"]["diff"])
    assert text["script/ep02.txt"]["status"] == "added"


def test_version_diff_scores_7d():
    diff = version_diff.diff_scores_7d(
        {"structure": 7.4, "style": 8.0},
        {"structure": 8.2, "style": 8.0, "detail": 6.0},
    )
    assert diff["structure"]["delta"] == pytest.approx(0.8)
    assert diff["style"]["delta"] == 0.0
    assert diff["detail"]["from"] == 0.0
    assert diff["detail"]["to"] == 6.0


# ---------------------------------------------------------------------------
def test_copyright_fp_text_roundtrip(tmp_path):
    db = tmp_path / "fp.json"
    reg = copyright_fp.CopyrightRegistry(db)
    fp = copyright_fp.text_simhash("这是一段需要保护的版权文本，约三十个字。")
    reg.add(fp=fp, kind="text", label="《示例小说》第一章")
    # exact-same text matches
    hit = reg.check_text("这是一段需要保护的版权文本，约三十个字。")
    assert hit["is_match"]
    assert hit["hits"][0]["distance"] <= 6
    # unrelated text doesn't
    miss = reg.check_text("完全不同的内容，描述春天里的小猫小狗在花园奔跑追逐。")
    assert miss["is_match"] is False or miss["hits"][0]["distance"] > 6


def test_copyright_fp_image_path(tmp_path):
    try:
        from PIL import Image  # type: ignore
    except Exception:
        pytest.skip("Pillow not installed")
    img_path = tmp_path / "ref.png"
    Image.new("RGB", (32, 32), (120, 50, 200)).save(img_path)
    reg = copyright_fp.CopyrightRegistry(tmp_path / "fp.json")
    reg.add_image(img_path, label="参考画风 A")
    res = reg.check_image(img_path)
    assert res["is_match"]
    assert res["hits"][0]["label"] == "参考画风 A"


# ---------------------------------------------------------------------------
def test_post_vlm_review_mock_blocks_explicit_filename():
    rep = post_vlm_review.review_image("/tmp/some_nsfw_frame.png", threshold=7.0)
    assert rep.blocked
    assert "adult" in rep.blocked_axes
    assert rep.recommended_route == "cover_safe_swap"


def test_post_vlm_review_clean_passes():
    rep = post_vlm_review.review_image("/tmp/standard_shot001.png", threshold=7.0)
    assert not rep.blocked
    assert rep.recommended_route is None
