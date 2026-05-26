"""Phase 12 + final rollout smoke tests."""
from __future__ import annotations

import json
import pathlib
import subprocess
import sys


def test_canary_rollout_dry_run(tmp_path, monkeypatch):
    state = tmp_path / "canary_state.json"
    monkeypatch.setattr(
        "scripts.canary_rollout.STATE_PATH", state, raising=False,
    )
    # import after monkeypatch path would not work - call as subprocess
    proc = subprocess.run(
        [sys.executable, "scripts/canary_rollout.py",
         "--base-url", "http://127.0.0.1:8000",
         "--stage", "10", "--dry-run"],
        capture_output=True, text=True, timeout=60,
    )
    assert proc.returncode == 0, proc.stderr


def test_acceptance_script_runs(tmp_path):
    out = tmp_path / "report.json"
    result = subprocess.run(
        [sys.executable, "scripts/v10_acceptance.py", "--out", str(out)],
        capture_output=True, text=True, timeout=90,
    )
    assert result.returncode in (0, 1), (
        f"acceptance returned {result.returncode}\nstderr={result.stderr[-800:]}"
    )
    assert out.exists()
    md = out.with_suffix(".md")
    assert md.exists()
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["fail"] == 0, f"unexpected failures: {data['fail']}"
    assert len(data["chapters"]) == 12


def test_healthz_route_registered():
    from backend.app.main import app
    paths = [getattr(r, "path", "") for r in app.routes]
    assert "/api/healthz" in paths
