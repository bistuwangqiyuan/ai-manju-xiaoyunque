"""经线上「真实管线」(火山小云雀 Manju Agent，全国产) 生成「荀彧劝曹操·奉天子以令诸侯」视频。

与 generate_xunyu_sample.py（阿里 HappyHorse i2v，当前账号欠费被封）不同，
本脚本走 **腾讯云 SCF + 火山 Manju** 的真实任务管线（POST /api/jobs → 轮询），
是当前可用的全国产真实生成路径。

成功后：下载 result_url / cover_url 到 web/public/samples/，做质量门禁校验，
写报告到 data/observability/xunyu_manju_real.json。**不自动改 catalog**——
是否入示例由调用方按门禁结果决定（满足"测试成功则放入示例"）。

用法：
  python scripts/generate_xunyu_via_manju.py
"""
from __future__ import annotations

import io
import json
import pathlib
import shutil
import sys
import time
import urllib.error
import urllib.request

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
    except Exception:  # noqa: BLE001
        pass
else:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

BACKEND = "https://cursoraicode-5g67ezfl8a1891da-1300352403.ap-shanghai.app.tcloudbase.com"
HOSTING = "https://cursoraicode-5g67ezfl8a1891da-1300352403.tcloudbaseapp.com"
TEST_EMAIL = "test1@139.com"
TEST_PWD = "123456"

REPO = pathlib.Path(__file__).resolve().parents[1]
SAMPLES_DIR = REPO / "web" / "public" / "samples"
REPORT = REPO / "data" / "observability" / "xunyu_manju_real.json"
SLUG = "xunyu_fengtianzi"

# >= 200 字真人写实「奉天子以令诸侯」小说片段，供 Manju 拆集
NOVEL_EXCERPT = (
    "汉献帝建安元年，曹操屯兵许县，帐内烛火通明。谋士荀彧整衣入帐，向曹操深深一揖。"
    "他言道：昔晋文公纳周襄王而诸侯景从，汉高祖为义帝缟素而天下归心。"
    "今天子蒙尘，播越流离，将军首倡义兵，何不奉迎天子以从民望？"
    "曹操按剑沉吟，目光如炬。荀彧再进一步，声音恳切：奉主上以从人望，大顺也；"
    "秉至公以服雄杰，大略也；扶弘义以致英俊，大德也。四方虽有逆节，其何能为？"
    "曹操闻言，霍然起身，斗篷随风而动。他望向北方，许久方道：文若之言，正合吾意！"
    "遂定计西迎天子，移驾许都，自此挟天子以令诸侯，奠定北方霸业之基。"
    "帐外旌旗猎猎，星河低垂，一个新的乱世格局，就在这一夜悄然定下。"
)


