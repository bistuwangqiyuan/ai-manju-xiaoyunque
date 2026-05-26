"""绑定 veFaaS 函数到 API 网关, 拿到公网域名.

前置:
  你已经在 https://console.volcengine.com/veapig 里建好:
  - 1 个 API Gateway 实例 (GatewayId, 例如 cqj2km4f...)
  - 1 个 Service (ServiceId, 例如 sxxx)
  - 1 个 Upstream (UpstreamId, 例如 uxxx)

usage:
  python scripts/bind_apig_trigger.py \\
      --function-name xyq-manju \\
      --gateway-id   gw-xxx \\
      --service-id   svc-xxx \\
      --upstream-id  up-xxx \\
      --path         /

doc: https://www.volcengine.com/docs/6662/116904
"""
from __future__ import annotations

import argparse
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
VEFAAS_VERSION = "2024-06-06"


def _from_registry(name: str) -> str:
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as k:
            v, _ = winreg.QueryValueEx(k, name)
            return str(v)
    except (OSError, FileNotFoundError):
        return ""


def _ak_sk() -> tuple[str, str, str]:
    ak = (os.environ.get("VOLC_ACCESS_KEY") or os.environ.get("VOLCENGINE_ACCESS_KEY") or "").strip()
    sk = (os.environ.get("VOLC_SECRET_KEY") or os.environ.get("VOLCENGINE_SECRET_KEY") or "").strip()
    if not ak or ak.startswith("<"):
        ak = _from_registry("VOLC_ACCESS_KEY") or _from_registry("VOLCENGINE_ACCESS_KEY")
    if not sk or sk.startswith("<"):
        sk = _from_registry("VOLC_SECRET_KEY") or _from_registry("VOLCENGINE_SECRET_KEY")
    region = os.environ.get("VOLC_REGION") or "cn-beijing"
    if not ak or not sk:
        raise SystemExit("VOLC_ACCESS_KEY / VOLC_SECRET_KEY missing")
    return ak, sk, region


def _call(service: str, action: str, version: str, body: dict) -> tuple[int, dict]:
    ak, sk, region = _ak_sk()
    body_json = json.dumps(body, separators=(",", ":"))
    signed = sign_request(
        access_key=ak, secret_key=sk, action=action, version=version,
        body=body_json.encode("utf-8"), method="POST",
        region=region, service=service, host=VEFAAS_HOST,
    )
    req = urllib.request.Request(signed.url, data=signed.body, method=signed.method)
    for k, v in signed.headers.items():
        req.add_header(k, v)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        txt = e.read().decode("utf-8", errors="replace")
        try:
            return e.code, json.loads(txt)
        except Exception:
            return e.code, {"raw": txt}


def find_fid(name: str) -> str:
    _, resp = _call("vefaas", "ListFunctions", VEFAAS_VERSION,
                    {"PageSize": 100, "PageNumber": 1})
    items = resp.get("Result", {}).get("Items") or []
    for it in items:
        if it.get("Name") == name:
            return str(it.get("Id"))
    raise SystemExit(f"function {name} not found")


def create_apig_trigger(fid: str, gateway_id: str, service_id: str,
                       upstream_id: str, path: str = "/") -> dict:
    body = {
        "FunctionId":   fid,
        "Name":         f"trig-{fid[:8]}",
        "GatewayId":    gateway_id,
        "ServiceId":    service_id,
        "UpstreamId":   upstream_id,
        "Path":         path,
        "MatchType":    "Prefix",
        "Methods":      ["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH", "HEAD"],
        "Enabled":      True,
        "Description":  "AI 漫剧 web service trigger (xyq-manju)",
    }
    code, resp = _call("vefaas", "CreateAPIGTrigger", VEFAAS_VERSION, body)
    print(f"--- CreateAPIGTrigger HTTP {code} ---")
    print(json.dumps(resp, ensure_ascii=False, indent=2))
    return resp


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--function-name", default="xyq-manju")
    p.add_argument("--gateway-id", required=True)
    p.add_argument("--service-id", required=True)
    p.add_argument("--upstream-id", required=True)
    p.add_argument("--path", default="/")
    args = p.parse_args()

    fid = find_fid(args.function_name)
    print(f"[*] function {args.function_name} -> {fid}")
    resp = create_apig_trigger(fid, args.gateway_id, args.service_id,
                                args.upstream_id, args.path)
    domain = (resp.get("Result") or {}).get("Domain") or \
             (resp.get("Result") or {}).get("PublicDomain")
    if domain:
        url = f"https://{domain}{args.path}"
        print(f"\n[*] PUBLIC URL: {url}")
        print(f"[*] HEALTH:     {url.rstrip('/')}/healthz")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
