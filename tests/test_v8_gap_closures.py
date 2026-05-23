"""Phase D — gap-closure regression tests for v8.

Covers Phase C deliverables in mock mode:

* Filing autogen (Gap C-9) writes a deterministic markdown + JSON sidecar.
* AIGC C2PA sidecar (Gap C-8) is emitted with sha256 + ai_systems list.
* Wan-Animate route classifier (Gap C-1) tags fight shots in the
  orchestrator output.
* PuLID multi-character lock helper (Gap C-3) gracefully degrades to
  the main character's canonical when no Replicate token is configured.
* Bilingual subtitle wiring (Gap C-10) produces the expected ISO lang
  normalisation and post-artifact key.
* Repair router auto-wires v8-corrected handler class names (drift B-1).
"""
from __future__ import annotations

import json
import os
import pathlib

import pytest

from src.pipeline.orchestrator_v2 import PipelineOrchestratorV2


# ============================================================================
# Filing autogen — Gap C-9
# ============================================================================

def test_filing_autogen_writes_markdown_and_sidecar(tmp_path):
    from src.compliance import autofill, categorize

    result = autofill(
        job_id=42,
        title="《测试·副本》",
        genre="ancient",
        episodes=10,
        cost_cny=600_000,
        synopsis_excerpt="一个完全原创的短剧梗概，主线清晰。",
        ai_systems=["skylark-agent-2.0"],
        ai_engine_records=[
            {"name": "Skylark", "vendor": "Volcengine", "filing_no": "VOLC-2026-001"},
        ],
        out_dir=tmp_path,
    )
    md = pathlib.Path(result["md_path"]).read_text(encoding="utf-8")
    sidecar = json.loads(pathlib.Path(result["json_path"]).read_text(encoding="utf-8"))
    checklist = json.loads(pathlib.Path(result["checklist_path"]).read_text(encoding="utf-8"))

    assert result["category"] == "其他类"  # 600k < 1M ⇒ 其他类
    assert "Skylark" in md
    assert sidecar["summary"]["title"] == "《测试·副本》"
    assert checklist["items"]["aigc_engine_records"] is True
    assert checklist["passed_count"] >= 4
    # Categoriser handles >300万
    assert categorize(2_500_000)[0] == "普通类"
    assert categorize(3_500_000)[0] == "重点类"


# ============================================================================
# C2PA sidecar — Gap C-8
# ============================================================================

def test_c2pa_sidecar_includes_sha256_and_ai_systems(tmp_path):
    from src.shell5_post_production.aigc_sidecar import write_sidecar

    fake_master = tmp_path / "master.mp4"
    fake_master.write_bytes(b"FAKEMP4DATA\x00" * 64)
    sidecar_path = write_sidecar(
        fake_master,
        job_id=99,
        ai_systems=["skylark-agent-2.0", "doubao-seed-1.6-vision"],
    )
    data = json.loads(sidecar_path.read_text(encoding="utf-8"))
    assert data["content_type"] == "ai_generated_video"
    assert data["synthid_present"] is True
    assert "skylark-agent-2.0" in data["ai_systems"]
    assert len(data["sha256"]) == 64
    assert data["producer_id"].startswith("99-")


# ============================================================================
# PuLID multi-character lock helper — Gap C-3
# ============================================================================

def test_multi_character_lock_falls_back_without_replicate_token(monkeypatch):
    from src.shell2_character_assets.build_asset import CharacterAsset, multi_character_lock

    monkeypatch.delenv("REPLICATE_API_TOKEN", raising=False)

    main = CharacterAsset(
        char_id="lead_a",
        name_zh="A",
        reference_image_urls=["https://x/a.png"],
        canonical_image_url="https://x/a.png",
    )
    other = CharacterAsset(
        char_id="lead_b",
        name_zh="B",
        reference_image_urls=["https://x/b.png"],
        canonical_image_url="https://x/b.png",
    )
    locked = multi_character_lock(
        main=main, others=[other], prompt="两人对峙", aspect_ratio="9:16"
    )
    # Without a key the helper must NOT crash; it must return the main's
    # canonical so downstream Skylark still has a reference image.
    assert locked == "https://x/a.png"


# ============================================================================
# Repair router wiring — Drift B-1
# ============================================================================

