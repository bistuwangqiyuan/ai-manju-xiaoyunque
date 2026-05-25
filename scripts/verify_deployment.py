"""Post-deploy 验证: 取 veFaaS 函数 URL, curl /healthz + /api/health, 回填 .env.

跑这个脚本会自动:
  1. 用 ve CLI 拿 xyq-manju 函数信息 (ListFunctions → 找 Name=xyq-manju)
  2. 解析 trigger URL (TriggerInfo.Endpoint 或 BackendURL)
  3. curl https://<url>/healthz 应返回 200 "ok"
  4. curl https://<url>/api/health 应返回 200 JSON
  5. 把域名回填到本地 .env (SITE_URL, CORS_ORIGINS, BACKEND_URL)
  6. 把域名同步到 GitHub Secrets (SITE_URL)

Usage:
  python scripts/verify_deployment.py
  python scripts/verify_deployment.py --function-name xyq-manju --update-env
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import subprocess
import sys
import time
import urllib.error
import urllib.request

_REPO = pathlib.Path(__file__).resolve().parent.parent


def _run(cmd: list[str], *, check: bool = True, timeout: float = 60.0) -> str:
    try:
        r = subprocess.run(cmd, capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=timeout)
        if check and r.returncode != 0:
            print(f"[err] {' '.join(cmd[:3])}... exit={r.returncode}\n{r.stderr[:400]}",
                  file=sys.stderr)
            return ""
        return r.stdout
    except FileNotFoundError:
        print(f"[err] command not found: {cmd[0]}", file=sys.stderr)
        return ""


def _find_function(name: str) -> dict | None:
    """Use ve CLI to find function with given name."""
    out = _run(["ve", "vefaas", "ListFunctions"])
    if not out:
        return None
    try:
        data = json.loads(out)
    except json.JSONDecodeError:
        print(f"[err] could not parse ListFunctions: {out[:200]}", file=sys.stderr)
        return None
    items = (data.get("Result") or {}).get("Items") or []
    for it in items:
        if (it.get("Name") or "") == name:
            return it
    print(f"[warn] function {name!r} not in list ({len(items)} functions)",
          file=sys.stderr)
    return None


def _get_function_detail(fid: str) -> dict | None:
    """Get full function detail (incl. triggers/URL) via GetFunction."""
    out = _run(["ve", "vefaas", "GetFunction", "--Id", fid])
    if not out:
        return None
    try:
        return (json.loads(out).get("Result") or {})
    except json.JSONDecodeError:
        return None


def _list_function_triggers(fid: str) -> list[dict]:
    """List triggers; veFaaS function URL usually comes from APIGW trigger."""
    out = _run(["ve", "vefaas", "ListTriggers", "--FunctionId", fid], check=False)
    if not out:
        return []
    try:
        return ((json.loads(out).get("Result") or {}).get("Items") or [])
    except json.JSONDecodeError:
        return []


def _curl(url: str, *, timeout: float = 30.0,
          expect_status: int = 200) -> tuple[bool, str]:
    """Return (success, snippet)."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "verify_deployment/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            body = r.read(4096).decode("utf-8", errors="replace")
            ok = (r.status == expect_status)
            return ok, f"HTTP {r.status} | {body[:300]}"
    except urllib.error.HTTPError as e:
        return (e.code == expect_status), f"HTTP {e.code} | {e.read(2048).decode('utf-8','replace')[:300]}"
    except Exception as e:
        return False, f"{type(e).__name__}: {e}"


def _update_env_file(path: pathlib.Path, kv: dict[str, str]) -> int:
    if not path.exists():
        return 0
    txt = path.read_text(encoding="utf-8", errors="replace")
    updated = 0
    for k, v in kv.items():
        marker = f"{k}="
        new_line = f"{k}={v}"
        if any(line.startswith(marker) for line in txt.splitlines()):
            new_lines = []
            for line in txt.splitlines():
                if line.startswith(marker):
                    new_lines.append(new_line); updated += 1
                else:
                    new_lines.append(line)
            txt = "\n".join(new_lines) + "\n"
        else:
            txt += f"\n{new_line}\n"; updated += 1
    path.write_text(txt, encoding="utf-8")
    return updated


