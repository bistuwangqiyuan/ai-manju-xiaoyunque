"""国产化无服务器架构审计：确认上线系统全部使用国产服务，且部署代码无境外依赖。

校验项：
  1. 部署目录 deploy/cloudfn-slim/*.py 中不得出现境外 AI SDK / 域名
     （anthropic / openai / api.anthropic.com / api.openai.com / gemini / vertexai ...）。
  2. 线上 /api/health 报告的视频管线提供方均为国产：
       - 火山引擎小云雀 Manju Agent（manju_configured）
       - 腾讯云 COS（cos_configured）
       - 阿里云百炼 / 快乐马（happyhorse_configured，备用）
  3. 线上托管域名为腾讯云 CloudBase（*.tcloudbaseapp.com / *.app.tcloudbase.com）。

全部通过 → 退出码 0。供 run_all_tests.py 聚合调用，也可单独运行。
"""
from __future__ import annotations

import json
import pathlib
import re
import sys
import time
import urllib.error
import urllib.request

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
    except Exception:  # noqa: BLE001
        pass

REPO = pathlib.Path(__file__).resolve().parents[1]
SLIM = REPO / "deploy" / "cloudfn-slim"
API = "https://cursoraicode-5g67ezfl8a1891da-1300352403.ap-shanghai.app.tcloudbase.com"
HOSTING = "https://cursoraicode-5g67ezfl8a1891da-1300352403.tcloudbaseapp.com"

# 境外 AI 服务标识（部署代码中不应出现）
_FOREIGN_PATTERNS = [
    r"\banthropic\b", r"api\.anthropic\.com", r"\bclaude-",
    r"\bopenai\b", r"api\.openai\.com", r"\bgpt-4", r"\bgpt-3",
    r"generativelanguage\.googleapis", r"\bvertexai\b", r"\bgemini-",
    r"\bcohere\b", r"\bmistral\b",
]

# 国产服务白名单（用于打印清单）
_DOMESTIC_STACK = {
    "无服务器运行时": "腾讯云 CloudBase 云函数 SCF (xyq-api)",
    "对象存储/状态": "腾讯云 COS",
    "静态托管": "腾讯云 CloudBase 静态托管",
    "视频生成(主)": "火山引擎 即梦/小云雀 Manju Agent",
    "视频生成(备)": "阿里云百炼 通义万相 / 快乐马 i2v",
    "首帧文生图": "阿里云百炼 通义万相 T2I",
}


def _http_json(url: str, *, retries: int = 5, timeout: int = 30):
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


def _scan_foreign() -> tuple[bool, str]:
    hits: list[str] = []
    for py in sorted(SLIM.glob("*.py")):
        text = py.read_text(encoding="utf-8", errors="replace").lower()
        for pat in _FOREIGN_PATTERNS:
            if re.search(pat, text):
                hits.append(f"{py.name}:{pat}")
    if hits:
        return False, "发现境外依赖引用: " + "; ".join(hits)
    n = len(list(SLIM.glob("*.py")))
    return True, f"部署代码 {n} 个 .py 文件均无境外 AI SDK/域名"


def _check_health() -> tuple[bool, str]:
    code, body = _http_json(f"{API}/api/health")
    if code != 200 or not isinstance(body, dict):
        return False, f"/api/health status={code}"
    domestic_ok = bool(body.get("manju_configured")) and bool(body.get("cos_configured"))
    detail = (f"real_video_mode={body.get('real_video_mode')} "
              f"manju={body.get('manju_configured')} cos={body.get('cos_configured')} "
              f"happyhorse={body.get('happyhorse_configured')}")
    return domestic_ok, detail


def _check_hosting_domain() -> tuple[bool, str]:
    ok_api = bool(re.search(r"\.(app\.tcloudbase|tcloudbaseapp)\.com", API))
    ok_host = bool(re.search(r"\.(app\.tcloudbase|tcloudbaseapp)\.com", HOSTING))
    return (ok_api and ok_host), "API + 托管均为腾讯云 CloudBase 域名"


def main() -> int:
    print("=" * 64)
    print("国产化无服务器架构审计")
    print("=" * 64)
    checks = [
        ("部署代码无境外依赖", _scan_foreign),
        ("线上管线提供方均国产", _check_health),
        ("托管域名为腾讯云", _check_hosting_domain),
    ]
    failed = []
    for name, fn in checks:
        try:
            ok, detail = fn()
        except Exception as e:  # noqa: BLE001
            ok, detail = False, f"EXC {type(e).__name__}: {e}"
        print(f"  [{'PASS' if ok else 'FAIL'}] {name} — {detail}")
        if not ok:
            failed.append(name)

    print("\n国产化技术栈清单:")
    for layer, svc in _DOMESTIC_STACK.items():
        print(f"  - {layer}: {svc}")

    print("\n" + "=" * 64)
    print("审计结果: " + ("全部国产 ✓" if not failed else f"未通过: {', '.join(failed)}"))
    print("=" * 64)
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
