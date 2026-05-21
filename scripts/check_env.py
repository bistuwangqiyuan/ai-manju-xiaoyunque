#!/usr/bin/env python3
"""Verify runtime dependencies and API keys for the AI manhua pipeline."""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]

# (env_var, required_for_production, description)
KEYS = [
    ("VOLC_ACCESS_KEY", True, "火山 IAM AK — 小云雀/Seedream"),
    ("VOLC_SECRET_KEY", True, "火山 IAM SK"),
    ("VOLC_ARK_API_KEY", True, "豆包 Seed 1.6 / Ark"),
    ("ANTHROPIC_API_KEY", True, "Claude Opus 编剧"),
    ("DEEPSEEK_API_KEY", True, "DeepSeek 事件抽取"),
    ("GEMINI_API_KEY", True, "Gemini schema 校验"),
    ("ELEVENLABS_API_KEY", True, "BGM / SFX"),
    ("FAL_API_KEY", True, "InfiniteYou / FLUX / Wan"),
    ("DOUBAO_TTS_APPID", False, "豆包 TTS"),
    ("DOUBAO_TTS_TOKEN", False, "豆包 TTS token"),
    ("REPLICATE_API_TOKEN", False, "PuLID"),
    ("OPENAI_API_KEY", False, "Sora 2 Pro 高光集"),
    ("GOOGLE_CLOUD_PROJECT", False, "Veo 3.1"),
    ("RUNWAY_API_KEY", False, "Runway Aleph"),
    ("HEDRA_API_KEY", False, "Hedra lip-sync"),
    ("MINIMAX_API_KEY", False, "MiniMax TTS"),
]


def _load_dotenv() -> None:
    env_path = _REPO / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def _check_cmd(name: str, version_args: list[str] | None = None) -> tuple[bool, str]:
    path = shutil.which(name)
    if not path:
        return False, f"MISSING: {name} not in PATH"
    if version_args:
        try:
            out = subprocess.run(
                [path, *version_args],
                capture_output=True,
                text=True,
                timeout=15,
                check=False,
            )
            detail = (out.stdout or out.stderr or "").strip().split("\n")[0][:120]
            return True, f"OK: {path} — {detail}"
        except Exception as e:
            return False, f"FAIL: {name} — {e}"
    return True, f"OK: {path}"


def main() -> int:
    _load_dotenv()
    print("=== 小云雀漫剧 · 环境检查 ===\n")
    ok = True

    print("[系统依赖]")
    for name, args in [
        ("python", ["--version"]),
        ("ffmpeg", ["-version"]),
        ("ffprobe", ["-version"]),
    ]:
        passed, msg = _check_cmd(name, args)
        print(f"  {'✓' if passed else '✗'} {msg}")
        ok = ok and passed

    print("\n[API Keys]")
    required_missing = []
    for var, required, desc in KEYS:
        val = os.environ.get(var, "").strip()
        if val:
            print(f"  ✓ {var} ({desc})")
        else:
            mark = "✗ REQUIRED" if required else "○ optional"
            print(f"  {mark} {var} — {desc}")
            if required:
                required_missing.append(var)
                ok = False

    print("\n[目录]")
    for rel in ["src", "prompts", "config", "compliance", "backend/app"]:
        p = _REPO / rel
        exists = p.exists()
        print(f"  {'✓' if exists else '✗'} {rel}")
        ok = ok and exists

    if required_missing:
        print(f"\n缺少必备 Key ({len(required_missing)}): {', '.join(required_missing)}")
        print("复制 .env.example → .env 并填入后重试。")
    elif ok:
        print("\n全部检查通过，可运行真实流水线。")
    else:
        print("\n部分可选项未配置，mock 模式仍可用。")

    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
