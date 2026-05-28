"""End-to-end live verification for CloudBase deployment (V10).

架构：
  - 前端：CloudBase 静态托管  https://cursoraicode-5g67ezfl8a1891da-1300352403.tcloudbaseapp.com
  - 后端：BaaS HTTP 访问 (SCF) https://cursoraicode-5g67ezfl8a1891da-1300352403.ap-shanghai.app.tcloudbase.com/api/...

覆盖：
  1. 前端首页 / 登录页 / 注册页 / 控制台页 静态资源可达 + 关键中文文案存在
  2. 后端 /api/health /api/genres /api/samples
  3. 测试账号 test1@139.com / test2@139.com 登录 (密码 123456)
  4. 登录后 /api/jobs 包含 3 个种子完成作品（聊斋·兰若 / 聊斋·小倩 / 西游·石猴）
  5. 真实创建一个任务并轮询直至 succeeded
  6. 拉取 jobs/{id}/logs jobs/{id}/export jobs/{id}/versions jobs/{id}/marketing
  7. 全部通过则写 data/observability/e2e_cloudbase_live.json
"""
from __future__ import annotations

import json
import pathlib
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field

FRONTEND = "https://cursoraicode-5g67ezfl8a1891da-1300352403.tcloudbaseapp.com"
BACKEND = "https://cursoraicode-5g67ezfl8a1891da-1300352403.ap-shanghai.app.tcloudbase.com"
TEST_ACCOUNTS = [("test1@139.com", "123456"), ("test2@139.com", "123456")]

REPO = pathlib.Path(__file__).resolve().parents[1]


@dataclass
class Result:
    name: str
    ok: bool
    detail: str = ""


@dataclass
class Report:
    base_frontend: str = FRONTEND
    base_backend: str = BACKEND
    results: list[Result] = field(default_factory=list)

    def check(self, name: str, ok: bool, detail: str = "") -> bool:
        self.results.append(Result(name, ok, detail))
        mark = "PASS" if ok else "FAIL"
        print(f"  [{mark}] {name}" + (f" — {detail}" if detail else ""))
        return ok

    @property
    def passed(self) -> int:
        return sum(1 for r in self.results if r.ok)

    @property
    def failed(self) -> int:
        return sum(1 for r in self.results if not r.ok)


