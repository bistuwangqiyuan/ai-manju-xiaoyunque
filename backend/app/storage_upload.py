"""Optional S3/R2 upload for rendered masters."""
from __future__ import annotations

import pathlib
from typing import Optional

from .settings import settings


def upload_if_configured(local_path: str, key: str) -> Optional[str]:
    """Upload file to S3-compatible storage; return public URL or None."""
    if not settings.S3_BUCKET or not settings.S3_ACCESS_KEY:
        return None
    try:
        import boto3
    except ImportError:
        return None

    client = boto3.client(
        "s3",
        endpoint_url=settings.S3_ENDPOINT or None,
        region_name=settings.S3_REGION,
        aws_access_key_id=settings.S3_ACCESS_KEY,
        aws_secret_access_key=settings.S3_SECRET_KEY,
    )
    path = pathlib.Path(local_path)
    client.upload_file(str(path), settings.S3_BUCKET, key, ExtraArgs={"ContentType": "video/mp4"})
    base = settings.S3_PUBLIC_BASE_URL.rstrip("/")
    return f"{base}/{key}"
