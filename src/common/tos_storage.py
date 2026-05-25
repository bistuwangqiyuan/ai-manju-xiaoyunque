"""Volcengine TOS (S3-compatible) storage backend.

Volc TOS 完全兼容 S3 协议，因此直接复用 ``boto3`` SDK 即可，无需额外 SDK。
区域 endpoint::

    cn-beijing   https://tos-cn-beijing.volces.com
    cn-shanghai  https://tos-cn-shanghai.volces.com
    cn-guangzhou https://tos-cn-guangzhou.volces.com

环境变量（按优先级）::

    TOS_ACCESS_KEY    -> S3_ACCESS_KEY -> VOLC_ACCESS_KEY -> VOLC_AK
    TOS_SECRET_KEY    -> S3_SECRET_KEY -> VOLC_SECRET_KEY -> VOLC_SK
    TOS_BUCKET        -> S3_BUCKET                              （必填）
    TOS_ENDPOINT      -> S3_ENDPOINT (默认 cn-beijing)
    TOS_REGION        -> S3_REGION   (默认 cn-beijing)
    TOS_PUBLIC_BASE   -> 可选; 用于生成 public_url 前缀 (留空则用 presigned URL)

公网访问策略：
    - 默认私有桶 + 7 天 presigned URL
    - 若设置 ``TOS_PUBLIC_BASE``（例如 CDN 域名），则用拼接方式给 public_url
    - 也支持 ``put_bytes(public=True)`` 显式置 ACL=public-read
"""
from __future__ import annotations

import hashlib
import logging
import os
import pathlib
from dataclasses import dataclass
from typing import Optional

from .storage import StoredObject

_log = logging.getLogger(__name__)


def _resolve(*keys: str, default: str = "") -> str:
    for k in keys:
        v = (os.environ.get(k) or "").strip()
        if v:
            return v
    return default


def _decode_volc_b64(raw: str) -> str:
    """Volc SK 有时存 base64; 尝试解码失败就返回原值."""
    import base64
    raw = raw.strip()
    if not raw:
        return raw
    try:
        pad = (-len(raw)) % 4
        decoded = base64.b64decode(raw + "=" * pad, validate=False).decode("utf-8").strip()
        if 8 <= len(decoded) <= 256:
            return decoded
    except Exception:  # noqa: BLE001
        pass
    return raw


@dataclass(frozen=True)
class TosConfig:
    access_key: str
    secret_key: str
    bucket: str
    endpoint: str
    region: str
    public_base: str

    @classmethod
    def from_env(cls) -> "TosConfig":
        ak = _resolve("TOS_ACCESS_KEY", "S3_ACCESS_KEY", "VOLC_ACCESS_KEY", "VOLC_AK")
        sk_raw = _resolve("TOS_SECRET_KEY", "S3_SECRET_KEY", "VOLC_SECRET_KEY", "VOLC_SK")
        sk = _decode_volc_b64(sk_raw)
        bucket = _resolve("TOS_BUCKET", "S3_BUCKET")
        endpoint = _resolve(
            "TOS_ENDPOINT", "S3_ENDPOINT",
            default="https://tos-cn-beijing.volces.com",
        )
        region = _resolve("TOS_REGION", "S3_REGION", default="cn-beijing")
        public_base = _resolve("TOS_PUBLIC_BASE", "COS_PUBLIC_BASE_URL")
        if not (ak and sk and bucket):
            raise RuntimeError(
                "TOS storage missing credentials: need TOS_ACCESS_KEY / TOS_SECRET_KEY / "
                "TOS_BUCKET (or VOLC_* / S3_* aliases)"
            )
        # endpoint sanity
        if not endpoint.startswith(("http://", "https://")):
            endpoint = "https://" + endpoint
        return cls(
            access_key=ak, secret_key=sk, bucket=bucket,
            endpoint=endpoint, region=region, public_base=public_base.rstrip("/"),
        )


