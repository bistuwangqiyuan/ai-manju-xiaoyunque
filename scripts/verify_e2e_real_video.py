"""End-to-end live verification for REAL video generation (Manju Agent).

流程：
  1. /api/health    + /api/genres    sanity
  2. test1@139.com 登录拿 token
  3. POST /api/jobs 创建真实任务（≥ 200 字小说片段）→ 拿 job_id
  4. 每 30s 轮询 GET /api/jobs/{id}，打印 stage / progress / result_url
  5. 直到 status == succeeded（或 failed / 超时 60 min）
  6. 完成后拉 logs / versions / marketing 验证
"""
from __future__ import annotations

import io
import json
import pathlib
import sys
import time
import urllib.error
import urllib.request

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
    except Exception:  # noqa: BLE001
        pass
else:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

BACKEND = "https://cursoraicode-5g67ezfl8a1891da-1300352403.ap-shanghai.app.tcloudbase.com"
TEST_EMAIL = "test1@139.com"
TEST_PWD = "123456"

# >= 200 字符的小说片段，让 Manju Agent 可以拆出至少 1 集
NOVEL_EXCERPT = (
    "兰若寺夜雨初停，廊下灯笼摇曳，宁采臣独宿西厢，案上残卷未掩。"
    "三更梆响，回廊外忽现一抹白影，月光透窗，照得那身缟素如水。"
    "宁采臣推窗探头，只见一名女子立于古井之畔，眉心一点朱砂，目若秋水。"
    "她回眸轻笑，启唇似有话欲说，却又化作一声叹息，飘进夜风。"
    "宁采臣心头一颤，那一刻他便知，这一夜的所见所闻，再不能用书生的常理度量。"
    "古钟突鸣，乌云压低，远处寺檐上有黑羽掠过，似有妖物在窥。"
    "他握紧腰间那柄祖传桃木剑，深吸一口气，缓缓向回廊外走去。"
    "脚下青砖被雨水浸得发亮，每一步都像是踩在百年前的旧事上。"
    "那女子静静等他，朱砂痣在月下灿如初雪。"
)

REPO = pathlib.Path(__file__).resolve().parents[1]
REPORT = REPO / "data" / "observability" / "e2e_real_video.json"


def _req(method: str, url: str, *, data=None, headers=None, timeout=30, retries=2):
    last = (0, "", {})
    for attempt in range(retries + 1):
        hdrs = {"Accept": "application/json", "User-Agent": "xyq-real/1.0",
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
            last = (0, str(exc), {})
            if attempt < retries:
                time.sleep(2 + 2 * attempt)
                continue
    return last


def main() -> int:
    print("=" * 60)
    print(f"REAL VIDEO E2E  backend={BACKEND}")
    print("=" * 60)

    code, raw, body = _req("GET", BACKEND + "/api/health")
    print(f"[health] {code} {raw[:120]}")
    if code != 200:
        print("❌ backend not reachable")
        return 1

    code, raw, login = _req("POST", BACKEND + "/api/auth/login",
                            data={"email": TEST_EMAIL, "password": TEST_PWD})
    token = login.get("token") if isinstance(login, dict) else None
    if not token:
        print(f"❌ login failed: {code} {raw[:200]}")
        return 1
    print(f"[login] {TEST_EMAIL} → token len={len(token)}")

    auth_hdr = {"Authorization": f"Bearer {token}"}

    payload = {
        "title": f"REAL E2E · 兰若惊鸿 {int(time.time())}",
        "novel_excerpt": NOVEL_EXCERPT,
        "genre": "ancient",
        "style": "3d",
        "mode": "excerpt",
        "language": "Chinese",
        "episodes": 1,
        "aspect_ratio": "9:16",
    }
    # POST is the only call that touches Volcengine network — retry on cold start
    job: dict = {}
    raw = ""
    code = 0
    for attempt in range(4):
        code, raw, job = _req("POST", BACKEND + "/api/jobs",
                              data=payload, headers=auth_hdr, timeout=90, retries=0)
        if code in (200, 201):
            break
        print(f"[create attempt {attempt+1}] code={code} body={raw[:300]}")
        time.sleep(8 * (attempt + 1))
    if code not in (200, 201):
        print(f"FAILED POST /jobs after retries: {code} {raw[:400]}")
        return 1
    jid = job.get("id")
    print(f"[create] id={jid} stage_at_create={job.get('current_step')}"
          f" status={job.get('status')} pipeline={job.get('pipeline_version')}")
    if job.get("pipeline_version") != "v10-manju-agent":
        print(f"⚠️  pipeline_version={job.get('pipeline_version')} — real mode NOT engaged!")

    deadline = time.time() + 60 * 60  # 60 min
    last_stage = ""
    last_status = ""
    last_progress = -1
    ticks = 0

    while time.time() < deadline:
        ticks += 1
        time.sleep(30)
        code, raw, j = _req("GET", BACKEND + f"/api/jobs/{jid}",
                            headers=auth_hdr, timeout=45)
        if code != 200 or not isinstance(j, dict):
            print(f"[tick {ticks}] GET failed {code} {raw[:200]}")
            continue
        status = j.get("status")
        stage = j.get("current_step")
        progress = j.get("progress")
        if status != last_status or stage != last_stage or progress != last_progress:
            print(f"[tick {ticks:3d} t={int((time.time()-(deadline-3600))/60):3d}min]"
                  f" status={status} step={stage} progress={progress}"
                  f" err={j.get('error') or ''}")
            last_status, last_stage, last_progress = status, stage, progress

        if status == "succeeded":
            print(f"\n✅ SUCCEEDED  result_url={j.get('result_url')}"
                  f"  cover_url={j.get('cover_url')}")
            REPORT.parent.mkdir(parents=True, exist_ok=True)
            REPORT.write_text(json.dumps({
                "backend": BACKEND, "job_id": jid, "title": payload["title"],
                "status": status, "result_url": j.get("result_url"),
                "cover_url": j.get("cover_url"),
                "elapsed_seconds": int((time.time() - (deadline - 3600))),
                "final_job": j,
            }, indent=2, ensure_ascii=False), encoding="utf-8")

            # subsequent endpoints
            code, raw, logs = _req("GET", BACKEND + f"/api/jobs/{jid}/logs",
                                   headers=auth_hdr)
            print(f"[logs] {code} entries={len(logs) if isinstance(logs, list) else 0}")
            code, raw, vers = _req("GET", BACKEND + f"/api/jobs/{jid}/versions",
                                   headers=auth_hdr)
            print(f"[versions] {code} body={raw[:120]}")
            code, raw, mk = _req("POST", BACKEND + f"/api/jobs/{jid}/export",
                                 data={"platforms": ["douyin"]}, headers=auth_hdr)
            print(f"[export] {code} body={raw[:120]}")
            return 0
        if status == "failed":
            print(f"\n❌ FAILED  error={j.get('error')}")
            REPORT.parent.mkdir(parents=True, exist_ok=True)
            REPORT.write_text(json.dumps({
                "backend": BACKEND, "job_id": jid, "title": payload["title"],
                "status": "failed", "error": j.get("error"), "final_job": j,
            }, indent=2, ensure_ascii=False), encoding="utf-8")
            return 1

    print("\n⏱ TIMEOUT (60 min) — Manju Agent did not finish")
    return 2


if __name__ == "__main__":
    sys.exit(main())