def _req(method, url, *, data=None, headers=None, timeout=30, retries=3):
    last = (0, "", {})
    for attempt in range(retries + 1):
        hdrs = {"Accept": "application/json", "User-Agent": "xyq-xunyu-manju/1.0",
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
        except Exception as exc:  # noqa: BLE001
            last = (0, str(exc), {})
            if attempt < retries:
                time.sleep(2 + 2 * attempt)
    return last


def _download(url: str, dest: pathlib.Path, attempts: int = 5) -> bool:
    dest.parent.mkdir(parents=True, exist_ok=True)
    for i in range(attempts):
        try:
            with urllib.request.urlopen(url, timeout=120) as r, open(dest, "wb") as f:
                shutil.copyfileobj(r, f)
            return True
        except Exception as e:  # noqa: BLE001
            print(f"    [dl retry {i+1}] {type(e).__name__}: {str(e)[:60]}")
            time.sleep(2 + 2 * i)
    return False


def main() -> int:
    print("=" * 60)
    print(f"荀彧·奉天子 真实生成 (Manju 火山)  backend={BACKEND}")
    print("=" * 60)

    code, raw, _ = _req("GET", BACKEND + "/api/health")
    print(f"[health] {code} {raw[:100]}")
    if code != 200:
        print("backend not reachable")
        return 1

    code, raw, login = _req("POST", BACKEND + "/api/auth/login",
                            data={"email": TEST_EMAIL, "password": TEST_PWD})
    token = login.get("token") if isinstance(login, dict) else None
    if not token:
        print(f"login failed: {code} {raw[:200]}")
        return 1
    auth = {"Authorization": f"Bearer {token}"}
    print(f"[login] {TEST_EMAIL} ok")

    payload = {
        "title": f"荀彧劝曹操·奉天子以令诸侯 {int(time.time())}",
        "novel_excerpt": NOVEL_EXCERPT,
        "genre": "ancient",
        "style": "cinema_realism",
        "mode": "excerpt",
        "language": "Chinese",
        "episodes": 1,
        "aspect_ratio": "9:16",
    }
    code = 0
    raw = ""
    job: dict = {}
    for attempt in range(4):
        code, raw, job = _req("POST", BACKEND + "/api/jobs",
                              data=payload, headers=auth, timeout=90, retries=0)
        if code in (200, 201):
            break
        print(f"[create {attempt+1}] code={code} body={raw[:300]}")
        time.sleep(8 * (attempt + 1))
    if code not in (200, 201):
        print(f"POST /jobs failed: {code} {raw[:400]}")
        return 1
    jid = job.get("id")
    print(f"[create] id={jid} pipeline={job.get('pipeline_version')} status={job.get('status')}")

    deadline = time.time() + 60 * 60
    last = ""
    while time.time() < deadline:
        time.sleep(30)
        code, raw, j = _req("GET", BACKEND + f"/api/jobs/{jid}", headers=auth, timeout=45)
        if code != 200 or not isinstance(j, dict):
            print(f"[poll] GET {code} {raw[:120]}")
            continue
        sig = f"{j.get('status')}|{j.get('current_step')}|{j.get('progress')}"
        if sig != last:
            print(f"[poll t={int((time.time()-(deadline-3600))/60)}min] "
                  f"status={j.get('status')} step={j.get('current_step')} "
                  f"progress={j.get('progress')} err={j.get('error') or ''}")
            last = sig
        if j.get("status") == "succeeded":
            result = j.get("result_url") or ""
            cover = j.get("cover_url") or ""
            print(f"\nSUCCEEDED result={result[:90]} cover={cover[:90]}")
            REPORT.parent.mkdir(parents=True, exist_ok=True)
            mp4 = SAMPLES_DIR / f"{SLUG}.mp4"
            jpg = SAMPLES_DIR / f"{SLUG}.jpg"
            mp4_ok = bool(result) and _download(
                result if result.startswith("http") else HOSTING + result, mp4)
            if cover:
                _download(cover if cover.startswith("http") else HOSTING + cover, jpg)
            size = mp4.stat().st_size if mp4.exists() else 0
            gate_ok = mp4_ok and size >= 2_000_000
            print(f"[gate] mp4={size/1024/1024:.2f}MB ok={gate_ok}")
            REPORT.write_text(json.dumps({
                "backend": BACKEND, "job_id": jid, "status": "succeeded",
                "result_url": result, "cover_url": cover,
                "local_mp4": str(mp4), "mp4_bytes": size, "gate_ok": gate_ok,
            }, ensure_ascii=False, indent=2), encoding="utf-8")
            return 0 if gate_ok else 3
        if j.get("status") == "failed":
            print(f"\nFAILED error={j.get('error')}")
            REPORT.parent.mkdir(parents=True, exist_ok=True)
            REPORT.write_text(json.dumps({
                "backend": BACKEND, "job_id": jid, "status": "failed",
                "error": j.get("error"), "final_job": j,
            }, ensure_ascii=False, indent=2), encoding="utf-8")
            return 1
    print("\nTIMEOUT 60min")
    return 2


if __name__ == "__main__":
    sys.exit(main())
