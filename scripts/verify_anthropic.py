"""验证 .env 配置的 Anthropic API（含 pure100.org 等第三方代理）端到端可用.

测试 3 个路径:
1. curl 路径(命令行)
2. urllib 路径(write_episodes.py 同款,无 SDK 依赖)
3. anthropic SDK 路径(multi_provider_vlm.py 同款)

用法:
    python scripts/verify_anthropic.py
"""
from __future__ import annotations

import json
import os
import pathlib
import subprocess
import sys
import urllib.error
import urllib.request

_REPO = pathlib.Path(__file__).resolve().parents[1]


def force_load_env(path: pathlib.Path) -> None:
    """强制覆盖 shell env(Claude Code 默认注入 api.anthropic.com 会屏蔽 .env)。"""

    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        v = v.split("#", 1)[0].strip()
        if k and v:
            os.environ[k.strip()] = v


BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
)


def test_curl() -> tuple[bool, str]:
    base = os.environ["ANTHROPIC_BASE_URL"].rstrip("/")
    tok = os.environ["ANTHROPIC_AUTH_TOKEN"]
    model = os.environ.get("ANTHROPIC_MODEL", "claude-opus-4-7")
    body = json.dumps({
        "model": model,
        "max_tokens": 30,
        "messages": [{"role": "user", "content": "Reply with the single word: pong"}],
    })
    cmd = [
        "curl", "-sS", "-X", "POST", f"{base}/v1/messages",
        "-H", "Content-Type: application/json",
        "-H", f"x-api-key: {tok}",
        "-H", f"Authorization: Bearer {tok}",
        "-H", "anthropic-version: 2023-06-01",
        "-d", body,
        "--max-time", "30",
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
    if proc.returncode != 0:
        return False, f"curl exit={proc.returncode} stderr={proc.stderr[:200]}"
    try:
        data = json.loads(proc.stdout)
        text = data.get("content", [{}])[0].get("text", "")
        return True, f"model={data.get('model')} text={text[:60]!r} tokens={data.get('usage', {}).get('output_tokens')}"
    except Exception as e:
        return False, f"parse fail: {e}; raw={proc.stdout[:200]}"


def test_urllib() -> tuple[bool, str]:
    base = os.environ["ANTHROPIC_BASE_URL"].rstrip("/")
    tok = os.environ["ANTHROPIC_AUTH_TOKEN"]
    model = os.environ.get("ANTHROPIC_MODEL", "claude-opus-4-7")
    payload = {
        "model": model,
        "max_tokens": 30,
        "messages": [{"role": "user", "content": "Reply with the single word: pong"}],
    }
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        f"{base}/v1/messages",
        data=body,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {tok}",
            "anthropic-version": "2023-06-01",
            "User-Agent": BROWSER_UA,
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read())
        text = data.get("content", [{}])[0].get("text", "")
        return True, f"model={data.get('model')} text={text[:60]!r} tokens={data.get('usage', {}).get('output_tokens')}"
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")[:300]
        return False, f"HTTP {e.code}: {body}"
    except Exception as e:
        return False, f"{type(e).__name__}: {e}"


def test_sdk() -> tuple[bool, str]:
    try:
        import anthropic
    except ImportError:
        return False, "anthropic SDK not installed (pip install anthropic)"
    base = os.environ["ANTHROPIC_BASE_URL"]
    tok = os.environ["ANTHROPIC_AUTH_TOKEN"]
    model = os.environ.get("ANTHROPIC_MODEL", "claude-opus-4-7")
    try:
        client = anthropic.Anthropic(
            base_url=base,
            auth_token=tok,
            default_headers={"User-Agent": BROWSER_UA},
        )
        # 显式校验 SDK 拿到正确 base_url（不被 shell ANTHROPIC_BASE_URL 覆盖）
        actual_base = str(client.base_url)
        if base not in actual_base:
            return False, f"SDK base_url={actual_base} ≠ configured {base} (env precedence bug)"
        msg = client.messages.create(
            model=model,
            max_tokens=30,
            messages=[{"role": "user", "content": "Reply with the single word: pong"}],
        )
        text = msg.content[0].text if msg.content else ""
        return True, f"model={msg.model} text={text[:60]!r} tokens={msg.usage.output_tokens}"
    except Exception as e:
        return False, f"{type(e).__name__}: {str(e)[:200]}"


def main() -> int:
    force_load_env(_REPO / ".env")
    print(f"=== Anthropic API connectivity check ===")
    print(f"  ANTHROPIC_BASE_URL  = {os.environ.get('ANTHROPIC_BASE_URL', '<UNSET>')}")
    print(f"  ANTHROPIC_AUTH_TOKEN= {os.environ.get('ANTHROPIC_AUTH_TOKEN', '<UNSET>')[:14]}…")
    print(f"  ANTHROPIC_API_KEY   = {os.environ.get('ANTHROPIC_API_KEY', '<UNSET>')[:14]}…")
    print(f"  ANTHROPIC_MODEL     = {os.environ.get('ANTHROPIC_MODEL', '<UNSET>')}")
    print()
    results: list[tuple[str, bool, str]] = []
    for name, fn in [("curl", test_curl), ("urllib", test_urllib), ("anthropic SDK", test_sdk)]:
        print(f"  Testing {name}…", end=" ", flush=True)
        ok, msg = fn()
        results.append((name, ok, msg))
        print("✓" if ok else "✗")
        print(f"    → {msg}")
    print()
    n_ok = sum(1 for _, ok, _ in results if ok)
    print(f"=== Summary: {n_ok}/{len(results)} paths OK ===")
    return 0 if n_ok == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
