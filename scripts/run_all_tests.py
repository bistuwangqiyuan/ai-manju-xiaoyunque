"""上线系统综合测试编排器（聚合已有 verify_* 脚本）。

跑一组针对线上 CloudBase 部署的端到端/单元测试，统一汇总 PASS/FAIL。
用于「测试 → 修复 → 重测」循环：每轮调用本脚本，全绿即退出码 0。

包含：
  1. health        线上 /api/health：real_video_mode 必须 true（禁用 mock 示例视频）
  2. guest_e2e     scripts/verify_e2e_guest.py（访客全链路）
  3. samples       scripts/verify_samples_showcase.py（示例视频 + 展示页）
  4. gallery       /api/gallery 与静态 catalog 一致性 + 荀彧样片 30s 真人写实
  5. fallback_unit scripts/verify_fallback_revive.py（容灾逻辑单测，离线）

用法：
  python scripts/run_all_tests.py
  python scripts/run_all_tests.py --only health,gallery
  python scripts/run_all_tests.py --skip fallback_unit
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
    except Exception:  # noqa: BLE001
        pass

REPO = Path(__file__).resolve().parents[1]
API = "https://cursoraicode-5g67ezfl8a1891da-1300352403.ap-shanghai.app.tcloudbase.com"
HOSTING = "https://cursoraicode-5g67ezfl8a1891da-1300352403.tcloudbaseapp.com"
PY = sys.executable


def _http_json(url: str, *, retries: int = 4, timeout: int = 30):
    last = None
    for i in range(retries):
        try:
            with urllib.request.urlopen(url, timeout=timeout) as r:
                return r.status, json.loads(r.read().decode("utf-8", "replace"))
        except urllib.error.HTTPError as e:
            return e.code, None
        except Exception as e:  # noqa: BLE001
            last = e
            time.sleep(2 + 2 * i)
    print(f"    [http] {url} failed: {last}")
    return 0, None


def _http_head_size(url: str, *, retries: int = 3, timeout: int = 30) -> int:
    for i in range(retries):
        try:
            req = urllib.request.Request(url, method="HEAD")
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return int(r.headers.get("Content-Length", 0) or 0)
        except Exception:  # noqa: BLE001
            time.sleep(2 + 2 * i)
    return -1


# ---------------------------------------------------------------------------
# Test: 线上 health 必须是真实管线（杜绝 mock 示例视频冒充）
# ---------------------------------------------------------------------------

def test_health() -> tuple[bool, str]:
    code, body = _http_json(f"{API}/api/health")
    if code != 200 or not isinstance(body, dict):
        return False, f"status={code}"
    checks = {
        "real_video_mode=true": body.get("real_video_mode") is True,
        "mock_worker=false": body.get("mock_worker") is False,
        "manju_configured": body.get("manju_configured") is True,
        "cos_configured": body.get("cos_configured") is True,
    }
    failed = [k for k, v in checks.items() if not v]
    detail = "all green" if not failed else f"failed={failed} body={body}"
    return (not failed), detail


# ---------------------------------------------------------------------------
# Test: /api/gallery 与静态 catalog 一致 + 荀彧 30s 真人写实样片
# ---------------------------------------------------------------------------

def test_gallery() -> tuple[bool, str]:
    code, samples = _http_json(f"{API}/api/gallery")
    if code != 200 or not isinstance(samples, list):
        return False, f"/api/gallery status={code}"
    xy = [s for s in samples if s.get("id") == "sample-xunyu_yingxiandi"]
    if not xy:
        return False, "荀彧样片不在 gallery 中"
    s = xy[0]
    problems = []
    if "30s" not in (s.get("subtitle") or ""):
        problems.append(f"subtitle 非 30s: {s.get('subtitle')}")
    if s.get("style") != "cinema_realism":
        problems.append(f"style 非 cinema_realism: {s.get('style')}")
    # 视频可访问且 ≥ 8MB（30s 720P）
    vurl = HOSTING + (s.get("video_url") or "")
    size = _http_head_size(vurl)
    if size < 8_000_000:
        problems.append(f"mp4 过小/不可达: {size}B")
    cover_size = _http_head_size(HOSTING + (s.get("cover_url") or ""))
    if cover_size <= 0:
        problems.append("cover 不可达")
    return (not problems), ("ok mp4=%dB cover=%dB" % (size, cover_size)
                            if not problems else "; ".join(problems))


# ---------------------------------------------------------------------------
# Test: 子进程跑已有 verify_* 脚本
# ---------------------------------------------------------------------------

def _run_script(rel: str, timeout: int = 600) -> tuple[bool, str]:
    path = REPO / rel
    if not path.exists():
        return False, f"脚本不存在: {rel}"
    try:
        r = subprocess.run(
            [PY, str(path)], capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=timeout, cwd=str(REPO),
        )
    except subprocess.TimeoutExpired:
        return False, f"超时 (>{timeout}s)"
    tail = "\n".join((r.stdout or "").strip().splitlines()[-8:])
    return (r.returncode == 0), tail


def test_guest_e2e() -> tuple[bool, str]:
    return _run_script("scripts/verify_e2e_guest.py", timeout=300)


def test_samples() -> tuple[bool, str]:
    return _run_script("scripts/verify_samples_showcase.py", timeout=300)


def test_fallback_unit() -> tuple[bool, str]:
    return _run_script("scripts/verify_fallback_revive.py", timeout=120)


def test_domestic() -> tuple[bool, str]:
    return _run_script("scripts/verify_domestic_stack.py", timeout=120)


TESTS = {
    "health": test_health,
    "domestic": test_domestic,
    "gallery": test_gallery,
    "guest_e2e": test_guest_e2e,
    "samples": test_samples,
    "fallback_unit": test_fallback_unit,
}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="", help="逗号分隔，仅跑这些")
    ap.add_argument("--skip", default="", help="逗号分隔，跳过这些")
    args = ap.parse_args()

    only = {x.strip() for x in args.only.split(",") if x.strip()}
    skip = {x.strip() for x in args.skip.split(",") if x.strip()}

    names = [n for n in TESTS if (not only or n in only) and n not in skip]
    print("=" * 64)
    print(f"上线系统综合测试  ({len(names)} 项): {', '.join(names)}")
    print("=" * 64)

    results: dict[str, tuple[bool, str]] = {}
    for name in names:
        print(f"\n>>> [{name}]")
        t0 = time.time()
        try:
            ok, detail = TESTS[name]()
        except Exception as e:  # noqa: BLE001
            ok, detail = False, f"EXC {type(e).__name__}: {e}"
        results[name] = (ok, detail)
        print(f"    {'PASS' if ok else 'FAIL'} ({int(time.time()-t0)}s) — {detail}")

    passed = sum(1 for ok, _ in results.values() if ok)
    failed = [n for n, (ok, _) in results.items() if not ok]
    print("\n" + "=" * 64)
    print(f"汇总: {passed}/{len(results)} PASS")
    if failed:
        print(f"未通过: {', '.join(failed)}")
    print("=" * 64)

    report = REPO / "data" / "observability" / "run_all_tests.json"
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(json.dumps(
        {"passed": passed, "total": len(results),
         "results": {n: {"ok": ok, "detail": d} for n, (ok, d) in results.items()}},
        ensure_ascii=False, indent=2), encoding="utf-8")
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
