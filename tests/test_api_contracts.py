"""Phase D — API request-body contract tests for every external provider.

The tests monkeypatch ``urllib.request.urlopen`` to capture each provider's
outbound request body and assert that the JSON it sends matches the
"Official body" recorded in ``docs/api-contracts-2026-05.md``.

These tests run with no network access and no real API keys. They catch
drift in request shape long before a real call would fail in production.
"""
from __future__ import annotations

import io
import json
import os
import pathlib
from contextlib import contextmanager
from typing import Any

import pytest

_REPO = pathlib.Path(__file__).resolve().parents[1]


class _Captured:
    """Records each outbound urllib request body so tests can assert on it."""

    def __init__(self) -> None:
        self.requests: list[dict[str, Any]] = []

    def append(self, req, body_bytes: bytes) -> None:
        headers = {k.lower(): v for k, v in req.header_items()}
        try:
            body = json.loads(body_bytes.decode("utf-8")) if body_bytes else {}
        except Exception:
            body = {"_raw": body_bytes[:200].decode("utf-8", errors="ignore")}
        self.requests.append({
            "url": req.full_url,
            "method": req.get_method(),
            "headers": headers,
            "body": body,
        })


def _make_fake_urlopen(captured: _Captured, response_body: dict | bytes):
    """Build a fake urlopen that records every Request and returns a canned response."""

    @contextmanager
    def _ctx(req, *args, **kwargs):
        if hasattr(req, "data") and req.data:
            captured.append(req, req.data)
        elif hasattr(req, "full_url"):
            captured.append(req, b"")
        # Decide response format
        if isinstance(response_body, (bytes, bytearray)):
            yield io.BytesIO(bytes(response_body))
        else:
            yield io.BytesIO(json.dumps(response_body).encode("utf-8"))

    return _ctx


@pytest.fixture()
def env(monkeypatch):
    """Provide harmless test keys + force mock for self-mock-aware modules."""
    monkeypatch.setenv("VOLC_ACCESS_KEY", "TEST_AK")
    monkeypatch.setenv("VOLC_SECRET_KEY", "TEST_SK")
    monkeypatch.setenv("VOLC_ARK_API_KEY", "TEST_ARK")
    monkeypatch.setenv("DOUBAO_API_KEY", "TEST_DOUBAO")
    monkeypatch.setenv("DOUBAO_TTS_APPID", "tts-app")
    monkeypatch.setenv("DOUBAO_TTS_TOKEN", "tts-token")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "TEST_ANTHROPIC")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "TEST_DEEPSEEK")
    monkeypatch.setenv("GEMINI_API_KEY", "TEST_GEMINI")
    monkeypatch.setenv("ELEVENLABS_API_KEY", "TEST_ELEVENLABS")
    monkeypatch.setenv("FAL_API_KEY", "TEST_FAL")
    monkeypatch.setenv("REPLICATE_API_TOKEN", "TEST_REPLICATE")
    monkeypatch.setenv("HEDRA_API_KEY", "TEST_HEDRA")
    monkeypatch.setenv("RUNWAY_API_KEY", "TEST_RUNWAY")
    monkeypatch.setenv("DASHSCOPE_API_KEY", "TEST_DASHSCOPE")
    monkeypatch.setenv("MINIMAX_API_KEY", "TEST_MINIMAX")
    monkeypatch.setenv("OPENAI_API_KEY", "TEST_OPENAI")
    monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "test-project")
    monkeypatch.setenv("GOOGLE_ACCESS_TOKEN", "test-google-token")
    # Make sure global "mock everything" defaults don't short-circuit the
    # specific module call we are exercising in each test.
    monkeypatch.delenv("FORCE_MOCK_THEME", raising=False)
    monkeypatch.delenv("FORCE_MOCK_NOVELTY", raising=False)
    monkeypatch.delenv("FORCE_MOCK_MARKETING", raising=False)
    monkeypatch.delenv("FORCE_MOCK_CONTINUATION", raising=False)
    monkeypatch.delenv("FORCE_MOCK_TRANSLATE", raising=False)
    monkeypatch.delenv("FORCE_MOCK_WAN_ANIMATE", raising=False)
    monkeypatch.delenv("FORCE_MOCK_TTS_MINIMAX", raising=False)
    return monkeypatch


# ============================================================================
# Skylark Agent 2.0 — official req_key + AIGC meta on query
# ============================================================================

