"""Phase 1 — Job specs (aspect/resolution/fps/duration) + custom style."""
from __future__ import annotations

import io
import pathlib

import pytest


@pytest.fixture(scope="module")
def synthetic_image_blobs() -> list[bytes]:
    """Three deterministic 32x32 RGB images of distinct dominant hues."""
    try:
        from PIL import Image  # type: ignore
    except Exception:
        pytest.skip("Pillow not installed")
    blobs = []
    for col in [(180, 60, 60), (60, 60, 180), (200, 160, 60)]:
        img = Image.new("RGB", (64, 64), col)
        # add a black border so JPEG noise doesn't collapse to one bucket
        for x in range(64):
            img.putpixel((x, 0), (0, 0, 0))
            img.putpixel((x, 63), (0, 0, 0))
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        blobs.append(buf.getvalue())
    return blobs


def test_fingerprint_emits_deterministic_id(synthetic_image_blobs):
    from src.genres.custom_style import fingerprint_style

    fp1 = fingerprint_style(synthetic_image_blobs, name="x", include_clip=False)
    fp2 = fingerprint_style(synthetic_image_blobs, name="x", include_clip=False)
    assert fp1.style_id == fp2.style_id
    assert fp1.style_id.startswith("custom_")
    assert len(fp1.palette_hex) == 5
    assert fp1.style_lock_prompt
    assert "9:16" in fp1.style_lock_prompt


def test_materialise_yaml_writable(synthetic_image_blobs, tmp_path, monkeypatch):
    from src.genres import custom_style as cs

    # Sandbox the output dirs
    monkeypatch.setattr(cs, "CUSTOM_DIR", tmp_path / "custom")
    monkeypatch.setattr(cs, "CUSTOM_EMBED_DIR", tmp_path / "emb")
    cs.CUSTOM_DIR.mkdir(parents=True, exist_ok=True)
    cs.CUSTOM_EMBED_DIR.mkdir(parents=True, exist_ok=True)

    fp = cs.fingerprint_style(synthetic_image_blobs, name="蜻蜓水墨", user_id=1, include_clip=False)
    path = cs.materialise_genre_yaml(fp)
    assert path.exists()
    import yaml
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert data["id"] == fp.style_id
    assert data["palette"]["primary"] == fp.palette_hex
    assert data["_custom_owner_user_id"] == 1
    assert data["style_lock_prompt"]


def test_list_and_delete(synthetic_image_blobs, tmp_path, monkeypatch):
    from src.genres import custom_style as cs

    monkeypatch.setattr(cs, "CUSTOM_DIR", tmp_path / "custom")
    monkeypatch.setattr(cs, "CUSTOM_EMBED_DIR", tmp_path / "emb")
    cs.CUSTOM_DIR.mkdir(parents=True, exist_ok=True)
    cs.CUSTOM_EMBED_DIR.mkdir(parents=True, exist_ok=True)
    fp = cs.fingerprint_style(synthetic_image_blobs, name="A", user_id=42, include_clip=False)
    cs.materialise_genre_yaml(fp)

    items = cs.list_custom_styles(user_id=42)
    assert any(i["style_id"] == fp.style_id for i in items)

    assert cs.delete_custom_style(fp.style_id, user_id=42) is True
    assert cs.delete_custom_style(fp.style_id, user_id=42) is False


def test_job_create_in_accepts_v10_fields():
    from backend.app.schemas import JobCreateIn

    payload = JobCreateIn(
        title="测试",
        novel_excerpt="x" * 60,
        episodes=2,
        aspect_ratio="16:9",
        resolution="2k",
        fps=30,
        duration_per_episode_s=120,
        custom_style_id="custom_abcdef123456",
        ui_mode="pro",
    )
    assert payload.aspect_ratio == "16:9"
    assert payload.resolution == "2k"
    assert payload.fps == 30
    assert payload.duration_per_episode_s == 120
    assert payload.custom_style_id == "custom_abcdef123456"
    assert payload.ui_mode == "pro"


def test_job_db_columns_present():
    from backend.app.db import Job

    cols = {c.name for c in Job.__table__.columns}
    assert "aspect_ratio" in cols
    assert "resolution" in cols
    assert "fps" in cols
    assert "duration_per_episode_s" in cols
    assert "custom_style_id" in cols
    assert "ui_mode" in cols
    assert "parent_id" in cols
    assert "org_id" in cols
