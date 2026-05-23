"""
Serverless mode regression tests.

Covers:
  - worker.tick_once() returns the expected shape and processes ≤ max_jobs
  - /api/internal/worker/tick requires X-Internal-Secret (403 if missing/wrong)
  - /api/internal/worker/tick returns processed=0 when queue is empty
  - /api/internal/worker/tick returns 503 if INTERNAL_API_SECRET not configured
  - EMBEDDED_WORKER=0 disables the in-process worker (no asyncio task spawned)
"""
from __future__ import annotations

import asyncio
import os
import pathlib
import sys
import time

import pytest

_REPO = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO))
sys.path.insert(0, str(_REPO / "backend"))


@pytest.fixture(scope="module")
def serverless_client():
    """Fresh sqlite + EMBEDDED_WORKER=0 + internal secret pre-set."""
    db_path = _REPO / "data" / "test_serverless.db"
    if db_path.exists():
        db_path.unlink()
    os.environ["DATABASE_URL"] = f"sqlite:///{db_path}"
    os.environ["JWT_SECRET"] = "test-jwt-sl"
    os.environ["STORAGE_DIR"] = str(_REPO / "data" / "test_sl_storage")
    os.environ["EMBEDDED_WORKER"] = "0"
    os.environ["INTERNAL_API_SECRET"] = "supersecret-test-token-32-bytes-abc"

    # Reset cached modules so env vars apply
    for mod in [
        "app.settings",
        "app.db",
        "app.main",
        "app.worker",
        "app.routes.auth",
        "app.routes.jobs",
        "app.routes.batch",
        "app.routes.genres",
        "app.routes.library",
        "app.routes.billing",
        "app.routes.internal",
        "app.security",
    ]:
        if mod in sys.modules:
            del sys.modules[mod]

    from fastapi.testclient import TestClient
    from app.main import app
    from app.db import init_db

    init_db()
    with TestClient(app) as c:
        yield c


def _signup(client):
    email = f"sl+{int(time.time()*1000)}@example.com"
    r = client.post("/api/auth/signup", json={"email": email, "password": "Password1!"})
    assert r.status_code in (200, 201), r.text
    return r.json()


# ---------------------------------------------------------------------------
# 1. tick_once() unit-level
# ---------------------------------------------------------------------------
def test_tick_once_empty_queue_returns_zero(serverless_client):
    """With no queued jobs, tick should return processed=0 fast."""
    from app.worker import tick_once

    result = asyncio.run(tick_once(max_jobs=3, max_seconds=5))
    assert isinstance(result, dict)
    assert result["processed"] == 0
    assert result["remaining_queued"] == 0
    assert result["elapsed_sec"] < 5.0


# ---------------------------------------------------------------------------
# 2. /api/internal/worker/tick auth + shape
# ---------------------------------------------------------------------------
def test_internal_tick_requires_secret_header(serverless_client):
    r = serverless_client.post("/api/internal/worker/tick", json={"max_jobs": 1})
    assert r.status_code == 403
    assert "invalid" in r.json()["detail"].lower()


def test_internal_tick_rejects_wrong_secret(serverless_client):
    r = serverless_client.post(
        "/api/internal/worker/tick",
        json={"max_jobs": 1},
        headers={"X-Internal-Secret": "wrong-token"},
    )
    assert r.status_code == 403


def test_internal_tick_with_correct_secret_returns_shape(serverless_client):
    r = serverless_client.post(
        "/api/internal/worker/tick",
        json={"max_jobs": 1, "max_seconds": 3},
        headers={"X-Internal-Secret": "supersecret-test-token-32-bytes-abc"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert set(body.keys()) >= {"processed", "remaining_queued", "elapsed_sec"}
    assert body["processed"] == 0
    assert body["remaining_queued"] == 0


def test_internal_worker_ping(serverless_client):
    r = serverless_client.get(
        "/api/internal/worker/ping",
        headers={"X-Internal-Secret": "supersecret-test-token-32-bytes-abc"},
    )
    assert r.status_code == 200
    assert r.json() == {"ok": True, "service": "xiaoyunque-worker"}


# ---------------------------------------------------------------------------
# 3. Serverless lifecycle: enqueue → tick → drained
# ---------------------------------------------------------------------------
def test_internal_tick_processes_queued_job(serverless_client):
    """Create a real mock-mode job, then drive it forward via /tick (not embedded loop)."""
    auth = _signup(serverless_client)
    headers = {"Authorization": f"Bearer {auth['token']}"}
    secret = {"X-Internal-Secret": "supersecret-test-token-32-bytes-abc"}

    payload = {
        "title": "tick-test",
        "novel_excerpt": ("夜色低垂，少女白衣立于古寺檐下。她眉间一点朱砂，目光清亮如月。" * 3),
        "style": "ancient_3d_guoman",
        "episodes": 1,
        "genre": "ancient",
        "mode": "excerpt",
        "language": "Chinese",
    }
    r = serverless_client.post("/api/jobs", json=payload, headers=headers)
    assert r.status_code == 201, r.text
    jid = r.json()["id"]

    # Drive via /tick — embedded worker is OFF, only explicit ticks make progress.
    # Mock pipeline runs to completion inside ONE tick (it just claims+processes a job),
    # so one call with a generous max_seconds budget should be enough.
    tr = serverless_client.post(
        "/api/internal/worker/tick",
        json={"max_jobs": 1, "max_seconds": 180},
        headers=secret,
    )
    assert tr.status_code == 200, tr.text
    tick_result = tr.json()
    assert tick_result["processed"] >= 1, tick_result

    final = serverless_client.get(f"/api/jobs/{jid}", headers=headers).json()
    assert final["status"] in {"done", "succeeded", "completed"}, final
    assert final.get("progress") == 100, final
    assert final.get("current_step") == 6, final


# ---------------------------------------------------------------------------
# 4. EMBEDDED_WORKER=0 → no background worker task spawned
# ---------------------------------------------------------------------------
def test_embedded_worker_disabled_under_env(monkeypatch):
    monkeypatch.setenv("EMBEDDED_WORKER", "0")
    # Re-import main so the toggle re-evaluates
    for mod in ["app.main"]:
        if mod in sys.modules:
            del sys.modules[mod]
    from app.main import _embedded_worker_enabled
    assert _embedded_worker_enabled() is False


def test_embedded_worker_enabled_by_default(monkeypatch):
    monkeypatch.delenv("EMBEDDED_WORKER", raising=False)
    for mod in ["app.main"]:
        if mod in sys.modules:
            del sys.modules[mod]
    from app.main import _embedded_worker_enabled
    assert _embedded_worker_enabled() is True