def test_skylark_submit_body_uses_official_req_key(env):
    """Skylark submit must use the single canonical req_key + ratio enum."""
    import urllib.request

    from src.shell3_skylark_engine.client import (
        AigcMeta,
        EpisodeRequest,
        ReferencePack,
        SKYLARK_REQ_KEY,
        SkylarkAgentV2WithRefClient,
    )

    captured = _Captured()
    env.setattr(
        urllib.request,
        "urlopen",
        _make_fake_urlopen(
            captured,
            {"code": 10000, "data": {"task_id": "task-test-123"}},
        ),
    )

    client = SkylarkAgentV2WithRefClient(aigc_meta=AigcMeta(producer_id="ep01"))
    task_id = client.submit(
        EpisodeRequest(
            prompt="少女白衣立于古寺檐下，眉间一点朱砂。",
            references=ReferencePack(character_images=["https://x/c1.png"]),
            ratio="9:16",
            duration="40～60s",
            language="Chinese",
            enable_watermark=False,
        )
    )

    assert task_id == "task-test-123"
    body = captured.requests[0]["body"]
    assert body["req_key"] == SKYLARK_REQ_KEY == "pippit_iv2v_v20_cvtob_with_vinput"
    assert body["ratio"] == "9:16"
    assert body["duration"] == "40～60s"
    assert body["enable_watermark"] is False
    assert body["img_url_list"] == ["https://x/c1.png"]


def test_skylark_query_embeds_aigc_meta(env):
    """The Skylark query body must include req_json with aigc_meta block."""
    import urllib.request

    from src.shell3_skylark_engine.client import (
        AigcMeta,
        SKYLARK_REQ_KEY,
        SkylarkAgentV2WithRefClient,
    )

    captured = _Captured()
    env.setattr(
        urllib.request,
        "urlopen",
        _make_fake_urlopen(
            captured,
            {"code": 10000, "data": {"status": "in_queue"}},
        ),
    )

    client = SkylarkAgentV2WithRefClient(
        aigc_meta=AigcMeta(producer_id="ep01-uid", content_producer="USCC18CHARID"),
        poll_interval_seconds=0.0,
        timeout_seconds=0.0,
    )
    _ = client._query("task-test-123")  # noqa: SLF001
    body = captured.requests[0]["body"]
    assert body["req_key"] == SKYLARK_REQ_KEY
    assert body["task_id"] == "task-test-123"
    aigc = json.loads(body["req_json"])
    assert aigc["aigc_meta"]["producer_id"] == "ep01-uid"
    assert aigc["aigc_meta"]["content_producer"] == "USCC18CHARID"


# ============================================================================
# Doubao Seed-TTS 2.0 ICL — body shape + auth header
# ============================================================================

def test_doubao_tts_request_body(tmp_path, env):
    import base64
    import urllib.request

    from src.shell5_post_production.tts_doubao_icl import DoubaoIclClient, TTSRequest

    captured = _Captured()
    env.setattr(
        urllib.request,
        "urlopen",
        _make_fake_urlopen(
            captured,
            {"code": 3000, "data": base64.b64encode(b"FAKEMP3").decode()},
        ),
    )

    client = DoubaoIclClient()
    client.synth(
        TTSRequest(text="月光低垂，少年抬眼。", voice_type="voice_v1", emotion="sad"),
        tmp_path / "out.mp3",
    )
    req = captured.requests[0]
    body = req["body"]
    assert body["app"]["cluster"] == "volcano_icl"
    assert body["request"]["text"].endswith("少年抬眼。")
    assert body["audio"]["encoding"] == "mp3"
    assert body["audio"]["emotion"] == "sad"
    # Auth header includes the Volcengine 「Bearer; 」 convention with semicolon
    assert req["headers"]["authorization"].startswith("Bearer; tts-token")


# ============================================================================
# Anthropic Claude — body uses Opus 4.7 by default after v8 drift fix
# ============================================================================

def test_anthropic_default_model_is_opus_4_7(env):
    import urllib.request

    from src.shell5_post_production.subtitle_translate import _via_anthropic
    from src.shell5_post_production.ass_subtitle import AssLine  # noqa: F401

    captured = _Captured()
    env.setattr(
        urllib.request,
        "urlopen",
        _make_fake_urlopen(
            captured,
            {"content": [{"type": "text", "text": "Moon falls<<<SEP>>>Boy looks up"}]},
        ),
    )

    out = _via_anthropic(["月光低垂", "少年抬眼"], "English")
    assert out == ["Moon falls", "Boy looks up"]
    body = captured.requests[0]["body"]
    assert body["model"] == "claude-opus-4-7-20260413", (
        f"v8 drift B-2 regressed: subtitle_translate default model is {body['model']!r}"
    )


def test_marketing_copy_uses_opus_4_7(env):
    import urllib.request

    from src.shell5_post_production.marketing_copy import generate_marketing_copy

    captured = _Captured()
    env.setattr(
        urllib.request,
        "urlopen",
        _make_fake_urlopen(
            captured,
            {
                "content": [
                    {"type": "text", "text": json.dumps({
                        "title": "T",
                        "summary": "S",
                        "hook_copy": "H",
                        "hashtags": ["#A", "#B", "#C", "#D", "#E"],
                    })}
                ]
            },
        ),
    )

    result = generate_marketing_copy(
        title="测试", synopsis="一个原创短剧的开端。", genre="ancient", language="Chinese"
    )
    assert result["title"] == "T"
    assert captured.requests, "Anthropic was never called"
    body = captured.requests[0]["body"]
    assert body["model"] == "claude-opus-4-7-20260413"


