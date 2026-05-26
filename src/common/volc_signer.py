"""火山引擎 Volcengine Visual API V4 HMAC-SHA256 签名实现.

锁定证据：基于 GitLab self-media-james/即梦.md (2026-03-12 更新) 的实测可跑通版本，
所有签名字段、规范化请求、credential_scope 公式均已实测验证。
"""
from __future__ import annotations

import datetime as _dt
import hashlib
import hmac
from dataclasses import dataclass
from typing import Mapping
from urllib.parse import quote


_REGION = "cn-north-1"
_SERVICE = "cv"
_HOST = "visual.volcengineapi.com"
_ALGORITHM = "HMAC-SHA256"


def _sign(key: bytes, msg: str) -> bytes:
    return hmac.new(key, msg.encode("utf-8"), hashlib.sha256).digest()


def _derive_signing_key(secret_key: str, datestamp: str, region: str, service: str) -> bytes:
    k_date = _sign(secret_key.encode("utf-8"), datestamp)
    k_region = _sign(k_date, region)
    k_service = _sign(k_region, service)
    return _sign(k_service, "request")


def _canonical_query_string(params: Mapping[str, str]) -> str:
    if not params:
        return ""
    pairs = sorted(params.items())
    return "&".join(
        f"{quote(str(k), safe='-_.~')}={quote(str(v), safe='-_.~')}" for k, v in pairs
    )


@dataclass(frozen=True)
class SignedRequest:
    method: str
    url: str
    headers: dict
    body: bytes


def sign_request(
    *,
    access_key: str,
    secret_key: str,
    action: str,
    version: str,
    body: bytes,
    method: str = "POST",
    region: str = _REGION,
    service: str = _SERVICE,
    host: str = _HOST,
    extra_query: Mapping[str, str] | None = None,
) -> SignedRequest:
    """Sign a Volcengine OpenAPI request with V4 HMAC-SHA256."""

    now = _dt.datetime.now(_dt.timezone.utc)
    amzdate = now.strftime("%Y%m%dT%H%M%SZ")
    datestamp = now.strftime("%Y%m%d")

    query = {"Action": action, "Version": version}
    if extra_query:
        query.update({k: v for k, v in extra_query.items() if v is not None})
    canonical_qs = _canonical_query_string(query)

    payload_hash = hashlib.sha256(body or b"").hexdigest()

    # NOTE: Volc vefaas / apig OpenAPI reject signatures whose canonical
    # content-type omits the charset segment (returns
    # InvalidAuthorization 100024). Keep `application/json; charset=utf-8`
    # to stay compatible with both visual.volcengineapi.com and
    # open.volcengineapi.com.
    canonical_headers = (
        "content-type:application/json; charset=utf-8\n"
        f"host:{host}\n"
        f"x-content-sha256:{payload_hash}\n"
        f"x-date:{amzdate}\n"
    )
    signed_headers = "content-type;host;x-content-sha256;x-date"

    canonical_request = "\n".join([
        method.upper(),
        "/",
        canonical_qs,
        canonical_headers,
        signed_headers,
        payload_hash,
    ])

    credential_scope = f"{datestamp}/{region}/{service}/request"
    string_to_sign = "\n".join([
        _ALGORITHM,
        amzdate,
        credential_scope,
        hashlib.sha256(canonical_request.encode("utf-8")).hexdigest(),
    ])

    signing_key = _derive_signing_key(secret_key, datestamp, region, service)
    signature = hmac.new(signing_key, string_to_sign.encode("utf-8"), hashlib.sha256).hexdigest()

    authorization = (
        f"{_ALGORITHM} "
        f"Credential={access_key}/{credential_scope}, "
        f"SignedHeaders={signed_headers}, "
        f"Signature={signature}"
    )

    return SignedRequest(
        method=method.upper(),
        url=f"https://{host}/?{canonical_qs}",
        headers={
            # MUST match canonical_headers exactly (incl. ; charset=utf-8)
            "Content-Type": "application/json; charset=utf-8",
            "Host": host,
            "X-Date": amzdate,
            "X-Content-Sha256": payload_hash,
            "Authorization": authorization,
        },
        body=body,
    )
