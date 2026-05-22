"""Phase 9: backend integration tests via FastAPI TestClient (mock worker)."""
from __future__ import annotations

import os
import pathlib
import sys
import time

import pytest

_REPO = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO))
sys.path.insert(0, str(_REPO / "backend"))


@pytest.fixture(scope="module")
def client():
    # Force fresh sqlite db for this module
    db_path = _REPO / "data" / "test_backend.db"
    if db_path.exists():
        db_path.unlink()
    os.environ["DATABASE_URL"] = f"sqlite:///{db_path}"
    os.environ["JWT_SECRET"] = "test-jwt"
    os.environ["STORAGE_DIR"] = str(_REPO / "data" / "test_backend_storage")
    # Reset cached settings + DB engine so the new env vars apply
    for mod in [
        "app.settings",
        "app.db",
        "app.main",
        "app.routes.auth",
        "app.routes.jobs",
        "app.routes.batch",
        "app.routes.genres",
        "app.routes.library",
        "app.routes.billing",
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


def _signup(client) -> dict:
    email = f"test+{int(time.time()*1000)}@example.com"
    r = client.post("/api/auth/signup", json={"email": email, "password": "Password1!"})
    assert r.status_code in (200, 201)
    return r.json()


def test_health_endpoint(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "ok"
    assert "mock_worker" in data


def test_genres_endpoint_returns_five(client):
    r = client.get("/api/genres")
    assert r.status_code == 200
    data = r.json()
    ids = {g["id"] for g in data}
    assert {"ancient", "modern", "sweet_pet", "suspense", "xuanhuan"}.issubset(ids)


def test_library_expressions_and_actions(client):
    r = client.get("/api/library/expressions")
    assert r.status_code == 200
    keys = {e["key"] for e in r.json()}
    assert {"happy", "angry", "sad", "shock", "shy", "cold"}.issubset(keys)

    r = client.get("/api/library/actions")
    assert r.status_code == 200
    keys = {a["key"] for a in r.json()}
    assert {"stand", "walk", "eye_lock", "hand_in", "salute", "fight"}.issubset(keys)


def test_full_job_lifecycle_in_mock_mode(client):
    auth = _signup(client)
    token = auth["token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 1) Create a free-tier job (1 episode)
    payload = {
        "title": "测试 · 古风",
        "novel_excerpt": ("夜色低垂，少女白衣立于古寺檐下。她眉间一点朱砂，目光清亮如月。" * 3),
        "style": "ancient_3d_guoman",
        "episodes": 1,
        "genre": "ancient",
        "mode": "excerpt",
        "language": "Chinese",
    }
    r = client.post("/api/jobs", json=payload, headers=headers)
    assert r.status_code == 201, r.text
    job = r.json()
    jid = job["id"]
    assert job["status"] in {"queued", "running"}

    # 2) Wait for the mock worker to finish (timeout 90s for slower CI)
    for _ in range(180):
        r = client.get(f"/api/jobs/{jid}", headers=headers)
        assert r.status_code == 200
        j = r.json()
        if j["status"] in {"succeeded", "failed"}:
            break
        time.sleep(0.5)
    assert j["status"] == "succeeded", f"job ended with {j['status']} err={j.get('error')}"
    assert j["quality_score"] is not None
    assert j["scores_7d"] is not None

    # 3) Logs reachable
    r = client.get(f"/api/jobs/{jid}/logs", headers=headers)
    assert r.status_code == 200
    assert len(r.json()) > 0

    # 4) Versions reachable
    r = client.get(f"/api/jobs/{jid}/versions", headers=headers)
    assert r.status_code == 200

    # 5) Shots endpoint reachable (empty in mock worker, but should not 500)
    r = client.get(f"/api/jobs/{jid}/shots", headers=headers)
    assert r.status_code == 200

    # 6) Marketing copy
    r = client.get(f"/api/jobs/{jid}/marketing", headers=headers)
    assert r.status_code == 200
    mk = r.json()
    assert mk["title"]
    assert mk["hashtags"]


def test_theme_mode_job_create(client):
    auth = _signup(client)
    headers = {"Authorization": f"Bearer {auth['token']}"}
    r = client.post(
        "/api/jobs",
        json={
            "title": "theme test",
            "novel_excerpt": "",
            "style": "modern_cinematic",
            "episodes": 1,
            "genre": "modern",
            "mode": "theme",
            "theme": "实习生闯进总裁办公室，一杯咖啡引发的命运纠葛。",
            "language": "Chinese",
        },
        headers=headers,
    )
    assert r.status_code == 201, r.text
    j = r.json()
    assert j["mode"] == "theme"
    assert j["theme"]


def test_batch_create_and_list(client):
    auth = _signup(client)
    headers = {"Authorization": f"Bearer {auth['token']}"}

    r = client.post(
        "/api/batch",
        json={
            "name": "测试批次",
            "style": "ancient_3d_guoman",
            "genre": "ancient",
            "aspect_ratio": "9:16",
            "source_urls": ["http://example.com/a.png", "http://example.com/b.png"],
            "params": {},
        },
        headers=headers,
    )
    assert r.status_code == 201, r.text
    b = r.json()
    assert b["total_items"] == 2

    r = client.get("/api/batch", headers=headers)
    assert r.status_code == 200
    assert any(item["id"] == b["id"] for item in r.json())
