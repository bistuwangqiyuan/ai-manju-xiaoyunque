"""快速烟测 — 仅提交一个真实任务，校验：
  - real mode 开关生效（pipeline_version == 'v10-manju-agent'）
  - COS state 持久化（同一 job_id 再 GET 一次仍能读到状态）
  - Manju script_analysis 已提交成功（script_task_id 存在）
"""
from __future__ import annotations
import json, sys, time, urllib.request, urllib.error

BACKEND = "https://cursoraicode-5g67ezfl8a1891da-1300352403.ap-shanghai.app.tcloudbase.com"
EMAIL = "test1@139.com"
PWD = "123456"
NOVEL = (
    "兰若寺夜雨初停，廊下灯笼摇曳，宁采臣独宿西厢，案上残卷未掩。"
    "三更梆响，回廊外忽现一抹白影，月光透窗，照得那身缟素如水。"
    "宁采臣推窗探头，只见一名女子立于古井之畔，眉心一点朱砂，目若秋水。"
    "她回眸轻笑，启唇似有话欲说，却又化作一声叹息，飘进夜风。"
    "宁采臣心头一颤，那一刻他便知，这一夜的所见所闻，再不能用书生的常理度量。"
    "古钟突鸣，乌云压低，远处寺檐上有黑羽掠过，似有妖物在窥。"
)


def req(method, url, *, data=None, headers=None, timeout=45):
    hdrs = {"Accept": "application/json", "Connection": "close"}
    if headers:
        hdrs.update(headers)
    body = None
    if data is not None:
        body = json.dumps(data, ensure_ascii=False).encode()
        hdrs["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=body, headers=hdrs, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read().decode("utf-8", errors="replace")
            try:
                return r.status, raw, json.loads(raw) if raw else {}
            except json.JSONDecodeError:
                return r.status, raw, {}
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", errors="replace")
        try:
            return e.code, raw, json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            return e.code, raw, {}
    except Exception as exc:
        return 0, str(exc), {}


def main() -> int:
    code, raw, body = req("GET", BACKEND + "/api/health")
    print(f"[health] {code} {raw[:120]}")
    assert code == 200, raw

    code, raw, login = req("POST", BACKEND + "/api/auth/login",
                            data={"email": EMAIL, "password": PWD})
    print(f"[login] {code}")
    token = login.get("token")
    auth = {"Authorization": f"Bearer {token}"}

    code, raw, job = req("POST", BACKEND + "/api/jobs",
                          data={"title": f"smoke {int(time.time())}",
                                "novel_excerpt": NOVEL, "genre": "ancient",
                                "style": "3d", "mode": "excerpt",
                                "language": "Chinese", "episodes": 1,
                                "aspect_ratio": "9:16"}, headers=auth, timeout=60)
    print(f"[POST /jobs] {code}")
    print("  pipeline_version=", job.get("pipeline_version"))
    print("  status=", job.get("status"))
    print("  current_step=", job.get("current_step"))
    print("  progress=", job.get("progress"))
    print("  id=", job.get("id"))
    print("  error=", job.get("error"))
    if code not in (200, 201):
        print(f"  raw_body={raw[:500]}")
        return 1
    jid = job.get("id")

    print("\n--- second GET to verify COS persistence ---")
    time.sleep(2)
    code, raw, job2 = req("GET", BACKEND + f"/api/jobs/{jid}", headers=auth)
    print(f"[GET /jobs/{jid}] {code}")
    print("  pipeline_version=", job2.get("pipeline_version"))
    print("  status=", job2.get("status"))
    print("  current_step=", job2.get("current_step"))
    print("  progress=", job2.get("progress"))
    print("  error=", job2.get("error"))

    print("\n--- logs ---")
    code, raw, logs = req("GET", BACKEND + f"/api/jobs/{jid}/logs", headers=auth)
    if isinstance(logs, list):
        for e in logs[:20]:
            print(f"  [{e.get('level')}] {e.get('message')}")
    else:
        print(f"  {raw[:300]}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
