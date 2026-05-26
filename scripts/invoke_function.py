"""通过 veFaaS Invoke OpenAPI 直接同步调用函数, 无需公网域名.

doc: https://www.volcengine.com/docs/6662/1262134 (Invoke--函数服务)

usage:
    python scripts/invoke_function.py --name xyq-manju --path /healthz
    python scripts/invoke_function.py --name xyq-manju --path /api/health
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import sys
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
        raise SystemExit("VOLC_ACCESS_KEY / VOLC_SECRET_KEY missing")
    return ak, sk, region


def _call(action: str, body: dict) -> tuple[int, dict]:
    ak, sk, region = _ak_sk()
    body_json = json.dumps(body, separators=(",", ":"))
    signed = sign_request(
        access_key=ak, secret_key=sk, action=action, version=VERSION,
        body=body_json.encode("utf-8"), method="POST",
        region=region, service=SERVICE, host=VEFAAS_HOST,
    )
    req = urllib.request.Request(signed.url, data=signed.body, method=signed.method)
    for k, v in signed.headers.items():
        req.add_header(k, v)
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        txt = e.read().decode("utf-8", errors="replace")
        try:
            return e.code, json.loads(txt)
        except Exception:
            return e.code, {"raw": txt}


def find_fid(name: str) -> str:
    _, resp = _call("ListFunctions", {"PageSize": 100, "PageNumber": 1})
    items = resp.get("Result", {}).get("Items") or resp.get("Result", {}).get("List") or []
    for it in items:
        if it.get("Name") == name:
            fid = it.get("Id") or it.get("FunctionId")
            return str(fid)
    raise SystemExit(f"function {name} not found")


def invoke(fid: str, path: str, method: str = "GET", body: str = "") -> None:
    """通过 Invoke action 模拟一次 HTTP 请求."""
    # veFaaS Invoke 接受标准 event 或 HTTP-style payload
    event = {
        "version": "1.0",
        "httpMethod": method,
        "path": path,
        "headers": {"Host": "test.invoke", "Accept": "*/*"},
        "queryStringParameters": {},
        "body": body,
        "isBase64Encoded": False,
    }
    payload = {
        "FunctionId": fid,
        "InvocationType": "Sync",
        "LogType": "Tail",
        "Event": base64.b64encode(json.dumps(event).encode("utf-8")).decode("utf-8"),
    }
    code, resp = _call("Invoke", payload)
    print(f"--- HTTP {code} ---")
    if isinstance(resp, dict):
        result = resp.get("Result", resp)
        log_b64 = result.get("LogResult") or resp.get("LogResult", "")
        if log_b64:
            try:
                log_txt = base64.b64decode(log_b64).decode("utf-8", errors="replace")
                print("--- function log (tail) ---")
                print(log_txt[-2000:])
            except Exception:
                pass
        payload_b64 = result.get("Payload") or result.get("Body")
        if payload_b64:
            try:
                body = base64.b64decode(payload_b64).decode("utf-8", errors="replace")
                print("--- response body ---")
                print(body[:2000])
            except Exception:
                print(payload_b64[:2000])
        else:
            print(json.dumps(resp, ensure_ascii=False, indent=2)[:2000])


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--name", default="xyq-manju")
    p.add_argument("--path", default="/healthz")
    p.add_argument("--method", default="GET")
    p.add_argument("--body", default="")
    args = p.parse_args()

    fid = find_fid(args.name)
    print(f"[*] {args.name} -> {fid}")
    invoke(fid, args.path, args.method, args.body)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
