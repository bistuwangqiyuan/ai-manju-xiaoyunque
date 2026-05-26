#!/usr/bin/env python3
"""autofill_env — 全自动聚合 / 发现 / 写入 API keys 与云资源配置.

数据源 (优先级从高到低):
  1. 已有 .env 文件 (用户手填优先)
  2. ve configure list / aliyun configure list (CLI 已登录凭证)
  3. tosutil ls / ve ark ListEndpoints (云资源发现)
  4. prompt.md / .env.example 等项目内已知 key
  5. secrets.token_urlsafe 生成 JWT_SECRET 等

用法:
    python scripts/autofill_env.py
    python scripts/autofill_env.py --apply-setup   # 写完 env 后跑 MCP setup 脚本
    python scripts/autofill_env.py --verify        # 写完 env 后 smoke-test 关键 key
"""
from __future__ import annotations

import argparse
import io
import json
import os
import re
import secrets
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

# Windows UTF-8
if sys.platform.startswith("win"):
    for stream in (sys.stdout, sys.stderr):
        if isinstance(stream, io.TextIOWrapper):
            try:
                stream.reconfigure(encoding="utf-8", errors="replace")
            except Exception:
                pass

ENV_TARGETS = [
    ROOT / ".env",
    ROOT / "backend" / ".env",
    ROOT / "deploy" / "cn-serverless" / ".env",
]

SCAN_FILES = [
    ROOT / ".env",
    ROOT / ".env.example",
    ROOT / "backend" / ".env",
    ROOT / "backend" / ".env.example",
    ROOT / "deploy" / "cn-serverless" / ".env",
    ROOT / "deploy" / "cn-serverless" / ".env.example",
    ROOT / "deploy" / "cn-serverless" / ".env.simple",
    ROOT / "prompt.md",
]

PLACEHOLDER_RE = re.compile(
    r"^(your_|YOUR_|<|\$\{|请改|请填|replace_with|STRONG_PASSWORD|xxxx|AKIDxxxx|"
    r"PLACEHOLDER|example|changeme|dev-secret)",
    re.I,
)

KEY_LINE_RE = re.compile(r"^\s*([A-Za-z_][A-Za-z0-9_]*)=(.*)$")

# 别名: 填主键时同步填别名 (仅当别名空)
ALIASES: dict[str, list[str]] = {
    "VOLC_ARK_API_KEY": ["DOUBAO_API_KEY", "ARK_API_KEY", "VOLCENGINE_API_KEY"],
    "DOUBAO_API_KEY": ["VOLC_ARK_API_KEY"],
    "TONGYI_API_KEY": [],  # dashscope 可共用
    "DASHSCOPE_API_KEY": [],
    "VOLC_ACCESS_KEY": ["VOLCENGINE_ACCESS_KEY", "S3_ACCESS_KEY"],
    "VOLC_SECRET_KEY": ["VOLCENGINE_SECRET_KEY", "S3_SECRET_KEY"],
    "ALIBABA_CLOUD_ACCESS_KEY_ID": ["ALIYUN_ACCESS_KEY_ID", "S3_ACCESS_KEY"],
    "ALIBABA_CLOUD_ACCESS_KEY_SECRET": ["ALIYUN_ACCESS_KEY_SECRET", "S3_SECRET_KEY"],
}

# CLI 发现写入的派生键
DERIVED_FROM_DISCOVERY: dict[str, str] = {}


def _strip_inline_comment(val: str) -> str:
    """Remove trailing # comment; keep values that are purely quoted."""
    v = val.strip().strip('"').strip("'")
    if "#" in v:
        # only strip if # is preceded by whitespace (inline comment)
        parts = re.split(r"\s+#", v, maxsplit=1)
        if len(parts) == 2 and parts[0].strip():
            v = parts[0].strip()
    return v


def _is_real(val: str) -> bool:
    v = _strip_inline_comment(val)
    if not v or len(v) < 4:
        return False
    if v.startswith("#"):
        return False
    return not PLACEHOLDER_RE.match(v)


