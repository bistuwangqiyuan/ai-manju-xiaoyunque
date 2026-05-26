"""End-to-end APIG binding for an existing veFaaS function.

Given:
  - an existing API Gateway instance (Running)
  - an existing veFaaS function (Running)

This script creates (idempotently) on the gateway:
  1. A public-facing HTTP Service
  2. An Upstream of type VeFaas pointing to the function
  3. A Route catching all paths on the Service routing to the Upstream

Then it reads the Service's public domain back and prints the live URL.

Usage:
    python scripts/setup_apig_full.py \\
        --gateway-id  gd8afjpepm94qqo1kmttg \\
        --function-id 0mt4ej8a \\
        --service-name xyq-manju-svc \\
        --upstream-name xyq-manju-up \\
        --route-name xyq-manju-all

API references:
  - https://www.volcengine.com/docs/6569/195265  (apig 2021-03-03)
  - https://www.volcengine.com/docs/6569/1255159 (apig 2022-11-12 routes)
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


APIG_HOST            = "open.volcengineapi.com"
APIG_SERVICE         = "apig"
APIG_REGION          = "cn-beijing"
APIG_VERSION_GW      = "2021-03-03"
APIG_VERSION_ROUTE   = "2022-11-12"


_PLACEHOLDER_MARKERS = (
    "<paste", "your-", "your_", "xxxx", "todo", "<set",
    "changeme", "replace-me", "your-key-here",
)


def _is_placeholder(v: str) -> bool:
    if not v:
        return True
    lo = v.strip().lower()
    return lo.startswith("<") or any(m in lo for m in _PLACEHOLDER_MARKERS)


def _from_registry(name: str) -> str:
    """Windows-only: read user-level env var directly from HKCU\\Environment.

    Necessary because PowerShell sessions may have stale env values from a
    project .env that contain placeholder strings; the global Windows env
    set by ``scripts/sync_keys_to_windows.ps1`` is the canonical source.
    """
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as k:
            v, _ = winreg.QueryValueEx(k, name)
            return str(v)
    except (OSError, FileNotFoundError):
        return ""


def _ak_sk() -> tuple[str, str]:
    ak = (os.environ.get("VOLC_ACCESS_KEY") or
          os.environ.get("VOLCENGINE_ACCESS_KEY") or "").strip()
    sk = (os.environ.get("VOLC_SECRET_KEY") or
          os.environ.get("VOLCENGINE_SECRET_KEY") or "").strip()
    if _is_placeholder(ak):
        ak = (_from_registry("VOLC_ACCESS_KEY")
              or _from_registry("VOLCENGINE_ACCESS_KEY") or "").strip()
    if _is_placeholder(sk):
        sk = (_from_registry("VOLC_SECRET_KEY")
              or _from_registry("VOLCENGINE_SECRET_KEY") or "").strip()
    if not ak or not sk or _is_placeholder(ak) or _is_placeholder(sk):
        raise SystemExit("VOLC_ACCESS_KEY / VOLC_SECRET_KEY missing (or placeholder). "
                         "Run scripts/sync_keys_to_windows.ps1 first.")
    return ak, sk


def _call(action: str, version: str, body: dict) -> tuple[int, dict]:
    ak, sk = _ak_sk()
    body_json = json.dumps(body, separators=(",", ":"), ensure_ascii=False)
    signed = sign_request(
        access_key=ak, secret_key=sk, action=action, version=version,
        body=body_json.encode("utf-8"), method="POST",
        region=APIG_REGION, service=APIG_SERVICE, host=APIG_HOST,
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


def _result(resp: dict) -> dict:
    return resp.get("Result") or {}


def _err(resp: dict) -> str:
    meta = resp.get("ResponseMetadata") or {}
    err = meta.get("Error") or {}
    return f"{err.get('CodeN', '')} {err.get('Code', '')} {err.get('Message', '')}".strip()


# ---------------------------------------------------------------------------
# Idempotent ensure helpers
# ---------------------------------------------------------------------------

def find_or_create_service(gateway_id: str, name: str) -> str:
    code, resp = _call("ListGatewayServices", APIG_VERSION_GW,
                       {"GatewayId": gateway_id})
    for it in _result(resp).get("Items") or []:
        if it.get("Name") == name or it.get("ServiceName") == name:
            sid = it.get("Id")
            print(f"[=] service '{name}' exists: {sid}")
            return str(sid)

    body = {
        "GatewayId":   gateway_id,
        "ServiceName": name,
        "Comments":    "xyq manju agent (v9.1 auto)",
        "Protocol":    ["HTTP", "HTTPS"],
        "ServiceNetworkSpec": {
            "EnablePublicNetwork":  True,
            "EnablePrivateNetwork": False,
        },
        "AuthSpec":    {"Enable": False},
    }
    code, resp = _call("CreateGatewayService", APIG_VERSION_GW, body)
    sid = _result(resp).get("Id")
    if not sid:
        raise SystemExit(f"CreateGatewayService failed [HTTP {code}]: {_err(resp) or resp}")
    print(f"[+] service '{name}' created: {sid}")
    return str(sid)


def find_or_create_upstream(gateway_id: str, name: str, function_id: str) -> str:
    code, resp = _call("ListUpstreams", APIG_VERSION_GW,
                       {"GatewayId": gateway_id})
    for it in _result(resp).get("Items") or []:
        if it.get("Name") == name:
            uid = it.get("Id")
            print(f"[=] upstream '{name}' exists: {uid}")
            return str(uid)

    body = {
        "GatewayId":   gateway_id,
        "Name":        name,
        "Comments":    f"xyq-manju veFaaS function {function_id}",
        "Protocol":    "HTTP",
        "SourceType":  "VeFaas",
        "UpstreamSpec": {
            "VeFaas": {"FunctionId": function_id},
        },
    }
    code, resp = _call("CreateUpstream", APIG_VERSION_GW, body)
    uid = _result(resp).get("Id")
    if not uid:
        raise SystemExit(f"CreateUpstream failed [HTTP {code}]: {_err(resp) or resp}")
    print(f"[+] upstream '{name}' created: {uid}")

    # Bootstrap an UpstreamVersion 'v1' so the route can reference a stable
    # label. VeFaas-typed upstreams auto-track the function's released
    # revision; the version label is only a routing alias.
    code, resp = _call("CreateUpstreamVersion", APIG_VERSION_GW, {
        "UpstreamId": uid,
        "UpstreamVersion": {"Name": "v1", "Labels": []},
    })
    if code == 200:
        print(f"[+] upstream version 'v1' bootstrapped")
    else:
        # Tolerate 'already exists' (will happen on idempotent re-runs)
        print(f"[=] upstream version 'v1' bootstrap: HTTP {code}")
    return str(uid)


def find_or_create_route(service_id: str, route_name: str, upstream_id: str,
                          path: str = "/") -> str:
    code, resp = _call("ListRoutes", APIG_VERSION_ROUTE,
                       {"ServiceId": service_id})
    for it in _result(resp).get("Items") or []:
        if it.get("Name") == route_name:
            rid = it.get("Id")
            print(f"[=] route '{route_name}' exists: {rid}")
            return str(rid)

    body = {
        "ServiceId":  service_id,
        "Name":       route_name,
        "Priority":   1,
        "Enable":     True,
        "MatchRule": {
            "Path":   {"MatchType": "Prefix", "MatchContent": path},
            "Method": ["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH", "HEAD"],
        },
        "UpstreamList": [{"UpstreamId": upstream_id, "Version": "v1",
                          "Weight": 100}],
        "AdvancedSetting": {
            "TimeoutSetting": {"Enable": True, "Timeout": 120},
        },
    }
    code, resp = _call("CreateRoute", APIG_VERSION_ROUTE, body)
    rid = _result(resp).get("Id")
    if not rid:
        raise SystemExit(f"CreateRoute failed [HTTP {code}]: {_err(resp) or resp}")
    print(f"[+] route '{route_name}' created: {rid}")
    return str(rid)


def get_service_url(service_id: str) -> str:
    """Read public URL from the service Domains list.

    Volc returns each Domain field already prefixed with scheme:
        {"Domain": "http://sxxx.apigateway-cn-beijing.volceapi.com", "Type": "public"}
    Prefer https; fall back to http.
    """
    code, resp = _call("GetGatewayService", APIG_VERSION_GW, {"Id": service_id})
    res = _result(resp)
    domains = res.get("Domains") or res.get("ServiceDomains") or []
    https_url = ""
    http_url = ""
    for d in domains:
        if not isinstance(d, dict):
            continue
        dom = d.get("Domain") or d.get("Name") or ""
        if not dom:
            continue
        # auto-add scheme if missing
        url = dom if dom.startswith("http") else f"http://{dom}"
        if url.startswith("https://"):
            https_url = url
        else:
            http_url = url
    return https_url or http_url


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--gateway-id",     required=True)
    p.add_argument("--function-id",    required=True)
    p.add_argument("--service-name",   default="xyq-manju-svc")
    p.add_argument("--upstream-name",  default="xyq-manju-up")
    p.add_argument("--route-name",     default="xyq-manju-all")
    p.add_argument("--path",           default="/")
    args = p.parse_args()

    sid = find_or_create_service(args.gateway_id, args.service_name)
    uid = find_or_create_upstream(args.gateway_id, args.upstream_name,
                                   args.function_id)
    rid = find_or_create_route(sid, args.route_name, uid, args.path)

    # Service URL may take a few seconds to propagate after Service creation
    url = ""
    for attempt in range(6):
        url = get_service_url(sid)
        if url:
            break
        time.sleep(5)

    print()
    print("=" * 60)
    print(f" service_id  = {sid}")
    print(f" upstream_id = {uid}")
    print(f" route_id    = {rid}")
    if url:
        print(f" PUBLIC URL  = {url}")
        print(f" HEALTH      = {url.rstrip('/')}/healthz")
    else:
        print(" PUBLIC URL  = (pending; check console at https://console.volcengine.com/veapig)")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