def _sync_gh_secret(repo: str, key: str, value: str) -> bool:
    proc = subprocess.run(
        ["gh", "secret", "set", key, "--repo", repo],
        input=value, capture_output=True, text=True, encoding="utf-8",
    )
    return proc.returncode == 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="verify_deployment")
    parser.add_argument("--function-name", default="xyq-manju")
    parser.add_argument("--update-env", action="store_true",
                        help="write domain back to .env files")
    parser.add_argument("--sync-gh-secret", action="store_true",
                        help="also sync SITE_URL to GitHub Secrets")
    parser.add_argument("--gh-repo", default="bistuwangqiyuan/ai-manju-xiaoyunque")
    parser.add_argument("--wait", type=int, default=0,
                        help="wait N seconds and retry function lookup if not found")
    args = parser.parse_args(argv)

    print(f"{'='*72}")
    print(f" verify_deployment  function={args.function_name}")
    print(f"{'='*72}")

    fn = None
    deadline = time.monotonic() + args.wait
    while True:
        fn = _find_function(args.function_name)
        if fn or time.monotonic() >= deadline:
            break
        print(f"[wait] not found yet, sleeping 30s ...")
        time.sleep(30)
    if not fn:
        print(f"\n[FAIL] function {args.function_name!r} not found.\n"
              f"       检查: ve vefaas ListFunctions 是否包含这个名字.")
        return 1

    fid = fn.get("Id") or ""
    print(f"[OK ] function found: id={fid}")
    print(f"      source={fn.get('Source','?')}")
    print(f"      cpu={fn.get('Cpu')} mem={fn.get('MemoryMB')}MB")
    print(f"      created={fn.get('CreationTime')}")
    print(f"      updated={fn.get('LastUpdateTime')}")

    # 找 trigger URL
    triggers = _list_function_triggers(fid)
    print(f"[OK ] {len(triggers)} trigger(s)")
    endpoint = ""
    for t in triggers:
        ep = t.get("Endpoint") or t.get("EndpointUrl") or t.get("URL") or ""
        if ep:
            endpoint = ep.rstrip("/")
            print(f"      trigger {t.get('Type','?')}: {endpoint}")
            break

    if not endpoint:
        # 没有 trigger 时, veFaaS 提供函数自身 URL (BackendURL/DefaultURL)
        detail = _get_function_detail(fid) or {}
        endpoint = (detail.get("DefaultURL") or detail.get("BackendURL")
                    or detail.get("URL") or "").rstrip("/")
        if endpoint:
            print(f"      default function URL: {endpoint}")

    if not endpoint:
        print("\n[FAIL] 函数无 trigger 且无 DefaultURL. 需要去控制台或 APIG 配 route.")
        print("      https://console.volcengine.com/vefaas/region:vefaas+cn-beijing/function")
        return 2

    print()
    print(f"[curl] {endpoint}/healthz ...")
    ok, msg = _curl(f"{endpoint}/healthz")
    print(f"        {'OK' if ok else 'FAIL'}: {msg}")
    healthz_ok = ok

    print(f"[curl] {endpoint}/api/health ...")
    ok, msg = _curl(f"{endpoint}/api/health")
    print(f"        {'OK' if ok else 'FAIL'}: {msg}")
    api_ok = ok

    # 回填 .env
    if args.update_env:
        kv = {
            "SITE_URL":     endpoint,
            "BACKEND_URL":  endpoint,
            "CORS_ORIGINS": endpoint,
        }
        for envp in (_REPO / ".env", _REPO / "backend" / ".env",
                     _REPO / "deploy" / "cn-volc-vefaas" / ".env"):
            n = _update_env_file(envp, kv)
            if n:
                print(f"[upd] {envp.relative_to(_REPO)}: {n} keys updated")

    if args.sync_gh_secret:
        if _sync_gh_secret(args.gh_repo, "SITE_URL", endpoint):
            print(f"[gh ] synced SITE_URL to {args.gh_repo}")
        else:
            print(f"[gh ] sync SITE_URL failed (skipped)")

    print()
    print(f"{'='*72}")
    print(f"  公网域名: {endpoint}")
    print(f"  /healthz:    {'PASS' if healthz_ok else 'FAIL'}")
    print(f"  /api/health: {'PASS' if api_ok    else 'FAIL'}")
    print(f"{'='*72}")
    return 0 if (healthz_ok or api_ok) else 3


if __name__ == "__main__":
    raise SystemExit(main())