def parse_env_file(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    if not path.exists():
        return out
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        m = KEY_LINE_RE.match(line)
        if not m:
            continue
        k, v = m.group(1), _strip_inline_comment(m.group(2))
        if _is_real(v):
            out[k] = v
    return out


def parse_markdown_keys(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    if not path.exists():
        return out
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        m = KEY_LINE_RE.match(line.strip())
        if m:
            k, v = m.group(1), m.group(2).strip().strip('"').strip("'")
            if _is_real(v):
                out[k] = v
    return out


def run_cmd(cmd: list[str], timeout: int = 30) -> tuple[int, str]:
    try:
        env = os.environ.copy()
        home = Path.home()
        extra = [
            str(home / ".volc-tools"),
            str(home / ".aliyun-tools"),
        ]
        env["Path"] = ";".join(extra + [env.get("Path", "")])
        r = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout, env=env,
            check=False, encoding="utf-8", errors="replace",
        )
        return r.returncode, (r.stdout or "") + (r.stderr or "")
    except Exception as e:
        return 1, str(e)


def discover_volc_from_cli() -> dict[str, str]:
    found: dict[str, str] = {}
    code, out = run_cmd(["ve", "configure", "list"])
    if code != 0:
        return found
    # JSON blocks in output
    for block in re.findall(r"\{[^{}]*\"access-key\"[^{}]*\}", out, re.S):
        try:
            obj = json.loads(block)
            ak = obj.get("access-key", "")
            sk = obj.get("secret-key", "")
            region = obj.get("region", "cn-beijing")
            if _is_real(ak) and _is_real(sk):
                found.setdefault("VOLC_ACCESS_KEY", ak)
                found.setdefault("VOLC_SECRET_KEY", sk)
                found.setdefault("VOLC_REGION", region)
                break
        except json.JSONDecodeError:
            continue

    # TOS buckets via tosutil
    code, out = run_cmd(["tosutil", "ls"])
    if code == 0:
        buckets = re.findall(r"tos://([^\s/]+)", out)
        # prefer project-related bucket names
        preferred = [
            b for b in buckets
            if any(x in b.lower() for x in ("manju", "xiaoyun", "xyq"))
        ] or [
            b for b in buckets
            if any(x in b.lower() for x in ("ainovel",))
        ]
        bucket = preferred[0] if preferred else (buckets[0] if buckets else "")
        if bucket:
            found["TOS_BUCKET"] = bucket
            found["S3_BUCKET"] = bucket
            found["STORAGE_BACKEND"] = "tos"
            found["S3_ENDPOINT"] = "https://tos-cn-beijing.volces.com"
            found["S3_REGION"] = "cn-beijing"
            found["TOS_ENDPOINT"] = "https://tos-cn-beijing.volces.com"

    # Ark endpoints
    code, out = run_cmd(["ve", "ark", "ListEndpoints"])
    if code == 0:
        try:
            data = json.loads(out)
            items = data.get("Result", {}).get("Items", [])
            running = [i for i in items if i.get("Status") == "Running"]
            pick = running[0] if running else (items[0] if items else None)
            if pick:
                found["VOLC_ARK_ENDPOINT_ID"] = pick.get("Id", "")
                found["DOUBAO_ENDPOINT_ID"] = pick.get("Id", "")
                model = pick.get("ModelReference", {}).get("FoundationModel", {})
                if model.get("Name"):
                    found.setdefault(
                        "DOUBAO_MODEL",
                        f"{model['Name']}-{model.get('ModelVersion', '')}",
                    )
        except json.JSONDecodeError:
            pass

    found.setdefault("VOLC_ARK_ENDPOINT", "https://ark.cn-beijing.volces.com/api/v3")
    found.setdefault("ARK_BASE_URL", "https://ark.cn-beijing.volces.com/api/v3")
    return found


def discover_aliyun_from_cli() -> dict[str, str]:
    found: dict[str, str] = {}
    code, out = run_cmd(["aliyun", "configure", "list"])
    if code != 0:
        return found
    # table: default * | AK:***pit | Valid | cn-hangzhou
    for line in out.splitlines():
        if "Valid" in line and "AK:" in line:
            # can't get full AK from list; sts for account
            break
    code, out = run_cmd(["aliyun", "sts", "GetCallerIdentity"])
    if code == 0:
        try:
            data = json.loads(out)
            found["ALIYUN_ACCOUNT_ID"] = str(data.get("AccountId", ""))
            found["ALIYUN_RAM_USER"] = data.get("Arn", "").split("/")[-1]
        except json.JSONDecodeError:
            pass
    found.setdefault("OSS_REGION", "cn-hangzhou")
    found.setdefault("OSS_ENDPOINT", "https://oss-cn-hangzhou.aliyuncs.com")
    return found


def generate_secrets() -> dict[str, str]:
    return {
        "JWT_SECRET": secrets.token_urlsafe(48),
        "INTERNAL_API_SECRET": secrets.token_urlsafe(48),
    }


def merge_all() -> dict[str, str]:
    merged: dict[str, str] = {}

    # 1) scan project files (lowest priority among sources we'll layer)
    for p in SCAN_FILES:
        for k, v in {**parse_env_file(p), **parse_markdown_keys(p)}.items():
            merged.setdefault(k, v)

    # 2) CLI discovery overwrites only if key missing
    for src in (discover_volc_from_cli, discover_aliyun_from_cli):
        for k, v in src().items():
            merged.setdefault(k, v)

    # 3) aliases
    for primary, aliases in ALIASES.items():
        if primary in merged:
            for alias in aliases:
                merged.setdefault(alias, merged[primary])

    # DOUBAO = ARK when either exists
    ark = merged.get("VOLC_ARK_API_KEY") or merged.get("DOUBAO_API_KEY")
    if ark:
        merged.setdefault("VOLC_ARK_API_KEY", ark)
        merged.setdefault("DOUBAO_API_KEY", ark)

    # storage keys mirror volc/aliyun
    if merged.get("STORAGE_BACKEND") == "tos":
        merged.setdefault("S3_ACCESS_KEY", merged.get("VOLC_ACCESS_KEY", ""))
        merged.setdefault("S3_SECRET_KEY", merged.get("VOLC_SECRET_KEY", ""))

    # secrets — only if missing or placeholder
    for k, v in generate_secrets().items():
        if not _is_real(merged.get(k, "")):
            merged[k] = v

    # 漫剧 Agent (v9): 默认关闭, 用户设 1 之后才走专用 API
    merged.setdefault("MANJU_AGENT_MODE", "0")
    merged.setdefault("FORCE_MOCK_MANJU_AGENT", "1")
    merged.setdefault("CN_DOMESTIC_MODE", "1")

    return merged


def read_env_sections(path: Path) -> tuple[list[str], dict[str, str]]:
    """Return (lines, key->line_index)."""
    if not path.exists():
        return [], {}
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines(keepends=True)
    idx: dict[str, int] = {}
    for i, line in enumerate(lines):
        m = KEY_LINE_RE.match(line.strip())
        if m:
            idx[m.group(1)] = i
    return lines, idx


def upsert_env(path: Path, updates: dict[str, str], header_if_new: str = "") -> list[str]:
    """Write updates into env file; return list of keys written."""
    path.parent.mkdir(parents=True, exist_ok=True)
    written: list[str] = []

    if not path.exists():
        lines = [header_if_new + "\n"] if header_if_new else []
        idx: dict[str, int] = {}
    else:
        lines, idx = read_env_sections(path)

    for key, val in sorted(updates.items()):
        if not _is_real(val):
            continue
        new_line = f"{key}={val}\n"
        if key in idx:
            old = lines[idx[key]].strip()
            old_val = old.split("=", 1)[1] if "=" in old else ""
            if _is_real(old_val):
                continue  # don't overwrite user values
            lines[idx[key]] = new_line
            written.append(key)
        else:
            if lines and not lines[-1].endswith("\n"):
                lines[-1] += "\n"
            lines.append(new_line)
            written.append(key)

    path.write_text("".join(lines), encoding="utf-8")
    return written


def apply_to_targets(merged: dict[str, str]) -> dict[str, list[str]]:
    results: dict[str, list[str]] = {}

    # .env — full AI + cloud keys
    ai_keys = {
        k: v for k, v in merged.items()
        if any(
            p in k
            for p in (
                "VOLC", "ARK", "DOUBAO", "ANTHROPIC", "DEEPSEEK", "GEMINI",
                "MISTRAL", "GLM", "TONGYI", "DASHSCOPE", "MOONSHOT", "GROQ",
                "XAI", "SPARK", "ELEVEN", "FAL_", "REPLICATE", "OPENAI",
                "RUNWAY", "HEDRA", "MINIMAX", "SUNO", "KLING", "NETEASE",
                "ALIBABA", "ALIYUN", "OSS_", "TOS_", "S3_", "STORAGE",
                "JWT", "INTERNAL", "MOCK", "DATABASE", "TENCENT", "COS_",
                "MANJU_", "NAS_", "CN_DOMESTIC_MODE",
            )
        )
    }
    results[".env"] = upsert_env(
        ROOT / ".env",
        ai_keys,
        "# 小云雀 AI 漫剧 · 本地开发 (autofill_env.py 自动生成/补全)\n",
    )

    # backend/.env
    backend_keys = {
        k: merged[k]
        for k in (
            "JWT_SECRET", "DATABASE_URL", "VOLC_ACCESS_KEY", "VOLC_SECRET_KEY",
            "VOLC_ARK_API_KEY", "DOUBAO_API_KEY", "ANTHROPIC_API_KEY",
            "DEEPSEEK_API_KEY", "DASHSCOPE_API_KEY", "GEMINI_API_KEY",
            "ELEVENLABS_API_KEY", "FAL_API_KEY", "REPLICATE_API_TOKEN",
            "DOUBAO_TTS_APPID", "DOUBAO_TTS_TOKEN", "MOCK_MODE",
        )
        if k in merged
    }
    results["backend/.env"] = upsert_env(ROOT / "backend" / ".env", backend_keys)

    # deploy/cn-serverless/.env
    deploy_keys = {k: v for k, v in merged.items() if k in merged}
    results["deploy/cn-serverless/.env"] = upsert_env(
        ROOT / "deploy" / "cn-serverless" / ".env", deploy_keys
    )
    return results


def run_setup_scripts() -> None:
    ps1_volc = ROOT / "scripts" / "setup_volc_mcp.ps1"
    ps1_ali = ROOT / "scripts" / "setup_aliyun_mcp.ps1"
    for script in (ps1_volc, ps1_ali):
        if not script.exists():
            continue
        print(f"\n>>> Running {script.name} ...")
        run_cmd(
            [
                "powershell", "-NoProfile", "-ExecutionPolicy", "Bypass",
                "-File", str(script),
            ],
            timeout=120,
        )


def smoke_test_keys(merged: dict[str, str]) -> list[tuple[str, str, str]]:
    """Return [(key, status, detail)]"""
    import urllib.error
    import urllib.request

    results: list[tuple[str, str, str]] = []

    def _post_json(url: str, headers: dict, body: dict, timeout: int = 15) -> tuple[int, str]:
        req = urllib.request.Request(
            url,
            data=json.dumps(body).encode(),
            headers={**headers, "Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.status, resp.read()[:200].decode(errors="replace")
        except urllib.error.HTTPError as e:
            return e.code, e.read()[:200].decode(errors="replace")
        except Exception as e:
            return 0, str(e)

    ark = merged.get("VOLC_ARK_API_KEY") or merged.get("DOUBAO_API_KEY")
    if ark:
        code, body = _post_json(
            "https://ark.cn-beijing.volces.com/api/v3/chat/completions",
            {"Authorization": f"Bearer {ark}"},
            {"model": "doubao-seed-1-6-250615", "messages": [{"role": "user", "content": "ping"}], "max_tokens": 5},
        )
        status = "OK" if code == 200 else f"HTTP_{code}"
        results.append(("VOLC_ARK_API_KEY", status, body[:80]))

    ds = merged.get("DASHSCOPE_API_KEY")
    if ds:
        code, body = _post_json(
            "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions",
            {"Authorization": f"Bearer {ds}"},
            {"model": "qwen-max-latest", "messages": [{"role": "user", "content": "ping"}], "max_tokens": 5},
        )
        status = "OK" if code == 200 else f"HTTP_{code}"
        results.append(("DASHSCOPE_API_KEY", status, body[:80]))

    return results


def print_report(merged: dict[str, str], written: dict[str, list[str]]) -> None:
    sys.path.insert(0, str(ROOT))
    from scripts.env_check import run_check

    print("\n" + "=" * 60)
    print("autofill_env — 写入报告")
    print("=" * 60)
    for target, keys in written.items():
        print(f"\n[{target}] 新写入/补全 {len(keys)} 项:")
        for k in keys[:30]:
            v = merged.get(k, "")
            mask = v[:6] + "***" if len(v) > 6 else v
            print(f"  + {k} = {mask}")
        if len(keys) > 30:
            print(f"  ... +{len(keys) - 30} more")

    # load .env into os.environ for check
    for p in ENV_TARGETS:
        for k, v in parse_env_file(p).items():
            os.environ.setdefault(k, v)

    print("\n--- env_check (required keys) ---")
    report = run_check()
    for k in report.required_present:
        print(f"  ✅ {k}")
    for k, why in report.required_missing:
        print(f"  ❌ {k} — {why}")
    print(f"\n📊 configured {report.configured_percent}%")

    cannot_auto = [
        "DOUBAO_TTS_APPID", "DOUBAO_TTS_TOKEN",
        "ELEVENLABS_API_KEY", "FAL_API_KEY", "REPLICATE_API_TOKEN",
    ]
    missing_auto = [k for k in cannot_auto if not _is_real(merged.get(k, ""))]
    if missing_auto:
        print("\n⚠️  以下 Key 无法通过 CLI 自动创建 (需各平台控制台/API 开通):")
        for k in missing_auto:
            print(f"     - {k}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply-setup", action="store_true", help="运行 setup_*_mcp.ps1")
    ap.add_argument("--verify", action="store_true", help="smoke-test 关键 API key")
    args = ap.parse_args()

    print("autofill_env — 聚合 CLI + 项目文件 + 云发现 ...")
    merged = merge_all()
    written = apply_to_targets(merged)
    print_report(merged, written)

    if args.verify:
        print("\n--- smoke tests ---")
        for key, status, detail in smoke_test_keys(merged):
            print(f"  {key}: {status} — {detail[:60]}")

    if args.apply_setup:
        run_setup_scripts()
        print("\n✅ setup 脚本已执行。请 Cursor → Reload Window 加载 MCP。")

    return 0


if __name__ == "__main__":
    sys.exit(main())
