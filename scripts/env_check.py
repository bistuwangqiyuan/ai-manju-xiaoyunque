"""env_check — preflight environment validator (v8 deploy package).

Usage:
    python scripts/env_check.py
    python scripts/env_check.py --strict        # fail on any missing optional key
    python scripts/env_check.py --json          # machine-readable output

Reads the current process env (Railway / Vercel / local .env) and reports:

- ✅ Configured: required & optional keys that are set.
- ❌ Missing: required keys that are absent.
- ⚠️  Mocked: optional keys absent and a FORCE_MOCK_* flag covers them.
- 📊 % configured gauge: simple readiness metric.

Exit codes:
    0 — all REQUIRED keys present
    1 — any REQUIRED key missing
    2 — any UNKNOWN key set (with --strict)
"""
from __future__ import annotations

import argparse
import io
import json
import os
import sys
from dataclasses import dataclass, field
from typing import Iterable


# Windows PowerShell defaults to GBK and dies on emoji. Force UTF-8 on stdout.
if sys.platform.startswith("win") and isinstance(sys.stdout, io.TextIOWrapper):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


REQUIRED_KEYS: dict[str, str] = {
    "JWT_SECRET": "Auth — JWT signing secret (≥ 32 chars).",
    "DATABASE_URL": "DB — sqlite:///./data.db or Postgres URL.",
    "VOLC_ACCESS_KEY": "Volcengine — Skylark / Seedream / 即梦 / Doubao 公共凭证.",
    "VOLC_SECRET_KEY": "Volcengine — same as VOLC_ACCESS_KEY.",
    "ANTHROPIC_API_KEY": "Claude Opus 4.7 主笔.",
    "DEEPSEEK_API_KEY": "DeepSeek V4-Pro 事件抽取.",
    "DOUBAO_API_KEY": "Doubao Seed 1.6 Vision 7-dim 质检.",
    "DOUBAO_TTS_APPID": "Doubao Seed-TTS 2.0 ICL 主路配音.",
    "DOUBAO_TTS_TOKEN": "Doubao TTS access token.",
    "ELEVENLABS_API_KEY": "ElevenLabs Music + SFX + Multilingual TTS.",
    "FAL_API_KEY": "FAL — FLUX Kontext + InfiniteYou + Wan FLF.",
    "REPLICATE_API_TOKEN": "Replicate PuLID 多角色锁.",
}

OPTIONAL_KEYS: dict[str, tuple[str, str]] = {
    # key: (description, mock-flag that covers absence)
    "GEMINI_API_KEY": ("Gemini 2.5 Pro schema 校验 + 字幕翻译", "FORCE_MOCK_TRANSLATE"),
    "GOOGLE_CLOUD_PROJECT": ("Veo 3.1 精修 + 4K 上采", ""),
    "GOOGLE_ACCESS_TOKEN": ("Veo 3.1 服务账号 OAuth token", ""),
    "OPENAI_API_KEY": ("Sora 2 Pro ep09 封神镜头", ""),
    "RUNWAY_API_KEY": ("Runway Aleph 跨集风格统一", ""),
    "HEDRA_API_KEY": ("Hedra Character-3 lip-sync 修复", ""),
    "DASHSCOPE_API_KEY": ("DashScope Wan 2.2-Animate 武打迁移", "FORCE_MOCK_WAN_ANIMATE"),
    "MINIMAX_API_KEY": ("MiniMax Speech 2.5 HD 情感配音", "FORCE_MOCK_TTS_MINIMAX"),
    "SUNO_API_KEY": ("Suno Chirp Premier v5.5 主题曲", ""),
    "KLING_API_KEY": ("可灵 2.5 备用动作戏", ""),
    "NETEASE_TIANYIN_API_KEY": ("网易天音 中文古风 BGM", ""),
    "VOLC_ARK_API_KEY": ("Seedance fallback + Doubao Ark 兼容", ""),
    "STRIPE_SECRET_KEY": ("Stripe live billing (生产可选)", ""),
    "STRIPE_WEBHOOK_SECRET": ("Stripe webhook (生产可选)", ""),
    "CORS_ORIGINS": ("Cross-origin 来源（前端域名）", ""),
    "SITE_URL": ("Stripe redirect base URL", ""),
    "STORAGE_BACKEND": ("local | s3 | tos | oss", ""),
    "STORAGE_DIR": ("Local artifact storage", ""),
    "S3_ENDPOINT": ("S3-compatible endpoint", ""),
    "S3_BUCKET": ("S3 bucket name", ""),
}


