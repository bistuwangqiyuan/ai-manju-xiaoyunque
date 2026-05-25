"""Contract tests for `manju_agent_client.ManjuAgentClient`.

Goal:
  - Validate the *shape* of the public API (req_key constants, field map,
    submission validation, mock submit/wait round-trip) without hitting
    the real Volcengine endpoint.
  - PDF-pending: req_key + field names are placeholders until the user
    drops 3 PDFs in ``docs/volc-manju/``; these tests still pass because
    they exercise the abstract contract not the live wire.

Run::

    pytest -q tests/test_manju_agent_client.py
"""
from __future__ import annotations

import os
import pathlib
import sys

import pytest

_REPO = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO))

from src.shell3_skylark_engine.manju_agent_client import (  # noqa: E402
    MANJU_FIELDS,
    MANJU_REQ_KEY_SEEDANCE_FAST_720P_DEFAULT,
    MANJU_REQ_KEY_SEEDANCE_720P_DEFAULT,
    NARRATION_VALUES,
    RATIO_VALUES,
    STYLE_VALUES,
    ManjuAgentClient,
    ManjuResult,
    ManjuSubmission,
    is_manju_agent_enabled,
    is_mock_mode,
)


@pytest.fixture(autouse=True)
def _force_mock(monkeypatch: pytest.MonkeyPatch):
    """Every test runs in mock mode; never hit the real OpenAPI endpoint."""

    monkeypatch.setenv("FORCE_MOCK_MANJU_AGENT", "1")
    monkeypatch.delenv("MANJU_AGENT_MODE", raising=False)
    yield


# ---------------------------------------------------------------------------
# 1. constants + field map shape
# ---------------------------------------------------------------------------

def test_req_keys_are_nonempty_strings():
    assert isinstance(MANJU_REQ_KEY_SEEDANCE_FAST_720P_DEFAULT, str)
    assert MANJU_REQ_KEY_SEEDANCE_FAST_720P_DEFAULT
    assert MANJU_REQ_KEY_SEEDANCE_720P_DEFAULT


def test_fields_map_covers_all_logical_keys():
    expected = {
        "script_text", "script_url", "style", "ratio", "narration",
        "episode_duration", "episode_count", "voice", "watermark", "task_id",
    }
    assert expected.issubset(MANJU_FIELDS.keys()), (
        f"missing logical keys: {expected - set(MANJU_FIELDS.keys())}"
    )
    for k, v in MANJU_FIELDS.items():
        assert isinstance(v, str) and v.strip(), f"empty mapping for {k!r}"


# ---------------------------------------------------------------------------
# 2. enum value sanity
# ---------------------------------------------------------------------------

def test_enum_value_lists_have_expected_members():
    assert {"2d", "3d", "real"}.issubset(set(STYLE_VALUES))
    assert {"16:9", "9:16"}.issubset(set(RATIO_VALUES))
    assert "auto" in NARRATION_VALUES


# ---------------------------------------------------------------------------
# 3. Submission validation
# ---------------------------------------------------------------------------

def test_submission_requires_text_or_url():
    with pytest.raises(ValueError, match="script_text or script_url"):
        ManjuSubmission().validate()


def test_submission_rejects_invalid_style():
    s = ManjuSubmission(script_text="abc", style="weird")
    with pytest.raises(ValueError, match="style="):
        s.validate()


def test_submission_rejects_invalid_ratio():
    s = ManjuSubmission(script_text="abc", style="real", ratio="3:5")
    with pytest.raises(ValueError, match="ratio="):
        s.validate()


def test_submission_to_payload_uses_field_map():
    sub = ManjuSubmission(
        script_text="某天, 月光下少年遇见青鸟. " * 50,
        style="real",
        ratio="9:16",
        narration="auto",
        episode_duration_sec=150,
        episode_count=5,
        voice="female_warm",
    )
    payload = sub.to_payload(req_key="probe_req_key")
    # req_key always present
    assert payload["req_key"] == "probe_req_key"
    # PDF-mapped field names actually used
    assert MANJU_FIELDS["script_text"] in payload
    assert MANJU_FIELDS["style"] in payload
    assert MANJU_FIELDS["ratio"] in payload
    assert payload[MANJU_FIELDS["episode_count"]] == 5
    assert payload[MANJU_FIELDS["voice"]] == "female_warm"