class TosStorage:
    """S3-compatible 实现 — 接口与 :class:`src.common.storage.Storage` 对齐。"""

    backend_name = "tos"

    def __init__(self, config: Optional[TosConfig] = None, *,
                 presign_ttl_seconds: int = 7 * 24 * 3600):
        try:
            import boto3  # noqa: F401  ;import lazily to avoid hard dep
            from botocore.config import Config as BotoConfig  # noqa: F401
        except ImportError as e:
            raise RuntimeError(
                "boto3 not installed; pip install boto3 to use TOS backend"
            ) from e

        self.cfg = config or TosConfig.from_env()
        self.presign_ttl = int(presign_ttl_seconds)
        self._client = self._build_client()

    def _build_client(self):
        import boto3
        from botocore.config import Config as BotoConfig
        boto_cfg = BotoConfig(
            region_name=self.cfg.region,
            s3={"addressing_style": "virtual"},
            signature_version="s3v4",
            retries={"max_attempts": 5, "mode": "standard"},
        )
        return boto3.client(
            "s3",
            endpoint_url=self.cfg.endpoint,
            region_name=self.cfg.region,
            aws_access_key_id=self.cfg.access_key,
            aws_secret_access_key=self.cfg.secret_key,
            config=boto_cfg,
        )

    # ---------------- public API ----------------

    def put_bytes(self, key: str, payload: bytes, *, public: bool = False) -> StoredObject:
        key = key.lstrip("/")
        sha = hashlib.sha256(payload).hexdigest()
        extra = {"ContentType": self._guess_ct(key)}
        if public:
            extra["ACL"] = "public-read"
        self._client.put_object(
            Bucket=self.cfg.bucket, Key=key, Body=payload, **extra,
        )
        return StoredObject(
            backend=self.backend_name,
            path=f"tos://{self.cfg.bucket}/{key}",
            public_url=self._public_url(key, public=public),
            sha256=sha,
            size_bytes=len(payload),
        )

    def put_file(self, key: str, src_path: str | os.PathLike, *,
                 public: bool = False) -> StoredObject:
        payload = pathlib.Path(src_path).read_bytes()
        return self.put_bytes(key, payload, public=public)

    def archive_url(self, key: str, url: str, *, timeout: float = 600.0) -> StoredObject:
        """Download a (TTL-limited) URL and re-host in TOS."""
        import urllib.request
        req = urllib.request.Request(url, headers={"User-Agent": "xyq-archive/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            payload = resp.read()
        return self.put_bytes(key, payload)

    def get_bytes(self, key: str) -> bytes:
        key = key.lstrip("/")
        resp = self._client.get_object(Bucket=self.cfg.bucket, Key=key)
        return resp["Body"].read()

    def head(self, key: str) -> dict:
        key = key.lstrip("/")
        return self._client.head_object(Bucket=self.cfg.bucket, Key=key)

    def list_prefix(self, prefix: str, *, max_keys: int = 1000) -> list[dict]:
        resp = self._client.list_objects_v2(
            Bucket=self.cfg.bucket, Prefix=prefix.lstrip("/"), MaxKeys=max_keys,
        )
        return resp.get("Contents", []) or []

    def delete(self, key: str) -> None:
        self._client.delete_object(Bucket=self.cfg.bucket, Key=key.lstrip("/"))

    # ---------------- helpers ----------------

    def _public_url(self, key: str, *, public: bool) -> Optional[str]:
        if public and self.cfg.public_base:
            return f"{self.cfg.public_base}/{key}"
        # private — return presigned URL (7-day default per TOS limits)
        try:
            return self._client.generate_presigned_url(
                "get_object",
                Params={"Bucket": self.cfg.bucket, "Key": key},
                ExpiresIn=self.presign_ttl,
            )
        except Exception:  # noqa: BLE001
            return None

    @staticmethod
    def _guess_ct(key: str) -> str:
        import mimetypes
        ct, _ = mimetypes.guess_type(key)
        return ct or "application/octet-stream"


__all__ = ["TosStorage", "TosConfig"]