def test_repair_router_wires_actual_class_names(monkeypatch):
    """All six routes must register without import errors after drift fix."""
    monkeypatch.setenv("FAL_API_KEY", "x")
    monkeypatch.setenv("HEDRA_API_KEY", "x")
    monkeypatch.setenv("RUNWAY_API_KEY", "x")
    monkeypatch.setenv("REPLICATE_API_TOKEN", "x")
    monkeypatch.setenv("OPENAI_API_KEY", "x")
    monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "x")
    monkeypatch.setenv("GOOGLE_ACCESS_TOKEN", "x")

    from src.shell4_qa_repair.run_qa import _build_default_router

    router = _build_default_router()
    # Phase B fix: previously every handler silently failed to import
    # because class names didn't exist. Now they should all wire.
    assert "face_drift" in router.routes
    assert "closeup_lipsync" in router.routes
    assert "costume_drift" in router.routes
    assert "cross_show_style" in router.routes
    assert "climax_enhance" in router.routes
    assert "god_tier" in router.routes


# ============================================================================
# Orchestrator v8 surface — bilingual + c2pa + filing wiring
# ============================================================================

def test_orchestrator_v8_emits_c2pa_filing_and_bilingual_artifacts(tmp_path):
    orch = PipelineOrchestratorV2(tmp_path, use_real_apis=False, genre="modern")
    result = orch.run(
        job_id=8,
        novel_excerpt="少女回到 17 岁，要改写父母的婚姻。这是完全原创的副本。" * 3,
        style="modern_cinematic",
        episodes=1,
        language="English",
    )
    art = result.step_artifacts
    step6 = art["steps"]["6"]
    # C2PA sidecar always emitted
    assert "c2pa_sidecar" in step6
    sidecar = json.loads(pathlib.Path(step6["c2pa_sidecar"]).read_text(encoding="utf-8"))
    assert sidecar["content_type"] == "ai_generated_video"

    # Bilingual subtitle wiring for language != Chinese
    assert step6.get("subtitle_bilingual") == "en"
    assert "subtitle" in step6

    # Filing autofill always emitted
    assert "filing" in art
    assert pathlib.Path(art["filing"]["md_path"]).exists()
    assert pathlib.Path(art["filing"]["checklist_path"]).exists()


def test_orchestrator_v8_normalizes_subtitle_language():
    assert PipelineOrchestratorV2._normalize_subtitle_lang("Chinese") == "zh"
    assert PipelineOrchestratorV2._normalize_subtitle_lang("English") == "en"
    assert PipelineOrchestratorV2._normalize_subtitle_lang("ja") == "ja"
    assert PipelineOrchestratorV2._normalize_subtitle_lang("") == "zh"


def test_orchestrator_v8_tags_fight_shot_routes(tmp_path, monkeypatch):
    """Storyboard shots with shot_type=fight should be tagged wan_2_2_animate."""
    monkeypatch.setenv("FORCE_MOCK_WAN_ANIMATE", "1")

    orch = PipelineOrchestratorV2(tmp_path, use_real_apis=False, genre="ancient")

    # Build minimal ep_list with a fight shot
    ep_list = [{
        "episode_id": "ep01",
        "title": "对决",
        "duration_seconds": 30,
        "characters_in_episode": ["lead_a"],
        "scenes_in_episode": ["sword_arena"],
        "shots": [
            {"shot_id": 1, "shot_type": "fight", "duration_s": 6.0,
             "subject_chars": ["lead_a"], "description": "拔剑斩妖"},
            {"shot_id": 2, "shot_type": "close_up", "duration_s": 3.0,
             "subject_chars": ["lead_a"], "description": "面部特写"},
        ],
    }]

    prompts = {"ep01": "古风武打"}
    shot_plan = {"ep01": ep_list[0]["shots"]}
    notes: list[str] = []

    def emit(*_a, **_k): ...

    rendered, _tids, all_shots = orch._step4_render(
        job_id=1, ep_list=ep_list, prompts=prompts, shot_plan=shot_plan,
        emit=emit, notes=notes,
    )
    routes = {s["shot_id"]: s["route"] for s in all_shots}
    assert routes[1] == "wan_2_2_animate"
    assert routes[2] == "skylark"
    assert rendered, "should have produced at least 1 rendered mp4"


# ============================================================================
# Wan-Animate top-level helper — mock-mode short-circuit
# ============================================================================

def test_wan_animate_helper_mock_returns_action_url(monkeypatch):
    monkeypatch.setenv("FORCE_MOCK_WAN_ANIMATE", "1")
    from src.shell3_skylark_engine.wan_animate import render_fight_shot

    out = render_fight_shot(
        character_image_url="https://x/a.png",
        action_video_url="https://x/action.mp4",
        prompt="斩",
    )
    assert out == "https://x/action.mp4"
