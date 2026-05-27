"""Post-deploy live verification for CloudBase all-in-one (xyq service).

Checks:
  1. Resolve service public URL (CLI or --base-url)
  2. GET /          → 200 (Next.js shell)
  3. GET /api/health + /api/healthz
  4. GET /api/genres (public catalogue)
  5. POST /api/auth/register + /api/auth/login (ephemeral user)
  6. GET /api/jobs (authenticated)

Usage:
  python scripts/verify_cloudbase_live.py
  python scripts/verify_cloudbase_live.py --base-url https://xxx.run.tcloudbase.com
  python scripts/verify_cloudbase_live.py --update-env
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
import uuid
from dataclasses import dataclass

REPO = pathlib.Path(__file__).resolve().parents[1]
ENV_SIMPLE = REPO / "deploy" / "cn-serverless" / ".env.simple"


def _load_env_simple() -> dict[str, str]:
    out: dict[str, str] = {}
    if not ENV_SIMPLE.exists():
        return out
    for line in ENV_SIMPLE.read_text(encoding="utf-8").splitlines():
        m = re.match(r"^\s*([A-Z_][A-Z0-9_]*)=(.*)$", line)
        if m:
            v = m.group(2).strip().strip('"').strip("'")
            if v:
                out[m.group(1)] = v
    return out


def _run(cmd: list[str], *, timeout: float = 120.0) -> tuple[int, str]:
    try:
        r = subprocess.run(
            cmd, capture_output=True, text=True, encoding="utf-8",
            errors="replace", timeout=timeout,
        )
        return r.returncode, (r.stdout or "") + (r.stderr or "")
    except FileNotFoundError:
        return 127, f"command not found: {cmd[0]}"
    except subprocess.TimeoutExpired:
        return 124, "timeout"


def _resolve_url(env_id: str) -> str | None:
    code, out = _run(["tcb", "cloudrun", "list", "--env-id", env_id])
    if code != 0:
        return None
    # Try JSON first
    for line in out.splitlines():
        line = line.strip()
        if line.startswith("{") or line.startswith("["):
            try:
                data = json.loads(line)
                items = data if isinstance(data, list) else data.get("services") or data.get("data") or []
                for it in items:
                    name = (it.get("name") or it.get("ServerName") or "").lower()
                    if name == "xyq":
                        return it.get("url") or it.get("DefaultDomain") or it.get("domain")
            except json.JSONDecodeError:
                pass
    # Fallback: scrape *.run.tcloudbase.com / *.tcloudbase.com from output
    m = re.search(r"https://[\w.-]+\.(?:run\.)?tcloudbase\.com", out)
    return m.group(0) if m else None


def _req(method: str, url: str, *, data: dict | None = None,
         headers: dict | None = None, timeout: float = 60.0) -> tuple[int, str, dict]:
    hdrs = {"Accept": "application/json", "User-Agent": "xyq-verify/1.0"}
    if headers:
        hdrs.update(headers)
    body = None
    if data is not None:
        body = json.dumps(data).encode("utf-8")
        hdrs["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=body, headers=hdrs, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            try:
                return resp.status, raw, json.loads(raw) if raw else {}
            except json.JSONDecodeError:
                return resp.status, raw, {}
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", errors="replace")
        try:
            return e.code, raw, json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            return e.code, raw, {}
    except Exception as exc:
        return 0, str(exc), {}


@dataclass
class Result:
    name: str
    ok: bool
    detail: str = ""


def verify(base: str) -> list[Result]:
    base = base.rstrip("/")
    results: list[Result] = []

    def check(name: str, ok: bool, detail: str = "") -> None:
        results.append(Result(name, ok, detail))
        mark = "PASS" if ok else "FAIL"
        print(f"  [{mark}] {name}" + (f" — {detail}" if detail else ""))

    # Warm-up (cold start minNum=0)
    print(f"\nTarget: {base}")
    for attempt in range(6):
        code, _, _ = _req("GET", f"{base}/api/health")
        if code == 200:
            break
        print(f"  ... cold start wait ({attempt + 1}/6, last={code})")
        time.sleep(15)

    code, raw, body = _req("GET", f"{base}/")
    check("GET / (frontend)", code == 200, f"status={code}")

    code, _, body = _req("GET", f"{base}/api/health")
    check("GET /api/health", code == 200 and body.get("status") == "ok",
          f"status={code} body={body.get('status', raw[:80])}")

    code, _, body = _req("GET", f"{base}/api/healthz")
    check("GET /api/healthz", code == 200, f"status={code}")

    code, _, body = _req("GET", f"{base}/api/genres")
    check("GET /api/genres", code == 200, f"status={code} count={len(body) if isinstance(body, list) else '?'}")

    email = f"verify_{uuid.uuid4().hex[:8]}@example.com"
    pwd = "VerifyPass123!"
    code, _, reg = _req("POST", f"{base}/api/auth/signup",
                        data={"email": email, "password": pwd})
    check("POST /api/auth/signup", code in (200, 201), f"status={code}")

    code, _, login = _req("POST", f"{base}/api/auth/login",
                          data={"email": email, "password": pwd})
    token = login.get("token") or login.get("access_token")
    check("POST /api/auth/login", code == 200 and bool(token), f"status={code}")

    if token:
        code, _, jobs = _req("GET", f"{base}/api/jobs",
                             headers={"Authorization": f"Bearer {token}"})
        check("GET /api/jobs (auth)", code == 200, f"status={code}")
    else:
        check("GET /api/jobs (auth)", False, "no token from login")

    return results


def _patch_env(base: str) -> None:
    targets = [REPO / ".env", REPO / "deploy" / "cn-serverless" / ".env",
               REPO / "deploy" / "cn-serverless" / ".env.simple"]
    keys = {"BACKEND_URL": base, "SITE_URL": base,
            "NEXT_PUBLIC_BACKEND_URL": base, "CORS_ORIGINS": base}
    for path in targets:
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        for k, v in keys.items():
            if re.search(rf"^{k}=", text, re.M):
                text = re.sub(rf"^{k}=.*$", f"{k}={v}", text, flags=re.M)
            else:
                text += f"\n{k}={v}\n"
        path.write_text(text, encoding="utf-8")
        print(f"  updated {path.relative_to(REPO)}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", default=os.environ.get("BACKEND_URL", ""))
    ap.add_argument("--env-id", default="")
    ap.add_argument("--update-env", action="store_true")
    args = ap.parse_args()

    env = _load_env_simple()
    env_id = args.env_id or env.get("ENV_ID", "")
    base = args.base_url.rstrip("/")

    if not base and env_id:
        print(f"Resolving CloudRun URL for env {env_id}...")
        base = _resolve_url(env_id) or ""

    if not base:
        print("[FAIL] No base URL. Deploy first or pass --base-url", file=sys.stderr)
        return 2

    print("=" * 60)
    print("CloudBase Live Verification")
    print("=" * 60)
    results = verify(base)
    passed = sum(1 for r in results if r.ok)
    failed = sum(1 for r in results if not r.ok)
    print(f"\nTOTAL: {passed} PASS / {failed} FAIL")

    if args.update_env and failed == 0:
        print("\nPatching local .env with BACKEND_URL / SITE_URL...")
        _patch_env(base)

    report = REPO / "data" / "observability" / "cloudbase_live_verify.json"
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(json.dumps({
        "base_url": base,
        "env_id": env_id,
        "passed": passed,
        "failed": failed,
        "checks": [{"name": r.name, "ok": r.ok, "detail": r.detail} for r in results],
    }, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Report: {report}")

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
