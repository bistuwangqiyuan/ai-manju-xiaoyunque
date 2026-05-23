"""Verify which Phase-2 LLM providers actually return a valid response.

Calls each available provider with the same short prompt and reports
per-provider success / latency / first 80 chars. Useful as a smoke test
after adding new API keys.

Run:
    python scripts/verify_llm_chain.py
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Load .env so this can be run standalone
def _load_env(p: Path) -> None:
    if not p.exists():
        return
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        k = k.strip()
        v = v.strip().strip('"').strip("'")
        if k and v and k not in os.environ:
            os.environ[k] = v


for env_file in (Path(".env"), Path("backend/.env"),
                 Path("deploy/cn-serverless/.env")):
    _load_env(env_file)

# Force stdout to UTF-8 on Windows
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
except Exception:
    pass

from src.common.multi_provider_llm import (  # noqa: E402
    DEFAULT_CHAIN_ORDER, _all_providers, LLMRequest,
)


PROMPT_SYS = "你是一个有帮助的助手。"
PROMPT_USER = "用 10 个汉字写一句关于秋天的诗。"


def short(s: str, n: int = 80) -> str:
    s = (s or "").replace("\n", " ").strip()
    return s if len(s) <= n else s[: n - 3] + "..."


def main() -> int:
    catalog = _all_providers()
    print(f"{'='*70}")
    print(f"Phase 2 LLM 后备链验证 — {len(catalog)} 个 provider")
    print(f"{'='*70}\n")

    results: list[tuple[str, str, float, str]] = []
    req = LLMRequest(system=PROMPT_SYS, user=PROMPT_USER,
                     json_mode=False, max_tokens=80, temperature=0.5)

    for name in DEFAULT_CHAIN_ORDER:
        p = catalog.get(name)
        if p is None:
            continue
        if not p.is_available():
            print(f"  [SKIP] {name:<12} — 缺 key")
            results.append((name, "NO_KEY", 0.0, ""))
            continue
        print(f"  [...]  {name:<12} 调用中...", end="", flush=True)
        t0 = time.time()
        try:
            out = p.complete(req)
            dt = time.time() - t0
            if out:
                print(f"\r  [OK]   {name:<12} {dt:5.1f}s -> {short(out)}")
                results.append((name, "OK", dt, short(out)))
            else:
                print(f"\r  [FAIL] {name:<12} {dt:5.1f}s -> (空响应)")
                results.append((name, "EMPTY", dt, ""))
        except Exception as e:
            dt = time.time() - t0
            print(f"\r  [ERR]  {name:<12} {dt:5.1f}s -> {short(str(e))}")
            results.append((name, "ERR", dt, short(str(e))))

    ok = sum(1 for _, s, _, _ in results if s == "OK")
    no_key = sum(1 for _, s, _, _ in results if s == "NO_KEY")
    fail = len(results) - ok - no_key

    print(f"\n{'='*70}")
    print(f"汇总: {ok} 可用 | {no_key} 缺 key | {fail} 失败")
    print(f"{'='*70}")
    if ok == 0:
        print("\n[!] 没有可用 provider — 至少配 1 个 key 才能跑非 mock 流水线")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
