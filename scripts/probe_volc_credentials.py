"""Probe Volcengine CV credentials.

试 3 个候选 SK（原值、base64 解码值），向 visual.volcengineapi.com 提交一个
最小 Manju script_analysis 任务（用假 file_url, 故意触发 400/参数错误）。

我们要的是：服务端给出"参数错误"而不是"401/Authentication/SignatureDoesNotMatch"，
代表签名正确且账号有权访问 cv 服务。
"""
from __future__ import annotations

import base64
import datetime as dt
import hashlib
import hmac
import json
import sys
import urllib.error
import urllib.request


HOST = "visual.volcengineapi.com"
REGION = "cn-north-1"
SERVICE = "cv"
ALGO = "HMAC-SHA256"


def _sign(key: bytes, msg: str) -> bytes:
    return hmac.new(key, msg.encode("utf-8"), hashlib.sha256).digest()


def _derive_signing_key(sk: str, datestamp: str) -> bytes:
    k_date = _sign(sk.encode("utf-8"), datestamp)
    k_region = _sign(k_date, REGION)
    k_service = _sign(k_region, SERVICE)
    return _sign(k_service, "request")


def call(ak: str, sk: str, action: str, payload: dict) -> tuple[int, dict]:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    now = dt.datetime.now(dt.timezone.utc)
    amzdate = now.strftime("%Y%m%dT%H%M%SZ")
    datestamp = now.strftime("%Y%m%d")
    canonical_qs = f"Action={action}&Version=2022-08-31"
    payload_hash = hashlib.sha256(body).hexdigest()
    canonical_headers = (
        "content-type:application/json; charset=utf-8\n"
        f"host:{HOST}\n"
        f"x-content-sha256:{payload_hash}\n"
        f"x-date:{amzdate}\n"
    )
    signed_headers = "content-type;host;x-content-sha256;x-date"
    canonical_request = "\n".join([
        "POST", "/", canonical_qs, canonical_headers, signed_headers, payload_hash
    ])
    credential_scope = f"{datestamp}/{REGION}/{SERVICE}/request"
    sts = "\n".join([
        ALGO, amzdate, credential_scope,
        hashlib.sha256(canonical_request.encode()).hexdigest(),
    ])
    signing_key = _derive_signing_key(sk, datestamp)
    signature = hmac.new(signing_key, sts.encode(), hashlib.sha256).hexdigest()
    authorization = (
        f"{ALGO} Credential={ak}/{credential_scope}, "
        f"SignedHeaders={signed_headers}, Signature={signature}"
    )
    url = f"https://{HOST}/?{canonical_qs}"
    req = urllib.request.Request(
        url,
        data=body,
        headers={
            "Content-Type": "application/json; charset=utf-8",
            "Host": HOST,
            "X-Date": amzdate,
            "X-Content-Sha256": payload_hash,
            "Authorization": authorization,
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", errors="replace")
        try:
            return e.code, json.loads(raw)
        except json.JSONDecodeError:
            return e.code, {"raw": raw}


def main() -> int:
    ak = sys.argv[1] if len(sys.argv) > 1 else ""
    sk_input = sys.argv[2] if len(sys.argv) > 2 else ""
    if not ak or not sk_input:
        print("usage: probe_volc_credentials.py AK SK")
        return 2

    candidates = [("raw", sk_input)]
    try:
        pad = (-len(sk_input)) % 4
        decoded = base64.b64decode(sk_input + "=" * pad, validate=False).decode("utf-8").strip()
        if decoded and decoded != sk_input:
            candidates.append(("base64-decoded", decoded))
    except Exception as e:  # noqa: BLE001
        print(f"(base64 decode failed: {e})")

    # 1) 用一个无意义 task_id 调 query 接口，期望返回 not_found / param error (=签名 OK)
    print("\n[1] CVSync2AsyncGetResult — minimal probe")
    for label, sk in candidates:
        status, body = call(ak, sk, "CVSync2AsyncGetResult", {
            "req_key": "pippit_shortplay_cvtob_script_analysis",
            "task_id": "probe-0000",
        })
        code = body.get("code") if isinstance(body, dict) else None
        msg = body.get("message") if isinstance(body, dict) else ""
        print(f"  sk={label:18s} http={status} code={code} msg={msg!r}")

    # 2) 用一个不可访问的 file_url 调 submit
    print("\n[2] CVSync2AsyncSubmitTask script_analysis — minimal probe")
    for label, sk in candidates:
        status, body = call(ak, sk, "CVSync2AsyncSubmitTask", {
            "req_key": "pippit_shortplay_cvtob_script_analysis",
            "visual_style": "2D, 国风, 平涂",
            "video_ratio": "9:16",
            "file_url": "https://example.com/probe.txt",
            "file_type": "txt",
            "file_name": "probe.txt",
        })
        code = body.get("code") if isinstance(body, dict) else None
        msg = body.get("message") if isinstance(body, dict) else ""
        print(f"  sk={label:18s} http={status} code={code} msg={msg!r}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
