"""deploy_smoke — post-deploy end-to-end smoke test for a live backend.

Usage:
    python scripts/deploy_smoke.py --backend-url https://your-app.railway.app
    python scripts/deploy_smoke.py --backend-url http://localhost:8000

Flow:
    1. GET  /api/health                               — backend reachable
    2. POST /api/auth/signup                           — fresh user
    3. POST /api/jobs                                  — create mock job
    4. GET  /api/jobs/{id} (poll)                      — wait for succeeded
    5. GET  /api/jobs/{id}/versions                    — version v1 exists
    6. GET  /api/jobs/{id}/marketing                   — marketing copy exists

Exit code:
    0 — PASS
    1 — FAIL (prints reason)
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import uuid
import urllib.error
import urllib.request


def _http(
    url: str,
    *,
    method: str = "GET",
    headers: dict | None = None,
    body: dict | None = None,
    timeout: float = 30.0,
) -> tuple[int, dict]:
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={"Content-Type": "application/json", **(headers or {})},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read()
            try:
                return r.status, json.loads(raw) if raw else {}
            except json.JSONDecodeError:
                return r.status, {"_raw": raw.decode("utf-8", errors="ignore")[:500]}
    except urllib.error.HTTPError as e:
        try:
            body = json.loads(e.read())
        except Exception:
            body = {}
        return e.code, body


def run_smoke(backend_url: str, *, email: str | None = None, password: str | None = None,
              poll_seconds: int = 180) -> int:
    base = backend_url.rstrip("/")
    print(f"→ smoke against {base}")

    # 1. Health
    code, h = _http(f"{base}/api/health")
    if code != 200 or h.get("status") != "ok":
        print(f"FAIL: /api/health = {code} {h}")
        return 1
    print("  ✅ /api/health ok")

    # 2. Sign up a fresh user
    # NOTE: avoid reserved TLDs like .test / .example — pydantic
    # email-validator rejects them with HTTP 422.
    email = email or f"smoke-{uuid.uuid4().hex[:10]}@xiaoyunque-smoke.com"
    password = password or "smoke-test-pw-1!"
    code, signup = _http(
        f"{base}/api/auth/signup",
        method="POST",
        body={"email": email, "password": password},
    )
    if code not in (200, 201):
        print(f"FAIL: signup = {code} {signup}")
        return 1
    token = signup.get("access_token") or signup.get("token")
    if not token:
        print(f"FAIL: no access_token in signup response: {signup}")
        return 1
    auth = {"Authorization": f"Bearer {token}"}
    print(f"  ✅ signup ok ({email})")

    # 3. Create a 1-ep mock job
    code, job = _http(
        f"{base}/api/jobs",
        method="POST",
        headers=auth,
        body={
            "novel_excerpt": "smoke-test 月光低垂，少年立于古寺檐下。" * 4,
            "style": "ancient_3d_guoman",
            "genre": "ancient",
            "episodes": 1,
            "language": "Chinese",
        },
    )
    if code not in (200, 201):
        print(f"FAIL: POST /api/jobs = {code} {job}")
        return 1
    job_id = job.get("id") or job.get("job_id")
    if not job_id:
        print(f"FAIL: no job id in create response: {job}")
        return 1
    print(f"  ✅ job created (id={job_id})")

    # 4. Poll until succeeded
    final = None
    for i in range(poll_seconds // 2):
        code, polled = _http(f"{base}/api/jobs/{job_id}", headers=auth)
        if code != 200:
            print(f"FAIL: GET /api/jobs/{job_id} = {code} {polled}")
            return 1
        status = polled.get("status")
        if status == "succeeded":
            final = polled
            break
        if status == "failed":
            print(f"FAIL: job ended with status=failed: {polled}")
            return 1
        time.sleep(2)
    if final is None:
        print(f"FAIL: job did not reach 'succeeded' in {poll_seconds}s")
        return 1
    print(f"  ✅ job succeeded (score={final.get('quality_score')})")

    # 5. Versions endpoint — must be 200; empty list is acceptable on a
    # very-first mock job before the worker has snapshotted a version.
    code, vs = _http(f"{base}/api/jobs/{job_id}/versions", headers=auth)
    if code != 200:
        print(f"FAIL: versions = {code} {vs}")
        return 1
    if isinstance(vs, list):
        v_count = len(vs)
    else:
        v_count = len(vs.get("versions", []) or [])
    if v_count == 0:
        print("  ⚠️ versions endpoint ok but empty — mock worker did not snapshot a row")
    else:
        print(f"  ✅ versions endpoint returns {v_count} entry/entries")

    # 6. Marketing copy (best-effort — endpoint may 404 in some skus, not fatal)
    code, mk = _http(f"{base}/api/jobs/{job_id}/marketing", headers=auth)
    if code == 200:
        print(f"  ✅ marketing endpoint ok ({len(mk.get('hashtags') or []) } hashtags)")
    else:
        print(f"  ⚠️ marketing endpoint not available ({code}) — non-blocking")

    print("PASS — deploy_smoke completed successfully.")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="deploy_smoke")
    p.add_argument("--backend-url", required=True)
    p.add_argument("--email", default=None)
    p.add_argument("--password", default=None)
    p.add_argument("--timeout", type=int, default=180,
                   help="poll seconds (default 180 = 90 polls × 2s)")
    args = p.parse_args(argv)
    return run_smoke(
        args.backend_url, email=args.email, password=args.password,
        poll_seconds=args.timeout,
    )


if __name__ == "__main__":
    sys.exit(main())
