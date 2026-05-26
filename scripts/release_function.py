"""Manually trigger a veFaaS function Release (publish current revision).

Useful when:
  - GitHub Actions deploy step succeeded at UpdateFunction but failed at
    Release because CR image sync was still running.
  - You want to roll a new traffic cut without rebuilding the image.

Usage:
    python scripts/release_function.py --function-id 0mt4ej8a
    python scripts/release_function.py --function-name xyq-manju
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import sys
import winreg
from datetime import datetime, timezone

# Use deploy.py's signer (correctly handles vefaas Content-Type)
ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "deploy" / "cn-volc-vefaas"))
sys.path.insert(0, str(ROOT))
from deploy import (  # noqa: E402
    VeApiClient, VEFAAS_SERVICE, VEFAAS_VERSION, _is_placeholder,
)


def _reg(name: str) -> str:
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as k:
            return str(winreg.QueryValueEx(k, name)[0])
    except (OSError, FileNotFoundError):
        return ""


def _good(name: str) -> str:
    v = os.environ.get(name, "").strip()
    if not v or _is_placeholder(v):
        v = _reg(name).strip()
    return v


def _find_fid_by_name(client: VeApiClient, name: str) -> str:
    r = client.call(service=VEFAAS_SERVICE, action="ListFunctions",
                    version=VEFAAS_VERSION,
                    body={"PageSize": 100, "PageNumber": 1})
    for it in (r.get("Result") or {}).get("Items") or []:
        if it.get("Name") == name:
            return str(it.get("Id"))
    raise SystemExit(f"function name '{name}' not found")


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--function-id")
    g.add_argument("--function-name")
    p.add_argument("--description", default=None,
                   help="Release description (default: timestamped)")
    p.add_argument("--target-weight", type=int, default=100,
                   help="Traffic weight 0-100 (default: 100)")
    p.add_argument("--region", default="cn-beijing")
    args = p.parse_args()

    ak = _good("VOLC_ACCESS_KEY")
    sk = _good("VOLC_SECRET_KEY")
    if not ak or not sk or _is_placeholder(ak) or _is_placeholder(sk):
        raise SystemExit("VOLC_ACCESS_KEY / VOLC_SECRET_KEY missing. "
                         "Run scripts/sync_keys_to_windows.ps1 first.")

    client = VeApiClient(access_key=ak, secret_key=sk, region=args.region)
    fid = args.function_id or _find_fid_by_name(client, args.function_name)

    desc = args.description or (
        "manual release at "
        + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    )
    body = {
        "FunctionId":          fid,
        "RevisionNumber":      0,
        "Description":         desc,
        "TargetTrafficWeight": args.target_weight,
    }
    r = client.call(service=VEFAAS_SERVICE, action="Release",
                    version=VEFAAS_VERSION, body=body)
    res = r.get("Result") or {}
    print(json.dumps({
        "fid":             fid,
        "release_id":      res.get("ReleaseRecordId"),
        "new_revision":    res.get("NewRevisionNumber"),
        "old_revision":    res.get("OldRevisionNumber"),
        "stable_revision": res.get("StableRevisionNumber"),
        "status":          res.get("Status"),
        "status_message":  res.get("StatusMessage"),
    }, indent=2, ensure_ascii=False))
    return 0 if res.get("Status") in ("inprogress", "done") else 1


if __name__ == "__main__":
    raise SystemExit(main())