def _req_once(method: str, url: str, *, data: dict | None = None,
              headers: dict | None = None, timeout: float = 60.0,
              raw_response: bool = False) -> tuple[int, str, dict]:
    hdrs = {"Accept": "application/json", "User-Agent": "xyq-e2e/1.0",
            "Connection": "close"}
    if headers:
        hdrs.update(headers)
    body = None
    if data is not None:
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        hdrs["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=body, headers=hdrs, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            if raw_response:
                return resp.status, raw, {}
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


def _req(method: str, url: str, *, retries: int = 3, retry_delay: float = 3.0,
         **kwargs) -> tuple[int, str, dict]:
    """Wrapper with retry for transient SSL/cold-start errors."""
    last = (0, "", {})
    for attempt in range(retries):
        code, raw, body = _req_once(method, url, **kwargs)
        last = (code, raw, body)
        if code != 0 and code < 500:
            return last
        if attempt < retries - 1:
            time.sleep(retry_delay * (attempt + 1))
    return last


def verify_frontend(rep: Report) -> None:
    print("\n[1] 前端静态托管")
    pages = [
        ("/", ["小云鹊", "AI", "漫剧"]),
        ("/login/", ["登录"]),
        ("/signup/", ["注册"]),
        ("/dashboard/", []),
        ("/pricing/", ["定价方案"]),
    ]
    for path, keywords in pages:
        url = FRONTEND + path
        code, raw, _ = _req("GET", url, raw_response=True)
        ok = code == 200 and "<html" in raw.lower()
        if ok and keywords:
            ok = any(kw in raw for kw in keywords)
            detail = f"status={code} kw_match={ok}"
        else:
            detail = f"status={code} len={len(raw)}"
        rep.check(f"frontend GET {path}", ok, detail)


def verify_backend_basics(rep: Report) -> None:
    print("\n[2] 后端基础 API")
    code, raw, body = _req("GET", BACKEND + "/api/health")
    rep.check("backend /api/health", code == 200 and body.get("status") == "ok",
              f"status={code} body={raw[:80]}")

    code, raw, body = _req("GET", BACKEND + "/api/genres")
    ok = code == 200 and isinstance(body, list) and len(body) >= 5
    rep.check("backend /api/genres", ok, f"status={code} count={len(body) if isinstance(body, list) else '?'}")

    code, raw, body = _req("GET", BACKEND + "/api/genres/ancient")
    ok = code == 200 and isinstance(body, dict) and body.get("id") == "ancient"
    rep.check("backend /api/genres/ancient", ok, f"status={code}")


def login_or_signup(rep: Report, email: str, pwd: str) -> str | None:
    code, raw, login = _req("POST", BACKEND + "/api/auth/login",
                            data={"email": email, "password": pwd})
    token = login.get("token") or login.get("access_token") if isinstance(login, dict) else None
    if code == 200 and token:
        rep.check(f"auth login {email}", True, "via login")
        return token

    code2, raw2, reg = _req("POST", BACKEND + "/api/auth/signup",
                            data={"email": email, "password": pwd})
    token = reg.get("token") or reg.get("access_token") if isinstance(reg, dict) else None
    if code2 in (200, 201) and token:
        rep.check(f"auth signup {email}", True, "via signup")
        return token

    code3, raw3, login2 = _req("POST", BACKEND + "/api/auth/login",
                               data={"email": email, "password": pwd})
    token = login2.get("token") or login2.get("access_token") if isinstance(login2, dict) else None
    rep.check(f"auth login {email}", code3 == 200 and bool(token),
              f"login={code} signup={code2} login2={code3} body={raw3[:120]}")
    return token


def verify_seed_jobs(rep: Report, email: str, token: str) -> None:
    code, raw, jobs = _req("GET", BACKEND + "/api/jobs",
                           headers={"Authorization": f"Bearer {token}"})
    if code != 200 or not isinstance(jobs, list):
        rep.check(f"jobs list {email}", False, f"status={code} body={raw[:120]}")
        return
    rep.check(f"jobs list {email}", True, f"count={len(jobs)}")

    seed_titles = {"聊斋·兰若惊鸿", "聊斋·小倩出场", "西游·石猴出世"}
    present = {j.get("title") for j in jobs if j.get("status") == "succeeded"}
    rep.check(f"seed jobs present {email}", seed_titles.issubset(present),
              f"missing={seed_titles - present}")

    succeeded = [j for j in jobs if j.get("status") == "succeeded"]
    if not succeeded:
        rep.check(f"seed job has video {email}", False, "no succeeded job")
        return
    first = succeeded[0]
    has_url = bool(first.get("result_url"))
    rep.check(f"seed job has result_url {email}", has_url,
              f"url={first.get('result_url')}")

    jid = first["id"]
    for endpoint in (f"/api/jobs/{jid}/logs", f"/api/jobs/{jid}/versions",
                     f"/api/jobs/{jid}/marketing"):
        code, raw, body = _req("GET", BACKEND + endpoint,
                               headers={"Authorization": f"Bearer {token}"})
        rep.check(f"seed job sub {endpoint} ({email})", code == 200,
                  f"status={code} body={raw[:80]}")

    code, raw, body = _req("POST", BACKEND + f"/api/jobs/{jid}/export",
                           data={"platforms": ["douyin", "xiaohongshu"]},
                           headers={"Authorization": f"Bearer {token}"})
    ok = code == 200 and isinstance(body, list) and len(body) >= 1
    rep.check(f"seed job export POST ({email})", ok,
              f"status={code} body={raw[:80]}")


def verify_create_and_wait(rep: Report, email: str, token: str) -> None:
    payload = {
        "title": f"E2E 真实创建 {int(time.time())}",
        "novel_excerpt": (
            "三月长安城，杏花微雨夜，玉门关外北风急。少年提剑入江湖，"
            "回首已是百年身。月下醉酒长歌，曲终人散云散，唯有故人相忆，"
            "不见昨日春风。此去经年，应是良辰好景虚设，便纵有千种风情，"
            "更与何人说？"
        ),
        "genre": "ancient",
        "style": "ancient_3d_guoman",
        "mode": "excerpt",
        "language": "Chinese",
        "episodes": 1,
        "aspect_ratio": "9:16",
        "resolution": "1080p",
        "fps": 24,
    }
    code, raw, body = _req("POST", BACKEND + "/api/jobs", data=payload,
                           headers={"Authorization": f"Bearer {token}"})
    if code not in (200, 201) or not isinstance(body, dict) or "id" not in body:
        rep.check(f"create job {email}", False, f"status={code} body={raw[:200]}")
        return
    jid = body["id"]
    rep.check(f"create job {email}", True, f"id={jid} status={body.get('status')}")

    deadline = time.time() + 60
    final_status = body.get("status")
    while time.time() < deadline:
        time.sleep(5)
        code, raw, job = _req("GET", BACKEND + f"/api/jobs/{jid}",
                              headers={"Authorization": f"Bearer {token}"})
        if code == 200 and isinstance(job, dict):
            final_status = job.get("status")
            if final_status == "succeeded":
                break
    ok = final_status == "succeeded"
    rep.check(f"job reach succeeded {email}", ok, f"final_status={final_status} id={jid}")

    if ok:
        code, raw, body = _req("GET", BACKEND + f"/api/jobs/{jid}/logs",
                               headers={"Authorization": f"Bearer {token}"})
        rep.check(f"job logs {email}", code == 200, f"status={code}")
        code, raw, body = _req("POST", BACKEND + f"/api/jobs/{jid}/export",
                               data={"platforms": ["douyin"]},
                               headers={"Authorization": f"Bearer {token}"})
        rep.check(f"job export {email}", code == 200, f"status={code}")


def main() -> int:
    rep = Report()
    print("=" * 64)
    print(f"E2E Live Verify  frontend={FRONTEND}")
    print(f"                 backend ={BACKEND}")
    print("=" * 64)

    verify_frontend(rep)
    verify_backend_basics(rep)

    for email, pwd in TEST_ACCOUNTS:
        print(f"\n[3-7] 测试账号 {email}")
        token = login_or_signup(rep, email, pwd)
        if not token:
            continue
        verify_seed_jobs(rep, email, token)
        verify_create_and_wait(rep, email, token)

    print("\n" + "=" * 64)
    print(f"TOTAL: {rep.passed} PASS / {rep.failed} FAIL")

    report_path = REPO / "data" / "observability" / "e2e_cloudbase_live.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps({
        "frontend": FRONTEND,
        "backend": BACKEND,
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "passed": rep.passed,
        "failed": rep.failed,
        "results": [{"name": r.name, "ok": r.ok, "detail": r.detail} for r in rep.results],
    }, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Report: {report_path}")
    return 0 if rep.failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