# ============================================================================
# DeepSeek V4-Pro — body shape (event extraction)
# ============================================================================

def test_deepseek_v4_pro_body(env):
    import urllib.request

    from src.shell1_screenwriter.extract_events import EventExtractor

    captured = _Captured()
    env.setattr(
        urllib.request,
        "urlopen",
        _make_fake_urlopen(
            captured,
            {
                "choices": [
                    {
                        "message": {
                            "content": json.dumps({
                                "events": [
                                    {
                                        "id": "1",
                                        "name": "兰若寺夜遇",
                                        "summary": "书生进寺",
                                        "hook_score": 5,
                                        "visual_keywords": ["月光", "古寺"],
                                        "act": "第一幕 投宿兰若",
                                    }
                                ]
                            })
                        }
                    }
                ]
            },
        ),
    )

    extractor = EventExtractor()
    events = list(extractor.extract("聂小倩原文 ..."))
    assert events[0].name == "兰若寺夜遇"
    body = captured.requests[0]["body"]
    assert body["model"] == "deepseek-v4-pro"
    assert body["response_format"] == {"type": "json_object"}


# ============================================================================
# ElevenLabs Multilingual v3 — body + auth header
# ============================================================================

def test_elevenlabs_multilingual_tts(tmp_path, env):
    import urllib.request

    from src.shell5_post_production.tts_elevenlabs_intl import (
        ElevenLabsMultilingualClient,
        IntlTTSRequest,
    )

    captured = _Captured()
    env.setattr(
        urllib.request,
        "urlopen",
        _make_fake_urlopen(captured, b"FAKEAUDIOBYTES"),
    )

    client = ElevenLabsMultilingualClient()
    client.synth(
        IntlTTSRequest(text="Moon falls.", language="en"),
        tmp_path / "out.mp3",
    )
    req = captured.requests[0]
    assert req["url"].startswith("https://api.elevenlabs.io/v1/text-to-speech/")
    assert req["headers"]["xi-api-key"] == "TEST_ELEVENLABS"
    body = req["body"]
    assert body["model_id"] == "eleven_multilingual_v3"


# ============================================================================
# Wan 2.2-Animate — new in v8 (Gap C-1)
# ============================================================================

def test_wan_animate_request_body(env):
    import urllib.request

    from src.shell3_skylark_engine.wan_animate import (
        WAN_ANIMATE_MODEL,
        WanAnimateClient,
        WanAnimateRequest,
    )

    captured = _Captured()
    # First response: submit; second response: poll (SUCCEEDED).
    responses = iter([
        {"output": {"task_id": "wan-task-1"}},
        {"output": {"task_status": "SUCCEEDED", "video_url": "https://x/wan.mp4"}},
    ])

    @contextmanager
    def fake(req, *a, **k):
        if req.data:
            captured.append(req, req.data)
        else:
            captured.append(req, b"")
        yield io.BytesIO(json.dumps(next(responses)).encode("utf-8"))

    env.setattr(urllib.request, "urlopen", fake)

    client = WanAnimateClient(poll_interval=0.0, timeout=5.0)
    url = client.render(
        WanAnimateRequest(
            character_image_url="https://x/char.png",
            action_video_url="https://x/action.mp4",
            prompt="挥剑斩妖",
            duration_seconds=6,
        )
    )
    assert url == "https://x/wan.mp4"
    submit = captured.requests[0]
    assert submit["body"]["model"] == WAN_ANIMATE_MODEL == "wan-2.2-animate"
    assert submit["body"]["parameters"]["aspect_ratio"] == "9:16"
    assert submit["body"]["parameters"]["resolution"] == "720p"
    assert submit["headers"]["x-dashscope-async"] == "enable"


# ============================================================================
# MiniMax Speech 2.5 HD — new in v8 (Gap C-7)
# ============================================================================

def test_minimax_speech_2_5_body(tmp_path, env):
    import base64
    import urllib.request

    from src.shell5_post_production.tts_minimax import (
        MINIMAX_TTS_MODEL,
        MinimaxTtsClient,
        MinimaxTtsRequest,
    )

    captured = _Captured()
    env.setattr(
        urllib.request,
        "urlopen",
        _make_fake_urlopen(
            captured,
            {"data": {"audio": base64.b64encode(b"FAKEMP3").decode()}},
        ),
    )

    client = MinimaxTtsClient()
    client.synth(
        MinimaxTtsRequest(text="月下相思", emotion="sad"),
        tmp_path / "minimax.mp3",
    )
    body = captured.requests[0]["body"]
    assert body["model"] == MINIMAX_TTS_MODEL == "speech-2.5-hd"
    assert body["voice_setting"]["emotion"] == "sad"
    assert body["audio_setting"]["format"] == "mp3"
    assert body["audio_setting"]["sample_rate"] == 32000
