"""Contract tests for the **official** 4-stage Manju Agent API surface.

These tests pin the new req_key constants and payload shapes to the
official docs (volcengine.com/docs/85621/238985x + 240708x).  All tests
run fully offline against mock-mode or hand-built fixtures.

Run::

    pytest -q tests/test_manju_official_contract.py
"""
from __future__ import annotations

import json
import pathlib
import sys

import pytest

_REPO = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO))

from src.shell3_skylark_engine.manju_agent_client import (  # noqa: E402
    MANJU_ACTION_QUERY,
    MANJU_ACTION_SUBMIT,
    MANJU_HOST,
    MANJU_REGION,
    MANJU_REQ_KEY_MATERIAL_DESIGN,
    MANJU_REQ_KEY_SCRIPT_ANALYSIS,
    MANJU_REQ_KEY_VIDEO_COMPOSE,
    MANJU_REQ_KEY_VIDEO_GEN_FAST,
    MANJU_REQ_KEY_VIDEO_GEN_STD,
    MANJU_REQ_KEY_VIDEO_COMPOSE_STD,
    MANJU_SERVICE,
    MANJU_VERSION,
    ManjuSubmission,
    _extract_episode_ids,
    _parse_resp_data,
    _verify_shot_statuses,
    ManjuAgentError,
    normalize_ratio,
    style_to_visual_style,
)


# ---------------------------------------------------------------------------
# 1. Official req_key constants
# ---------------------------------------------------------------------------

def test_official_req_keys_locked_to_docs():
    """官方实测固定值, 不允许漂移."""
    assert MANJU_REQ_KEY_SCRIPT_ANALYSIS == "pippit_shortplay_cvtob_script_analysis"
    assert MANJU_REQ_KEY_MATERIAL_DESIGN == "pippit_shortplay_cvtob_material_design"
    assert MANJU_REQ_KEY_VIDEO_GEN_FAST == "pippit_shortplay_cvtob_video_generate_fast720p"
    assert MANJU_REQ_KEY_VIDEO_COMPOSE == "pippit_shortplay_cvtob_video_compose_fast720p"


def test_openapi_endpoint_pins_to_official_host():
    assert MANJU_HOST == "visual.volcengineapi.com"
    assert MANJU_REGION == "cn-north-1"
    assert MANJU_SERVICE == "cv"
    assert MANJU_VERSION == "2022-08-31"
    assert MANJU_ACTION_SUBMIT == "CVSync2AsyncSubmitTask"
    assert MANJU_ACTION_QUERY == "CVSync2AsyncGetResult"


# ---------------------------------------------------------------------------
# 2. Submission → script-analysis payload (real wire fields)
# ---------------------------------------------------------------------------

def test_script_analysis_payload_uses_official_field_names():
    sub = ManjuSubmission(
        script_url="https://tos.example/x.docx",
        style="real",
        ratio="9:16",
        file_type="docx",
        file_name="x.docx",
    )
    p = sub.to_script_analysis_payload()
    # required wire fields per docs/85621/2389851
    assert p["req_key"] == MANJU_REQ_KEY_SCRIPT_ANALYSIS
    assert p["visual_style"] == "真人写实, 电视风格, 高清画质"
    assert p["video_ratio"] == "9:16"
    assert p["file_url"] == "https://tos.example/x.docx"
    assert p["file_type"] == "docx"
    assert p["file_name"] == "x.docx"
    # 内部字段不应出现在官方 payload
    assert "narration_mode" not in p
    assert "episode_count" not in p


def test_script_analysis_requires_url_not_text():
    """官方 API 不接受裸文本, 必须先上传到公网 URL."""
    sub = ManjuSubmission(script_text="月光如水...")
    with pytest.raises(ValueError, match="script_url"):
        sub.to_script_analysis_payload()


def test_style_to_visual_style_maps_high_level_keywords():
    assert "2D" in style_to_visual_style("2d")
    assert "3D" in style_to_visual_style("3d")
    assert "真人写实" in style_to_visual_style("real")
    # passthrough for explicit official strings
    assert style_to_visual_style("2D, 国风, 平涂") == "2D, 国风, 平涂"


def test_normalize_ratio_falls_back_to_official_values():
    assert normalize_ratio("16:9") == "16:9"
    assert normalize_ratio("9:16") == "9:16"
    assert normalize_ratio("4:3") == "16:9"
    assert normalize_ratio("3:4") == "9:16"
    assert normalize_ratio("garbage") == "9:16"


# ---------------------------------------------------------------------------
# 3. resp_data parsing
# ---------------------------------------------------------------------------

def test_parse_resp_data_handles_json_string():
    payload = {"assets_id": "ark_x", "thread_id": "ark_y"}
    parsed = _parse_resp_data(json.dumps(payload))
    assert parsed["assets_id"] == "ark_x"


def test_parse_resp_data_handles_dict():
    assert _parse_resp_data({"a": 1}) == {"a": 1}


def test_parse_resp_data_invalid_json_returns_empty():
    assert _parse_resp_data("not json") == {}


def test_extract_episode_ids_sorted_numerically():
    resp = {
        "script_detail": {
            "EpisodeAssets": [
                {"EpisodeID": "3"},
                {"EpisodeID": "1"},
                {"EpisodeID": "10"},
                {"EpisodeID": "2"},
            ]
        }
    }
    assert _extract_episode_ids(resp) == ["1", "2", "3", "10"]


def test_extract_episode_ids_empty_when_no_episodes():
    assert _extract_episode_ids({}) == []
    assert _extract_episode_ids({"script_detail": {}}) == []


# ---------------------------------------------------------------------------
# 4. Shot status verification (video_generate phase)
# ---------------------------------------------------------------------------

def test_verify_shot_statuses_passes_when_all_done():
    resp = {
        "storyboard_detail": [{
            "EpisodeID": "1",
            "Shots": [
                {"ShotID": "S1", "Status": 3},
                {"ShotID": "S2", "Status": 3},
            ],
        }]
    }
    _verify_shot_statuses(resp, "1")  # should not raise


def test_verify_shot_statuses_raises_on_failure():
    resp = {
        "storyboard_detail": [{
            "EpisodeID": "1",
            "Shots": [
                {"ShotID": "S1", "Status": 3},
                {"ShotID": "S2", "Status": 4},
                {"ShotID": "S3", "Status": 5},
            ],
        }]
    }
    with pytest.raises(ManjuAgentError, match="not done"):
        _verify_shot_statuses(resp, "1")


def test_verify_shot_statuses_skips_other_episodes():
    resp = {
        "storyboard_detail": [{
            "EpisodeID": "999",
            "Shots": [{"ShotID": "S1", "Status": 4}],
        }]
    }
    # Episode 1 has no shots in this resp, so 0-failure → pass
    _verify_shot_statuses(resp, "1")


# ---------------------------------------------------------------------------
# 5. Standard 720p req_keys (fallback)
# ---------------------------------------------------------------------------

def test_standard_720p_req_keys_distinct_from_fast():
    assert MANJU_REQ_KEY_VIDEO_GEN_STD != MANJU_REQ_KEY_VIDEO_GEN_FAST
    assert MANJU_REQ_KEY_VIDEO_COMPOSE_STD != MANJU_REQ_KEY_VIDEO_COMPOSE
    assert "fast720p" in MANJU_REQ_KEY_VIDEO_GEN_FAST
    assert "fast720p" not in MANJU_REQ_KEY_VIDEO_GEN_STD
