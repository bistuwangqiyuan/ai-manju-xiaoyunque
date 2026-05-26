"""轮询 veFaaS 函数状态 + 拉取 HTTP 入口 URL.

usage:
    python scripts/get_function_info.py [--name xyq-manju] [--wait 180]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
import winreg
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.common.volc_signer import sign_request  # noqa: E402


VEFAAS_HOST = "open.volcengineapi.com"
SERVICE = "vefaas"
VERSION = "2024-06-06"


def _from_registry(name: str) -> str:
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as k:
            val, _ = winreg.QueryValueEx(k, name)
            return str(val)
    except (OSError, FileNotFoundError):
        return ""


def _ak_sk() -> tuple[str, str, str]:
    ak = (os.environ.get("VOLC_ACCESS_KEY") or os.environ.get("VOLCENGINE_ACCESS_KEY") or "").strip()
    sk = (os.environ.get("VOLC_SECRET_KEY") or os.environ.get("VOLCENGINE_SECRET_KEY") or "").strip()
    if not ak or ak.startswith("<") or ak.endswith(">"):
        ak = _from_registry("VOLC_ACCESS_KEY") or _from_registry("VOLCENGINE_ACCESS_KEY")
    if not sk or sk.startswith("<") or sk.endswith(">"):
        sk = _from_registry("VOLC_SECRET_KEY") or _from_registry("VOLCENGINE_SECRET_KEY")
    region = os.environ.get("VOLC_REGION") or "cn-beijing"
    if not ak or not sk:
        raise SystemExit("VOLC_ACCESS_KEY / VOLC_SECRET_KEY missing (env+registry both empty)")
    return ak, sk, region


def _call(action: str, body: dict) -> dict:
    ak, sk, region = _ak_sk()
    body_json = json.dumps(body, separators=(",", ":"))
    signed = sign_request(
        access_key=ak,
        secret_key=sk,
        action=action,
        version=VERSION,
        body=body_json.encode("utf-8"),
        method="POST",
        region=region,
        service=SERVICE,
        host=VEFAAS_HOST,
    )
    req = urllib.request.Request(signed.url, data=signed.body, method=signed.method)
    for k, v in signed.headers.items():
        req.add_header(k, v)
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body_txt = e.read().decode("utf-8", errors="replace")
        raise SystemExit(f"HTTP {e.code} on {action}: {body_txt}")


def list_functions() -> list[dict]:
    resp = _call("ListFunctions", {"PageSize": 100, "PageNumber": 1})
    r = resp.get("Result", {})
    return r.get("Items") or r.get("List") or []


def get_function(fid: str) -> dict:
    return _call("GetFunction", {"Id": fid}).get("Result", {})


def list_releases(fid: str) -> list[dict]:
    try:
        resp = _call("ListReleaseRecords", {"FunctionId": fid, "PageSize": 20, "PageNumber": 1})
    except SystemExit:
        return []
    r = resp.get("Result", {})
    return r.get("Items") or r.get("List") or []


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--name", default="xyq-manju")
    p.add_argument("--wait", type=int, default=180, help="seconds to wait for release done")
    args = p.parse_args()

    items = list_functions()
    target = next((it for it in items if it.get("Name") == args.name), None)
    if not target:
        names = [it.get("Name") for it in items]
        raise SystemExit(f"function {args.name} not found; available: {names}")
    fid = target.get("Id") or target.get("FunctionId")
    print(f"[*] {args.name} -> id={fid}")
    print(f"    status={target.get('Status', '?')}")

    deadline = time.time() + args.wait
    last_status = None
    while time.time() < deadline:
        recs = list_releases(fid)
        if recs:
            latest = recs[0]
            status = latest.get("Status", "?")
            if status != last_status:
                print(f"[release] {status}  (rev={latest.get('RevisionNumber','?')}, "
                      f"weight={latest.get('TargetTrafficWeight','?')})")
                last_status = status
            if status in {"done", "Done", "success", "Succeed", "released"}:
                break
            if status in {"failed", "Failed", "error", "Error"}:
                print(f"[release] FAILED: {json.dumps(latest, ensure_ascii=False, indent=2)}")
                break
        else:
            # No release records endpoint available; just poll Function status
            detail = get_function(fid)
            status = detail.get("Status", "?")
            if status != last_status:
                print(f"[function] {status}")
                last_status = status
            if status in {"Active", "Running", "Done", "Succeed"}:
                break
        time.sleep(6)

    detail = get_function(fid)
    print("\n=== function detail ===")
    interesting = (
        "Id", "Name", "Status", "Source", "Port",
        "TestInvocationURL", "URL", "FaasUrl", "InvokeUrl",
        "TriggerURL", "TriggerURLs", "CustomDomain",
        "RouteDomain", "PublicDomain", "ReleaseStatus",
    )
    for k in interesting:
        if k in detail:
            print(f"  {k}: {detail[k]}")

    print("\n=== raw GetFunction (first 6000 chars) ===")
    txt = json.dumps(detail, ensure_ascii=False, indent=2)
    print(txt[:6000] + ("\n... truncated ..." if len(txt) > 6000 else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
