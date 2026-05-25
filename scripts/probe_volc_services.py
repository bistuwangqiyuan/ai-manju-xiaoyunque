"""Probe Volcengine service authorization & resources — fully automated check.

跑这个脚本会自动尝试以下 4 件事 (用现有 AK/SK 即可):

  1. veFaaS 服务授权状态 (调用 ListFunctions, 看 401 / 403 / 200)
  2. API 网关 (apig) 服务授权状态 (调用 ListGateway)
  3. TOS bucket 是否存在 (HeadBucket); 若用户允许可自动 PutBucket
  4. Doubao TTS 数字 AppID (尝试调用 speech 控制台 OpenAPI 列出应用)

结果汇总到 ``data/volc_services_probe.json``, 同时打印「下一步建议」.

Usage::

    python scripts/probe_volc_services.py             # 只探测, 不修改
    python scripts/probe_volc_services.py --create-bucket   # 缺失时帮忙建 bucket
    python scripts/probe_volc_services.py --quiet     # 静默, 只写 JSON
"""
from __future__ import annotations

import argparse
import dataclasses
import datetime as _dt
import hashlib
import hmac
import json
import os
import pathlib
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

_REPO = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO))


# ---------------------------------------------------------------------------
# Env loader: prefer Windows User-level setx values, else process env, else .env
# ---------------------------------------------------------------------------

def _read_windows_user_env(name: str) -> str:
    if os.name != "nt":
        return ""
    try:
        import winreg  # type: ignore

        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as h:
            try:
                v, _ = winreg.QueryValueEx(h, name)
                return str(v or "").strip()
            except FileNotFoundError:
                return ""
    except Exception:
        return ""


def _load_envfile(p: pathlib.Path) -> None:
    if not p.exists():
        return
    for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        k = k.strip(); v = v.strip().strip('"').strip("'")
        if k and v and k not in os.environ:
            os.environ[k] = v


for p in (_REPO / ".env", _REPO / "backend" / ".env",
          _REPO / "deploy" / "cn-serverless" / ".env"):
    _load_envfile(p)

# Override with Windows user-level for the keys we care about
for key in (
    "VOLC_ACCESS_KEY", "VOLC_SECRET_KEY",
    "VOLC_ARK_API_KEY", "ARK_API_KEY",
    "DOUBAO_TTS_APPID", "DOUBAO_TTS_TOKEN",
    "TOS_BUCKET", "TOS_ENDPOINT", "TOS_REGION",
):
    v = _read_windows_user_env(key)
    if v and v not in ("", "<paste-rotated-AK>", "<paste-rotated-SK>"):
        os.environ[key] = v

VOLC_AK = (os.environ.get("VOLC_ACCESS_KEY") or os.environ.get("VOLC_AK") or "").strip()
VOLC_SK = (os.environ.get("VOLC_SECRET_KEY") or os.environ.get("VOLC_SK") or "").strip()
DEFAULT_REGION = (os.environ.get("VOLC_REGION") or "cn-beijing").strip()


# ---------------------------------------------------------------------------
# Volc OpenAPI V4 signer (inline, no project import)
# ---------------------------------------------------------------------------

