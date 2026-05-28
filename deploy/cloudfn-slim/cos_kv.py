"""Tencent COS V5 minimal client (zero-dep, stdlib only).

支持：
  - put_json / get_json：跨 SCF 实例的 KV 状态存储（任务 4 阶段状态机）
  - put_text_public：把剧本 .txt 放到公网可读地址（供火山 Manju Agent file_url）
  - list_keys_under：列出某前缀下的所有 object key（用于列任务）
  - delete_key：删除单 object（任务取消时清理）

凭证来源（优先级从高到低）：
  1. 函数参数 secret_id/secret_key/security_token
  2. 环境变量 COS_SECRET_ID / COS_SECRET_KEY / COS_SESSION_TOKEN
  3. SCF 自动注入 TENCENTCLOUD_SECRETID / TENCENTCLOUD_SECRETKEY / TENCENTCLOUD_SESSIONTOKEN

环境变量：
  COS_BUCKET  必填，例如 6375-cursoraicode-5g67ezfl8a1891da-1300352403
  COS_REGION  必填，例如 ap-shanghai
"""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any
from xml.etree import ElementTree as ET

_log = logging.getLogger(__name__)


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default) or default


def _credentials(secret_id: str | None, secret_key: str | None,
                 security_token: str | None) -> tuple[str, str, str]:
    sid = (secret_id or _env("COS_SECRET_ID") or _env("TENCENTCLOUD_SECRETID")).strip()
    skey = (secret_key or _env("COS_SECRET_KEY") or _env("TENCENTCLOUD_SECRETKEY")).strip()
    tok = (security_token or _env("COS_SESSION_TOKEN")
           or _env("TENCENTCLOUD_SESSIONTOKEN")).strip()
    return sid, skey, tok


def _bucket_host() -> tuple[str, str]:
    bucket = _env("COS_BUCKET").strip()
    region = _env("COS_REGION", "ap-shanghai").strip()
    if not bucket:
        raise RuntimeError("COS_BUCKET env var required for cos_kv")
    host = f"{bucket}.cos.{region}.myqcloud.com"
    return bucket, host


def _public_base_url() -> str:
    """If COS_PUBLIC_BASE_URL set, use it (CDN); else fall back to bucket origin."""
    explicit = _env("COS_PUBLIC_BASE_URL").strip().rstrip("/")
    if explicit:
        return explicit
    _bucket, host = _bucket_host()
    return f"https://{host}"


# ---------------------------------------------------------------------------
# COS V5 signature (sha1 / q-sign-algorithm)
# Reference: https://cloud.tencent.com/document/product/436/7778
# ---------------------------------------------------------------------------

def _canon_uri(key: str) -> str:
    """Encode each path segment, keep '/' separators."""
    key = key.lstrip("/")
    parts = [urllib.parse.quote(p, safe="-_.~") for p in key.split("/")]
    return "/" + "/".join(parts)


def _canon_kv(items: list[tuple[str, str]]) -> tuple[str, str]:
    items_sorted = sorted((k.lower(), v) for k, v in items)
    pairs = "&".join(
        f"{urllib.parse.quote(k, safe='-_.~')}={urllib.parse.quote(str(v), safe='-_.~')}"
        for k, v in items_sorted
    )
    name_list = ";".join(k for k, _ in items_sorted)
    return pairs, name_list


