"""Seedream 5.0 Lite — multi-view character sheet (8 angles)."""
from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from typing import Sequence

from ..common.volc_signer import sign_request
import urllib.request


_log = logging.getLogger(__name__)


@dataclass
class SeedreamRequest:
    prompt: str
    reference_images: Sequence[str] = ()
    num_images: int = 8
    aspect_ratio: str = "3:4"
    deep_thinking: bool = True
    seed: int | None = None


class SeedreamClient:
    """Volcengine Visual OpenAPI — Seedream 5.0 Lite (req_key=jimeng_t2i_v50_lite)."""

    def __init__(self,
                 access_key: str | None = None,
                 secret_key: str | None = None,
                 req_key: str = "jimeng_t2i_v50_lite",
                 api_version: str = "2022-08-31"):
        self.access_key = access_key or os.environ.get("VOLC_ACCESS_KEY", "")
        self.secret_key = secret_key or os.environ.get("VOLC_SECRET_KEY", "")
        if not self.access_key or not self.secret_key:
            raise RuntimeError("Missing VOLC_ACCESS_KEY / VOLC_SECRET_KEY")
        self.req_key = req_key
        self.api_version = api_version

    def generate(self, request: SeedreamRequest) -> list[str]:
        payload = {
            "req_key": self.req_key,
            "prompt": request.prompt,
            "num_images": request.num_images,
            "aspect_ratio": request.aspect_ratio,
            "deep_thinking": request.deep_thinking,
        }
        if request.reference_images:
            payload["reference_images"] = list(request.reference_images)
        if request.seed is not None:
            payload["seed"] = request.seed
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        signed = sign_request(
            access_key=self.access_key, secret_key=self.secret_key,
            action="CVProcess", version=self.api_version, body=body,
        )
        req = urllib.request.Request(
            signed.url, data=signed.body, headers=signed.headers, method=signed.method,
        )
        with urllib.request.urlopen(req, timeout=180) as resp:
            data = json.loads(resp.read())
        if data.get("code") != 10000:
            raise RuntimeError(f"Seedream error: {data}")
        images = data.get("data", {}).get("image_urls") or data.get("data", {}).get("images", [])
        return list(images)