def _domestic_mode() -> bool:
    return os.environ.get("CN_DOMESTIC_MODE", "").strip() in ("1", "true", "yes")


def _effective_required_keys() -> dict[str, str]:
    """CN_DOMESTIC_MODE=1: 国产 Key 替代海外必填项."""
    keys = dict(REQUIRED_KEYS)
    if not _domestic_mode():
        return keys
    # 编剧: multi-LLM chain (DeepSeek/GLM/通义) 替代 Anthropic
    keys.pop("ANTHROPIC_API_KEY", None)
    # 配音: 豆包 TTS 替代 ElevenLabs
    keys.pop("ELEVENLABS_API_KEY", None)
    # 图像: Seedream/即梦(VOLC) 替代 FAL + Replicate PuLID
    keys.pop("FAL_API_KEY", None)
    keys.pop("REPLICATE_API_TOKEN", None)
    return keys


KNOWN_MOCK_FLAGS = {
    "MOCK_MODE",
    "FORCE_MOCK_SCORER",
    "FORCE_MOCK_THEME",
    "FORCE_MOCK_NOVELTY",
    "FORCE_MOCK_MARKETING",
    "FORCE_MOCK_CONTINUATION",
    "FORCE_MOCK_RESTYLE",
    "FORCE_MOCK_TRANSLATE",
    "FORCE_MOCK_REDRAW",
    "FORCE_MOCK_WAN_ANIMATE",
    "FORCE_MOCK_TTS_MINIMAX",
    "SKIP_CINEMATIC_MASTER",
    "USE_REAL_COVER",
    "USE_REAL_UPSCALER",
    "USE_REAL_WAN_ANIMATE",
    "USE_C2PATOOL",
    "AIGC_CONTENT_PRODUCER",
    "AIGC_CONTENT_PROPAGATOR",
    "AIGC_PROPAGATE_ID",
    "ANTHROPIC_MODEL",
    "ANTHROPIC_BASE_URL",
    "ANTHROPIC_AUTH_TOKEN",
    "GOOGLE_VERTEX_LOCATION",
    "LOG_LEVEL",
    "WORKER_POLL_INTERVAL",
    "SKYLARK_REQ_KEY_CACHE",
    "FORCE_MOCK_TTS_ELEVENLABS",
    "FORCE_MOCK_MANJU_AGENT",
    "CN_DOMESTIC_MODE",
    "LLM_PROVIDER_CHAIN",
    "SCHEMA_VALIDATOR",
    "TTS_PRIMARY",
    "IMAGE_GEN_PRIMARY",
    "DOUBAO_TTS_CLUSTER",
    # 漫剧 Agent (v9)
    "MANJU_AGENT_MODE",
    "MANJU_REQ_KEY",
    # TOS object storage (v9)
    "TOS_BUCKET",
    "TOS_ENDPOINT",
    "TOS_REGION",
    "TOS_PREFIX",
    # NAS persistent data (v9)
    "NAS_MOUNT_PATH",
    "PYTHONPATH",
    "PATH",
    "PORT",
    "RAILWAY_TOKEN",
    "VERCEL_TOKEN",
    "VERCEL_ORG_ID",
    "VERCEL_PROJECT_ID",
    "SIGNUP_BONUS_CENTS",
}


@dataclass
class CheckReport:
    required_present: list[str] = field(default_factory=list)
    required_missing: list[tuple[str, str]] = field(default_factory=list)
    optional_present: list[str] = field(default_factory=list)
    optional_mocked: list[tuple[str, str, str]] = field(default_factory=list)
    optional_absent: list[tuple[str, str]] = field(default_factory=list)
    unknown_set: list[str] = field(default_factory=list)

    @property
    def configured_percent(self) -> int:
        req_total = len(self.required_present) + len(self.required_missing)
        denom = req_total + len(OPTIONAL_KEYS)
        num = len(self.required_present) + len(self.optional_present)
        return round(100 * num / denom) if denom else 0