def _sign(method: str, uri: str, *, query: dict[str, str], headers: dict[str, str],
          secret_id: str, secret_key: str, expire_seconds: int = 3600) -> str:
    """Build the Authorization header value for a COS V5 request."""
    start_ts = int(time.time()) - 60
    end_ts = start_ts + expire_seconds + 60
    key_time = f"{start_ts};{end_ts}"

    sign_key = hmac.new(secret_key.encode("utf-8"), key_time.encode("utf-8"),
                        hashlib.sha1).hexdigest()

    qs, q_list = _canon_kv(list(query.items()))
    hdr_items = [(k, v) for k, v in headers.items()
                 if k.lower() in {"host", "content-type", "content-md5", "content-length",
                                  "x-cos-security-token", "x-cos-meta-mtime"}]
    hs, h_list = _canon_kv(hdr_items)

    http_string = f"{method.lower()}\n{uri}\n{qs}\n{hs}\n"
    string_to_sign = (
        f"sha1\n{key_time}\n"
        f"{hashlib.sha1(http_string.encode('utf-8')).hexdigest()}\n"
    )
    signature = hmac.new(sign_key.encode("utf-8"), string_to_sign.encode("utf-8"),
                         hashlib.sha1).hexdigest()
    return (
        f"q-sign-algorithm=sha1&q-ak={secret_id}&q-sign-time={key_time}"
        f"&q-key-time={key_time}&q-header-list={h_list}"
        f"&q-url-param-list={q_list}&q-signature={signature}"
    )


# ---------------------------------------------------------------------------
# HTTP helper
# ---------------------------------------------------------------------------

class CosError(RuntimeError):
    def __init__(self, status: int, body: str):
        super().__init__(f"COS HTTP {status}: {body[:300]}")
        self.status = status
        self.body = body


def _request(method: str, key: str, *, body: bytes | None = None,
             extra_headers: dict[str, str] | None = None,
             query: dict[str, str] | None = None,
             secret_id: str | None = None, secret_key: str | None = None,
             security_token: str | None = None, timeout: float = 30.0) -> tuple[int, bytes, dict[str, str]]:
    """Low-level COS HTTP call. Returns (status, body, headers)."""
    sid, skey, tok = _credentials(secret_id, secret_key, security_token)
    if not sid or not skey:
        raise RuntimeError(
            "Missing COS credentials: set COS_SECRET_ID/COS_SECRET_KEY "
            "or rely on TENCENTCLOUD_SECRETID/TENCENTCLOUD_SECRETKEY (SCF runtime)"
        )
    _bucket, host = _bucket_host()
    uri = _canon_uri(key)
    q = dict(query or {})

    hdrs: dict[str, str] = {"Host": host}
    if body is not None:
        hdrs["Content-Length"] = str(len(body))
        hdrs.setdefault("Content-Type", "application/octet-stream")
    if extra_headers:
        hdrs.update(extra_headers)
    if tok:
        hdrs["x-cos-security-token"] = tok

    authz = _sign(method, uri, query=q, headers=hdrs,
                  secret_id=sid, secret_key=skey)
    hdrs["Authorization"] = authz

    qs = "&".join(f"{urllib.parse.quote(k, safe='-_.~')}={urllib.parse.quote(v, safe='-_.~')}"
                  for k, v in q.items())
    url = f"https://{host}{uri}" + (f"?{qs}" if qs else "")
    req = urllib.request.Request(url, data=body, headers=hdrs, method=method.upper())
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read(), dict(resp.headers.items())
    except urllib.error.HTTPError as e:
        raw = e.read()
        return e.code, raw, dict(e.headers.items())


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def put_bytes(key: str, payload: bytes, *,
              content_type: str = "application/octet-stream",
              public: bool = False, **kw) -> str:
    """Upload bytes; returns the public origin URL (caller must ensure ACL if needed)."""
    extra: dict[str, str] = {"Content-Type": content_type}
    if public:
        extra["x-cos-acl"] = "public-read"
    status, body, _ = _request("PUT", key, body=payload, extra_headers=extra, **kw)
    if status not in (200, 201):
        raise CosError(status, body.decode("utf-8", "replace"))
    return f"{_public_base_url()}/{key.lstrip('/')}"


def put_json(key: str, data: dict, **kw) -> str:
    payload = json.dumps(data, ensure_ascii=False).encode("utf-8")
    return put_bytes(key, payload, content_type="application/json; charset=utf-8", **kw)


def put_text_public(key: str, text: str, *,
                    content_type: str = "text/plain; charset=utf-8", **kw) -> str:
    payload = text.encode("utf-8")
    return put_bytes(key, payload, content_type=content_type, public=True, **kw)


