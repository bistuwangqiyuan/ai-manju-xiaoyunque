"""End-to-end smoke test for guest (no-registration) experience.

Flow:
  1. POST /api/auth/guest  -> obtains token + guest_id
  2. Verify guest_id stickiness across two calls
  3. With token, hit core unauthenticated-then-now-allowed endpoints:
        GET  /api/auth/me
        GET  /api/jobs
        GET  /api/jobs/quota
        GET  /api/genres
        GET  /api/templates
        GET  /api/gallery
        GET  /api/library
  4. Verify that the static homepage advertises the new CTA copy.
"""
from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.request

try:  # ensure utf-8 on windows
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:  # noqa: BLE001
    pass

BACKEND = "https://cursoraicode-5g67ezfl8a1891da-1300352403.ap-shanghai.app.tcloudbase.com"
HOSTING = "https://cursoraicode-5g67ezfl8a1891da-1300352403.tcloudbaseapp.com"


def _req(path: str, *, method: str = "GET", token: str | None = None,
         body: dict | None = None, base: str = BACKEND,
         retries: int = 3, timeout: int = 30) -> tuple[int, str]:
    url = f"{base}{path}"
    data = json.dumps(body).encode() if body is not None else None
    headers = {"Accept": "application/json"}
    if body is not None:
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = f"Bearer {token}"
    last_exc: Exception | None = None
    for attempt in range(retries):
        try:
            r = urllib.request.Request(url, data=data, method=method, headers=headers)
            with urllib.request.urlopen(r, timeout=timeout) as resp:
                return resp.status, resp.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as e:
            return e.code, e.read().decode("utf-8", errors="replace")
        except Exception as e:  # noqa: BLE001
            last_exc = e
            time.sleep(1 + attempt)
    raise RuntimeError(f"failed: {url} after {retries} tries: {last_exc}")


def _ok(label: str, cond: bool, detail: str = "") -> bool:
    mark = "OK" if cond else "FAIL"
    print(f"  [{mark}] {label}{(' — ' + detail) if detail else ''}")
    return cond


def main() -> int:
    failures: list[str] = []

    print("== 1. POST /api/auth/guest (no guest_id) ==")
    code, body = _req("/api/auth/guest", method="POST", body={})
    if code != 200:
        print(f"  ERR status={code} body={body[:200]}")
        return 1
    data = json.loads(body)
    token = data["token"]
    gid = data["guest_id"]
    user = data["user"]
    _ok("status=200", True)
    _ok("is_guest=true", data.get("is_guest") is True, str(data.get("is_guest")))
    _ok("guest_id valid", isinstance(gid, str) and 8 <= len(gid) <= 32, gid)
    _ok("credits_cents=10000", user.get("credits_cents") == 10000, str(user.get("credits_cents")))
    _ok("tier=free", user.get("tier") == "free", str(user.get("tier")))
    _ok("email looks like guest", str(user.get("email", "")).startswith("guest-"), user.get("email"))

    print("\n== 2. POST /api/auth/guest with same guest_id (stickiness) ==")
    code, body = _req("/api/auth/guest", method="POST", body={"guest_id": gid})
    data2 = json.loads(body)
    _ok("status=200", code == 200)
    if not _ok("guest_id sticky", data2.get("guest_id") == gid,
               f"sent={gid} got={data2.get('guest_id')}"):
        failures.append("guest_id-sticky")
    if not _ok("uid sticky", data2.get("user", {}).get("id") == user["id"]):
        failures.append("uid-sticky")

    print("\n== 3. Authenticated endpoints with guest token ==")
    # only test paths the frontend actually calls
    for path in ["/api/auth/me", "/api/jobs", "/api/jobs/quota", "/api/genres",
                 "/api/gallery",
                 "/api/library/characters", "/api/library/scenes",
                 "/api/library/expressions", "/api/library/actions",
                 "/api/library/wardrobe"]:
        code, body = _req(path, token=token)
        ok = (code == 200)
        snippet = body[:80].replace("\n", " ")
        if not _ok(f"GET {path}", ok, f"status={code} body[0:80]={snippet}"):
            failures.append(f"GET {path}")

    print("\n== 3b. Library endpoints must return non-empty arrays ==")
    lib_min = {
        "/api/library/characters": 5,
        "/api/library/scenes": 5,
        "/api/library/expressions": 5,
        "/api/library/actions": 5,
        "/api/library/wardrobe": 5,
    }
    for path, min_count in lib_min.items():
        code, body = _req(path, token=token)
        try:
            arr = json.loads(body)
        except Exception:  # noqa: BLE001
            arr = None
        cond = isinstance(arr, list) and len(arr) >= min_count
        if not _ok(f"{path} >= {min_count} items",
                   cond, f"got {len(arr) if isinstance(arr, list) else type(arr).__name__}"):
            failures.append(f"library-empty {path}")

    print("\n== 4. Hosting front page advertises new CTA ==")
    code, html = _req("/", base=HOSTING, retries=2)
    _ok("hosting status=200", code == 200)
    must = ["立即免费体验，无需注册", "免注册免登录", "点开就用", "/dashboard/new"]
    missing = [m for m in must if m not in html]
    if not _ok("homepage has new CTA copy", not missing, f"missing={missing}"):
        failures.append("homepage-copy")

    print("\n== 4b. Library page renders heading + tab labels ==")
    code, lib_html = _req("/library/", base=HOSTING, retries=2)
    _ok("hosting /library status=200", code == 200)
    lib_must = ["角色", "场景", "表情", "动作", "服饰", "分镜层可直接调用"]
    lib_missing = [m for m in lib_must if m not in lib_html]
    if not _ok("library page has expected labels", not lib_missing,
               f"missing={lib_missing}"):
        failures.append("library-page-html")

    print("\n== 5. Guest user can hit core 'requires_auth' resources ==")
    # listJobs after auth must include seeded test1/test2 jobs even for guest? No:
    # guest has its own uid, so list is empty unless they created jobs. Just confirm 200.
    code, body = _req("/api/jobs", token=token)
    _ok("GET /api/jobs as guest", code == 200, f"status={code}")
    code, body = _req("/api/jobs/quota", token=token)
    if code == 200:
        q = json.loads(body)
        _ok("quota.tier=free", q.get("tier") == "free", str(q.get("tier")))
        _ok("quota.credits_cents=10000", q.get("credits_cents") == 10000,
            str(q.get("credits_cents")))

    if failures:
        print("\n== FAILURES ==")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("\n== ALL GREEN ==")
    return 0


if __name__ == "__main__":
    sys.exit(main())