def _has(key: str) -> bool:
    return bool(os.environ.get(key, "").strip())


def run_check(*, env: dict[str, str] | None = None) -> CheckReport:
    if env is not None:
        # rehydrate env for testing
        os.environ.update(env)

    report = CheckReport()
    required = _effective_required_keys()
    for key, why in required.items():
        if _has(key):
            report.required_present.append(key)
        else:
            report.required_missing.append((key, why))

    for key, (why, mock_flag) in OPTIONAL_KEYS.items():
        if _has(key):
            report.optional_present.append(key)
        elif mock_flag and _has(mock_flag):
            report.optional_mocked.append((key, why, mock_flag))
        else:
            report.optional_absent.append((key, why))

    known = set(REQUIRED_KEYS) | set(OPTIONAL_KEYS) | KNOWN_MOCK_FLAGS
    for key in os.environ:
        if (
            key not in known
            and not key.startswith("_")
            and not key.startswith("npm_")
            and not key.startswith("VERCEL_")
            and not key.startswith("RAILWAY_")
        ):
            # only flag clearly project-relevant prefixes
            if any(p in key for p in ("API", "TOKEN", "KEY", "SECRET", "MOCK_", "ANTHROPIC", "VOLC", "DOUBAO")):
                report.unknown_set.append(key)
    return report


def _emoji(present: bool) -> str:
    return "✅" if present else "❌"


def _print_human(report: CheckReport) -> None:
    print("AI 漫剧 v8 — env_check report")
    print("=" * 56)
    req_total = len(report.required_present) + len(report.required_missing)
    print(f"REQUIRED keys: {len(report.required_present)}/{req_total}"
          + (" (CN_DOMESTIC_MODE)" if _domestic_mode() else ""))
    for key in report.required_present:
        print(f"  ✅ {key}")
    for key, why in report.required_missing:
        print(f"  ❌ {key}  — {why}")

    print()
    print(f"OPTIONAL keys: {len(report.optional_present)}/{len(OPTIONAL_KEYS)}")
    for key in report.optional_present:
        print(f"  ✅ {key}")
    for key, why, flag in report.optional_mocked:
        print(f"  ⚠️  {key}  — covered by {flag}=1  ({why})")
    for key, why in report.optional_absent:
        print(f"  ⛔ {key}  — NOT SET, NO MOCK ({why})")

    if report.unknown_set:
        print()
        print("Unknown / non-canonical env keys (review for typos):")
        for k in report.unknown_set:
            print(f"  ? {k}")

    print()
    pct = report.configured_percent
    bar = "█" * (pct // 4) + "░" * (25 - pct // 4)
    print(f"📊 configured {pct:3d}% [{bar}]")
    print(f"   MOCK_MODE={os.environ.get('MOCK_MODE','0')} "
          f"USE_REAL_COVER={os.environ.get('USE_REAL_COVER','0')} "
          f"USE_REAL_UPSCALER={os.environ.get('USE_REAL_UPSCALER','0')}")
    if report.required_missing:
        print()
        print("❌ Required keys missing — set them before production deploy.")
    else:
        print()
        print("✅ All REQUIRED keys are present. Ready for staging.")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="env_check")
    p.add_argument("--json", action="store_true", help="JSON output for CI")
    p.add_argument("--strict", action="store_true", help="exit 2 if unknown keys set")
    args = p.parse_args(argv)

    report = run_check()

    if args.json:
        payload = {
            "required_present": report.required_present,
            "required_missing": [k for k, _ in report.required_missing],
            "optional_present": report.optional_present,
            "optional_mocked": [k for k, _, _ in report.optional_mocked],
            "optional_absent": [k for k, _ in report.optional_absent],
            "unknown_set": report.unknown_set,
            "configured_percent": report.configured_percent,
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        _print_human(report)

    if report.required_missing:
        return 1
    if args.strict and report.unknown_set:
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