def _sha256_hex(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _sign_v4(ak: str, sk: str, service: str, region: str, host: str,
             method: str, query: dict, body: bytes,
             content_type: str = "application/json; charset=utf-8") -> dict:
    now = _dt.datetime.now(_dt.timezone.utc)
    amzdate = now.strftime("%Y%m%dT%H%M%SZ")
    datestamp = now.strftime("%Y%m%d")
    body_hash = _sha256_hex(body)
    qs = "&".join(
        urllib.parse.quote(str(k), safe="-_.~") + "=" +
        urllib.parse.quote(str(v), safe="-_.~")
        for k, v in sorted(query.items())
    )
    canonical_headers = (
        f"content-type:{content_type}\nhost:{host}\n"
        f"x-content-sha256:{body_hash}\nx-date:{amzdate}\n"
    )
    signed_headers = "content-type;host;x-content-sha256;x-date"
    canonical_request = "\n".join([
        method.upper(), "/", qs, canonical_headers, signed_headers, body_hash,
    ])
    scope = f"{datestamp}/{region}/{service}/request"
    sts = "\n".join([
        "HMAC-SHA256", amzdate, scope,
        _sha256_hex(canonical_request.encode("utf-8")),
    ])

    def _h(key: bytes, msg: str) -> bytes:
        return hmac.new(key, msg.encode("utf-8"), hashlib.sha256).digest()

    k_date = _h(sk.encode("utf-8"), datestamp)
    k_region = _h(k_date, region)
    k_service = _h(k_region, service)
    k_sign = _h(k_service, "request")
    sig = hmac.new(k_sign, sts.encode("utf-8"), hashlib.sha256).hexdigest()
    return {
        "Host": host,
        "Content-Type": content_type,
        "X-Date": amzdate,
        "X-Content-Sha256": body_hash,
        "Authorization": (
            f"HMAC-SHA256 Credential={ak}/{scope}, "
            f"SignedHeaders={signed_headers}, Signature={sig}"
        ),
    }


def _call_openapi(*, service: str, action: str, version: str,
                  body: dict, region: str = DEFAULT_REGION,
                  host: str = "open.volcengineapi.com",
                  method: str = "POST",
                  timeout: float = 30.0) -> tuple[int, dict | str]:
    """Call Volc OpenAPI and return (http_status, parsed_json_or_raw_text)."""
    body_bytes = json.dumps(body, ensure_ascii=False).encode("utf-8")
    headers = _sign_v4(VOLC_AK, VOLC_SK, service, region, host,
                       method, {"Action": action, "Version": version}, body_bytes)
    url = f"https://{host}/?Action={action}&Version={version}"
    req = urllib.request.Request(url, data=body_bytes, headers=headers,
                                 method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
            status = resp.status
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", errors="replace")
    except Exception as e:
        return -1, f"{type(e).__name__}: {e}"
    try:
        return status, json.loads(raw)
    except Exception:
        return status, raw.decode("utf-8", errors="replace")


# ---------------------------------------------------------------------------
# Probes
# ---------------------------------------------------------------------------

@dataclasses.dataclass
class ProbeResult:
    name: str
    status: str           # "authorized" / "not_authorized" / "missing" / "exists" / "unknown" / "no_creds"
    detail: str = ""
    extra: dict = dataclasses.field(default_factory=dict)
    next_action: str = ""


def probe_vefaas() -> ProbeResult:
    if not VOLC_AK or not VOLC_SK:
        return ProbeResult("veFaaS", "no_creds",
                           detail="VOLC_ACCESS_KEY/SECRET_KEY missing",
                           next_action=("先跑 .\\scripts\\sync_keys_to_windows.ps1 "
                                       "把 AK/SK 写入 Windows 用户级 env"))
    status, body = _call_openapi(
        service="vefaas", action="ListFunctions", version="2024-06-06",
        body={"PageSize": 1}, region=DEFAULT_REGION,
    )
    if status == 200 and isinstance(body, dict):
        items = (body.get("Result") or {}).get("Items") or []
        return ProbeResult(
            "veFaaS", "authorized",
            detail=f"已授权; 当前 {len(items)} 个函数",
            extra={"function_count": len(items)},
            next_action="可以直接跑 .\\deploy\\cn-volc-vefaas\\deploy.ps1",
        )
    text = body if isinstance(body, str) else json.dumps(body, ensure_ascii=False)
    if "NotAuthorized" in text or "Forbidden" in text or status in (401, 403):
        return ProbeResult(
            "veFaaS", "not_authorized",
            detail=f"http {status}: {text[:200]}",
            next_action=("浏览器开 https://console.volcengine.com/vefaas "
                         "点「立即授权」 (一次性, ~30 秒)"),
        )
    return ProbeResult("veFaaS", "unknown",
                       detail=f"http {status}: {text[:200]}")


def probe_apig() -> ProbeResult:
    if not VOLC_AK or not VOLC_SK:
        return ProbeResult("API 网关 (apig)", "no_creds",
                           next_action="先同步 AK/SK")
    # APIG OpenAPI version is 2022-11-12
    status, body = _call_openapi(
        service="apig", action="ListGateways", version="2022-11-12",
        body={"PageSize": 1, "PageNumber": 1}, region=DEFAULT_REGION,
    )
    if status == 200 and isinstance(body, dict):
        items = (body.get("Result") or {}).get("Items") or []
        return ProbeResult(
            "API 网关 (apig)", "authorized",
            detail=f"已授权; 当前 {len(items)} 个 gateway",
            extra={"gateway_count": len(items)},
            next_action="若 0 个 gateway, 控制台或 deploy.ps1 会建一个",
        )
    text = body if isinstance(body, str) else json.dumps(body, ensure_ascii=False)
    if "NotAuthorized" in text or "Forbidden" in text or status in (401, 403):
        return ProbeResult(
            "API 网关 (apig)", "not_authorized",
            detail=f"http {status}: {text[:200]}",
            next_action=("浏览器开 https://console.volcengine.com/veapig "
                         "点「立即授权」"),
        )
    return ProbeResult("API 网关 (apig)", "unknown",
                       detail=f"http {status}: {text[:200]}")


def probe_tos_bucket(*, create_if_missing: bool = False) -> ProbeResult:
    if not VOLC_AK or not VOLC_SK:
        return ProbeResult("TOS bucket", "no_creds")
    bucket = (os.environ.get("TOS_BUCKET") or "").strip() or "xyq-prod-cn-beijing"
    region = (os.environ.get("TOS_REGION") or DEFAULT_REGION).strip()
    endpoint_host = f"tos-{region}.volces.com"
    bucket_host = f"{bucket}.{endpoint_host}"

    # HEAD bucket via S3-compatible (signed via S3 v4)
    try:
        try:
            import boto3
            from botocore.config import Config as BotoConfig
            from botocore.exceptions import ClientError
        except ImportError:
            return ProbeResult(
                "TOS bucket", "unknown",
                detail="boto3 not installed; pip install boto3",
                next_action="pip install boto3",
            )
        client = boto3.client(
            "s3",
            endpoint_url=f"https://{endpoint_host}",
            region_name=region,
            aws_access_key_id=VOLC_AK,
            aws_secret_access_key=VOLC_SK,
            config=BotoConfig(
                s3={"addressing_style": "virtual"},
                signature_version="s3v4",
                retries={"max_attempts": 2, "mode": "standard"},
            ),
        )
        try:
            client.head_bucket(Bucket=bucket)
            return ProbeResult(
                "TOS bucket", "exists",
                detail=f"bucket={bucket} region={region} 可用",
                extra={"bucket": bucket, "region": region,
                       "endpoint": f"https://{bucket_host}"},
                next_action=f"已在 .env 设置 TOS_BUCKET={bucket}",
            )
        except ClientError as e:
            code = e.response["Error"].get("Code", "")
            if code in ("404", "NoSuchBucket", "NotFound"):
                if create_if_missing:
                    # TOS bucket 的 region 由 endpoint 决定, 不传 LocationConstraint;
                    # 第一次失败再尝试带 LocationConstraint (S3 兼容路径)
                    last_err = None
                    for attempt_kwargs in (
                        {"Bucket": bucket},
                        {"Bucket": bucket,
                         "CreateBucketConfiguration": {"LocationConstraint": region}},
                    ):
                        try:
                            client.create_bucket(**attempt_kwargs)
                            return ProbeResult(
                                "TOS bucket", "exists",
                                detail=f"bucket={bucket} 已自动创建 (region={region})",
                                extra={"bucket": bucket, "region": region,
                                       "created": True},
                            )
                        except ClientError as ce:
                            last_err = ce
                            continue
                        except Exception as ce:
                            last_err = ce
                            break
                    return ProbeResult(
                        "TOS bucket", "missing",
                        detail=f"create failed: {last_err}",
                        next_action=(
                            f"控制台手动建: https://console.volcengine.com/tos "
                            f"-> 创建桶 -> 名字 {bucket} -> 地域 {region} -> 私有"
                        ),
                    )
                return ProbeResult(
                    "TOS bucket", "missing",
                    detail=f"bucket={bucket} 不存在",
                    extra={"bucket": bucket, "region": region},
                    next_action=("跑 python scripts/probe_volc_services.py "
                                 "--create-bucket 自动建; 或控制台手动建"),
                )
            return ProbeResult("TOS bucket", "unknown", detail=str(e))
    except Exception as e:
        return ProbeResult("TOS bucket", "unknown", detail=f"{type(e).__name__}: {e}")


def probe_doubao_tts_appid() -> ProbeResult:
    """尝试从 openspeech 控制台 OpenAPI 列出 ICL 应用拿 AppID."""
    if not VOLC_AK or not VOLC_SK:
        return ProbeResult("Doubao TTS AppID", "no_creds")
    current = (os.environ.get("DOUBAO_TTS_APPID") or "").strip()
    if current.isdigit() and len(current) >= 10:
        return ProbeResult(
            "Doubao TTS AppID", "exists",
            detail=f"已是数字 ID: {current}",
            extra={"appid": current},
        )
    # Try OpenAPI: speech service has ListAppIDs / GetAppList (subject to permission).
    # Use the documented "speech_saas_inner" service host.  这里只能尽力一试.
    for service, action, version, host in [
        ("speech_saas_inner", "ListSpeechApps", "2023-11-07", "open.volcengineapi.com"),
        ("speech_saas_inner", "GetUserApps", "2023-11-07", "open.volcengineapi.com"),
        ("speech_saas_inner", "ListAppsByService", "2023-11-07", "open.volcengineapi.com"),
    ]:
        status, body = _call_openapi(
            service=service, action=action, version=version,
            body={"Service": "tts_icl", "PageSize": 20},
            host=host,
        )
        if status == 200 and isinstance(body, dict):
            items = body.get("Result", {}).get("Apps") or []
            if items:
                # pick first numeric AppID
                ids = [str(a.get("AppID") or a.get("AppId") or "")
                       for a in items if str(a.get("AppID") or a.get("AppId") or "").isdigit()]
                if ids:
                    return ProbeResult(
                        "Doubao TTS AppID", "exists",
                        detail=f"OpenAPI 探测到 {len(ids)} 个 ICL AppID, 首个 = {ids[0]}",
                        extra={"all_appids": ids, "picked": ids[0]},
                        next_action=("脚本会建议把 DOUBAO_TTS_APPID 改成此 ID; "
                                     "或人工去控制台核对"),
                    )
    return ProbeResult(
        "Doubao TTS AppID", "missing",
        detail=("当前值 ='" + (current or "未设置") + "', 不是 11 位数字 ID; "
                "OpenAPI ListSpeechApps 也未返回可用 AppID"),
        next_action=("浏览器开 https://console.volcengine.com/speech/service/8 "
                     "复制「语音合成大模型 ICL」应用的 11 位数字 AppID 给我"),
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="probe_volc_services")
    parser.add_argument("--create-bucket", action="store_true",
                        help="if TOS bucket missing, try to create it")
    parser.add_argument("--quiet", action="store_true",
                        help="suppress stdout (only write JSON)")
    parser.add_argument("--output", default="data/volc_services_probe.json")
    args = parser.parse_args(argv)

    if not args.quiet:
        print(f"{'='*72}")
        print(f" 火山引擎服务自动探测  ({_dt.datetime.now().isoformat(timespec='seconds')})")
        print(f"{'='*72}")
        print(f"  AK={VOLC_AK[:8]}***  region={DEFAULT_REGION}")
        print(f"  bucket={(os.environ.get('TOS_BUCKET') or 'xyq-prod-cn-beijing')}")
        print()

    results = [
        probe_vefaas(),
        probe_apig(),
        probe_tos_bucket(create_if_missing=args.create_bucket),
        probe_doubao_tts_appid(),
    ]
    if not args.quiet:
        for r in results:
            badge = {
                "authorized": "[OK ]", "exists": "[OK ]",
                "not_authorized": "[NEED]", "missing": "[NEED]",
                "no_creds": "[FAIL]", "unknown": "[??? ]",
            }.get(r.status, "[??? ]")
            print(f"{badge} {r.name}: {r.status}")
            if r.detail:
                print(f"        detail: {r.detail}")
            if r.next_action:
                print(f"        ->      {r.next_action}")
            print()

    out = _REPO / args.output
    out.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "timestamp": _dt.datetime.now(_dt.timezone.utc).isoformat(),
        "ak_prefix": VOLC_AK[:8],
        "region": DEFAULT_REGION,
        "results": [dataclasses.asdict(r) for r in results],
        "summary": {
            "ok":     sum(1 for r in results if r.status in {"authorized", "exists"}),
            "need":   sum(1 for r in results if r.status in {"not_authorized", "missing"}),
            "failed": sum(1 for r in results if r.status in {"no_creds", "unknown"}),
        },
    }
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    if not args.quiet:
        print(f"  wrote: {out}")
    # exit 0 only if all are OK
    return 0 if payload["summary"]["need"] == 0 and payload["summary"]["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
