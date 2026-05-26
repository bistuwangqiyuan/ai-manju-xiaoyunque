"""Phase 4 — visual asset modules."""
from __future__ import annotations

import pathlib

import pytest


def test_three_view_seed_is_deterministic():
    from src.visual import three_view

    s1 = three_view.derive_seed("林清", "ancient_3d_guoman")
    s2 = three_view.derive_seed("林清", "ancient_3d_guoman")
    s3 = three_view.derive_seed("林清", "modern_cinematic")
    assert s1 == s2
    assert s1 != s3

    sheet = three_view.build_three_view_prompts(
        character_name="林清",
        character_description="少年剑客，黑发飘逸",
        style_id="ancient_3d_guoman",
        style_lock_prompt="cinematic, soft lighting",
    )
    assert sheet.character_name == "林清"
    assert sheet.seed == s1
    assert len(sheet.views) == 3
    assert {v["view"] for v in sheet.views} == {"front", "three_quarter", "back"}
    assert all(v["seed"] == s1 for v in sheet.views)
    assert all(v["group_id"] == "林清__sheet" for v in sheet.views)


def test_expression_router_routes_correctly():
    from src.visual import expression_router

    plan = expression_router.route("angry", intensity=5)
    assert plan.shot_size == "extreme close-up"
    assert plan.camera_angle == "slight low angle"
    assert "furrowed brow" in plan.face_prompt

    plan = expression_router.route("joyful", intensity=1)
    assert plan.shot_size == "long shot"

    plan = expression_router.route("sad", intensity=3)
    assert plan.camera_angle == "slight high angle"


def test_expression_router_full_prompt():
    from src.visual import expression_router

    plan = expression_router.route("loving", intensity=4)
    prompt = expression_router.build_full_prompt(
        base_character_prompt="林清，黑发剑客",
        plan=plan,
        style_lock="ancient ink wash",
        scene_setting="月光下的院子",
    )
    assert "林清" in prompt
    assert "close-up" in prompt
    assert "月光" in prompt


def test_pose_extract_classify_stand():
    from src.visual import pose_extract

    # Build a synthetic record where head is well above hips
    kp = [[0.5, 0.10, 0, 1.0]] * 33  # init
    kp[0]  = [0.5, 0.10, 0, 1.0]    # head
    kp[23] = [0.5, 0.50, 0, 1.0]    # left hip
    kp[24] = [0.5, 0.50, 0, 1.0]    # right hip
    kp[25] = [0.5, 0.65, 0, 1.0]    # left knee
    kp[26] = [0.5, 0.65, 0, 1.0]    # right knee
    kp[27] = [0.5, 0.90, 0, 1.0]    # left ankle
    kp[28] = [0.5, 0.90, 0, 1.0]    # right ankle
    rec = pose_extract.PoseRecord(image_path="x", keypoints=kp)
    assert pose_extract.classify_pose(rec) == "stand"

    # Sitting: knees near hip vertical
    kp_sit = [list(p) for p in kp]
    kp_sit[25] = [0.5, 0.52, 0, 1.0]
    kp_sit[26] = [0.5, 0.52, 0, 1.0]
    rec2 = pose_extract.PoseRecord(image_path="x", keypoints=kp_sit)
    assert pose_extract.classify_pose(rec2) == "sit"


def test_costume_climate_atmospheres():
    from src.visual import costume_climate

    adj = costume_climate.adjust(base_costume_id="ancient_robe", atmosphere="battle")
    assert "armoured" in adj.color_tweak
    assert "sword" in adj.accessories

    merged = costume_climate.merge_into_prompt(
        "a brave warrior", base_costume_id="ancient_robe", atmosphere="winter"
    )
    assert "ancient_robe" in merged
    assert "fur" in merged or "layered" in merged


def test_scene_search_index_persistence(tmp_path):
    try:
        from PIL import Image  # type: ignore
    except Exception:
        pytest.skip("Pillow not installed")
    from src.visual.scene_search import SceneIndex

    img1 = tmp_path / "scene_a.png"
    img2 = tmp_path / "scene_b.png"
    Image.new("RGB", (32, 32), (200, 50, 50)).save(img1)
    Image.new("RGB", (32, 32), (50, 50, 200)).save(img2)

    idx = SceneIndex(tmp_path / "idx.json")
    idx.add(scene_id="scn1", image_path=img1, atmosphere="battle", tags=["red"])
    idx.add(scene_id="scn2", image_path=img2, atmosphere="tranquil", tags=["blue"])

    res = idx.search_image(img1, top_k=2)
    assert res
    assert res[0][0].scene_id == "scn1"
    assert res[0][1] > res[1][1]

    # round-trip via fresh instance
    idx2 = SceneIndex(tmp_path / "idx.json")
    assert len(idx2) == 2

    # text query with atmosphere filter
    res2 = idx2.search_text("a tranquil garden", atmosphere="tranquil", top_k=5)
    assert all(r[0].atmosphere == "tranquil" for r in res2)


def test_atmosphere_inferer():
    from src.visual import atmosphere_inferer

    a = atmosphere_inferer.infer("两人激战厮杀，刀光剑影。")
    assert a.atmosphere == "battle"
    assert a.confidence > 0.4

    a2 = atmosphere_inferer.infer("月光洒在湖面，万籁俱寂。")
    assert a2.atmosphere == "tranquil"

    a3 = atmosphere_inferer.infer("")
    assert a3.atmosphere == "tranquil"


def test_shot_size_coupler_climax_promotes_to_closeup():
    from src.visual import shot_size_coupler

    item = shot_size_coupler.plan_shot(
        emotion_intensity=5, atmosphere="tense", n_characters=1, is_climax=True)
    assert item.shot_size == "extreme_closeup"
    assert item.camera_movement == "push-in"
    assert item.angle == "low"

    item_crowd = shot_size_coupler.plan_shot(
        emotion_intensity=3, atmosphere="festive", n_characters=7)
    assert item_crowd.shot_size == "extreme_long"
    assert item_crowd.camera_movement == "slow dolly"


def test_shot_size_coupler_avoids_back_to_back_closeups():
    from src.visual import shot_size_coupler
    item = shot_size_coupler.plan_shot(
        emotion_intensity=5, atmosphere="tense", n_characters=1,
        prev_shot_size="extreme_closeup")
    assert item.shot_size == "medium_closeup"
