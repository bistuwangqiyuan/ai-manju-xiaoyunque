#!/usr/bin/env python3
"""Deploy Event-type xyq-api to CloudBase BaaS and verify core endpoints."""
from __future__ import annotations

import argparse
import pathlib
import re
import subprocess
import sys

REPO = pathlib.Path(__file__).resolve().parents[1]
MINI = REPO / "deploy" / "cloudfn-minimal"
ENV_SIMPLE = REPO / "deploy" / "cn-serverless" / ".env.simple"


def _load_env() -> dict[str, str]:
    out: dict[str, str] = {}
    if ENV_SIMPLE.exists():
        for line in ENV_SIMPLE.read_text(encoding="utf-8").splitlines():
            m = re.match(r"^\s*([A-Z_][A-Z0-9_]*)=(.*)$", line)
            if m:
                v = m.group(2).strip().strip('"').strip("'")
                if v:
                    out[m.group(1)] = v
    return out


def _run(cmd: str) -> int:
    print(f"\n>>> {cmd}")
    return subprocess.run(cmd, shell=True, cwd=str(REPO)).returncode


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-verify", action="store_true")
    args = ap.parse_args()

    cfg = _load_env()
    env_id = cfg.get("ENV_ID", "")
    if not env_id:
        print("Missing ENV_ID", file=sys.stderr)
        return 2

    catalog_src = REPO / "web" / "public" / "samples" / "catalog.json"
    if catalog_src.is_file():
        (MINI / "catalog.json").write_bytes(catalog_src.read_bytes())

    if _run("python scripts/sync_sample_assets.py") != 0:
        return 1

    if _run(
        f'tcb fn deploy xyq-api --env-id {env_id} --dir deploy/cloudfn-minimal '
        f'--force --runtime Python3.9'
    ):
        return 1

    api_base = cfg.get("API_URL") or f"https://{env_id}.service.tcloudbase.com"
    print(f"\nAPI base: {api_base}")

    if not args.skip_verify:
        return _run(
            f"python scripts/verify_cloudbase_live.py --base-url {api_base.rstrip('/')}"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