def presigned_get_url(key: str, *, expire_seconds: int = 86400,
                      secret_id: str | None = None, secret_key: str | None = None,
                      security_token: str | None = None) -> str:
    """Generate a time-limited GET URL signed with q-sign-algorithm=sha1.

    Works regardless of bucket ACL (private buckets are fine), since the signature
    is embedded in the query string.
    """
    sid, skey, tok = _credentials(secret_id, secret_key, security_token)
    if not sid or not skey:
        raise RuntimeError("Missing COS credentials for presigned_get_url")
    _bucket, host = _bucket_host()
    uri = _canon_uri(key)

    start_ts = int(time.time()) - 60
    end_ts = start_ts + max(60, int(expire_seconds))
    key_time = f"{start_ts};{end_ts}"
    sign_key = hmac.new(skey.encode("utf-8"), key_time.encode("utf-8"),
                        hashlib.sha1).hexdigest()
    qs, q_list = _canon_kv([])
    hs, h_list = _canon_kv([])
    http_string = f"get\n{uri}\n{qs}\n{hs}\n"
    sts = (f"sha1\n{key_time}\n"
           f"{hashlib.sha1(http_string.encode('utf-8')).hexdigest()}\n")
    signature = hmac.new(sign_key.encode("utf-8"), sts.encode("utf-8"),
                         hashlib.sha1).hexdigest()
    params = [
        ("q-sign-algorithm", "sha1"),
        ("q-ak", sid),
        ("q-sign-time", key_time),
        ("q-key-time", key_time),
        ("q-header-list", h_list),
        ("q-url-param-list", q_list),
        ("q-signature", signature),
    ]
    if tok:
        params.append(("x-cos-security-token", tok))
    query = "&".join(
        f"{urllib.parse.quote(k, safe='-_.~')}={urllib.parse.quote(v, safe='-_.~')}"
        for k, v in params
    )
    return f"https://{host}{uri}?{query}"


def get_bytes(key: str, **kw) -> bytes | None:
    status, body, _ = _request("GET", key, **kw)
    if status == 404:
        return None
    if status != 200:
        raise CosError(status, body.decode("utf-8", "replace"))
    return body


def get_json(key: str, **kw) -> dict | None:
    raw = get_bytes(key, **kw)
    if raw is None:
        return None
    try:
        return json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as e:
        _log.warning("get_json(%s) decode fail: %s", key, e)
        return None


def delete_key(key: str, **kw) -> bool:
    status, body, _ = _request("DELETE", key, **kw)
    if status in (200, 204, 404):
        return True
    raise CosError(status, body.decode("utf-8", "replace"))


def list_keys_under(prefix: str, *, max_keys: int = 200, **kw) -> list[str]:
    """List all object keys whose name starts with prefix."""
    out: list[str] = []
    marker = ""
    while True:
        q = {"prefix": prefix, "max-keys": str(max_keys)}
        if marker:
            q["marker"] = marker
        status, body, _ = _request("GET", "/", query=q, **kw)
        if status != 200:
            raise CosError(status, body.decode("utf-8", "replace"))
        try:
            root = ET.fromstring(body)
        except ET.ParseError as e:
            raise CosError(status, f"list xml parse fail: {e}; body={body[:200]!r}")
        ns = ""
        if root.tag.startswith("{"):
            ns = root.tag[: root.tag.index("}") + 1]
        for c in root.findall(f"{ns}Contents"):
            k = c.findtext(f"{ns}Key")
            if k:
                out.append(k)
        is_truncated = (root.findtext(f"{ns}IsTruncated") or "false").lower() == "true"
        if not is_truncated:
            break
        next_marker = root.findtext(f"{ns}NextMarker") or ""
        if not next_marker:
            break
        marker = next_marker
    return out


def is_configured() -> bool:
    bucket = _env("COS_BUCKET").strip()
    sid, skey, _ = _credentials(None, None, None)
    return bool(bucket and sid and skey)


__all__ = [
    "put_bytes", "put_json", "put_text_public", "presigned_get_url",
    "get_bytes", "get_json",
    "delete_key", "list_keys_under",
    "is_configured", "CosError",
]