def test_submission_episode_count_bounds():
    s = ManjuSubmission(script_text="x", episode_count=-1)
    with pytest.raises(ValueError, match="episode_count"):
        s.validate()


# ---------------------------------------------------------------------------
# 4. Mock client: submit + wait_for_completion + archive
# ---------------------------------------------------------------------------

def test_is_mock_mode_when_env_set():
    assert is_mock_mode() is True


def test_is_manju_agent_enabled_off_by_default():
    assert is_manju_agent_enabled() is False


def test_is_manju_agent_enabled_when_env_set(monkeypatch):
    monkeypatch.setenv("MANJU_AGENT_MODE", "1")
    assert is_manju_agent_enabled() is True


def test_mock_submit_returns_task_id():
    c = ManjuAgentClient(mock=True)
    tid = c.submit_script(
        novel_text="月光如水, 少年抬眼, 看见一只青色的鸟.",
        style="real", ratio="9:16",
    )
    assert tid.startswith("mock-manju-")
    assert len(tid) > len("mock-manju-")


def test_mock_query_task_returns_done_with_episodes():
    c = ManjuAgentClient(mock=True)
    data = c.query_task("mock-task-x")
    assert data["status"] == "done"
    assert isinstance(data["episodes"], list) and len(data["episodes"]) >= 1
    ep0 = data["episodes"][0]
    assert "video_url" in ep0


def test_mock_wait_for_completion_returns_result(tmp_path, monkeypatch):
    """Patch storage.archive_url so the test doesn't hit real network."""

    class _NopeStore:
        def archive_url(self, key, url, timeout=30):
            class _Obj:
                path = str(tmp_path / pathlib.Path(key).name)
                public_url = url
                sha256 = "x" * 64
                size_bytes = 1
            (tmp_path / pathlib.Path(key).name).write_bytes(b"\x00")
            return _Obj()

        def put_bytes(self, key, payload, public=False):
            raise NotImplementedError
        def put_file(self, key, src_path, public=False):
            raise NotImplementedError

    c = ManjuAgentClient(mock=True, storage=_NopeStore(),
                        poll_interval_seconds=0.01, timeout_seconds=2.0)
    result = c.wait_for_completion("mock-task-abc", ep_id="probe")
    assert isinstance(result, ManjuResult)
    assert result.status == "done"
    assert len(result.episodes) >= 1
    assert result.episodes[0].archived_path  # archived via _NopeStore


def test_render_script_end_to_end_mock(tmp_path):
    """Smoke the convenience wrapper render_script (submit+wait)."""

    class _DummyStore:
        def archive_url(self, key, url, timeout=30):
            class _Obj:
                path = str(tmp_path / pathlib.Path(key).name)
                public_url = url
                sha256 = "y" * 64
                size_bytes = 1
            (tmp_path / pathlib.Path(key).name).write_bytes(b"\x01")
            return _Obj()

        def put_bytes(self, key, payload, public=False):
            raise NotImplementedError
        def put_file(self, key, src_path, public=False):
            raise NotImplementedError

    c = ManjuAgentClient(mock=True, storage=_DummyStore(),
                        poll_interval_seconds=0.01, timeout_seconds=2.0)
    r = c.render_script(
        novel_text="少年与青鸟的故事. " * 100,
        ep_id="ep",
        style="real",
        ratio="9:16",
        episode_count=3,
    )
    assert r.task_id.startswith("mock-manju-")
    assert len(r.episodes) >= 1
    # Each archived path should have been written by the dummy store
    for ep in r.episodes:
        assert ep.archived_path
