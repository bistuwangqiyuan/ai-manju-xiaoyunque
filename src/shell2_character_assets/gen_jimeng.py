"""即梦 Image 4.6 — pose / wardrobe variants for character asset library."""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Sequence

from ..common.volc_signer import sign_request
import urllib.request


@dataclass
class JimengRequest:
    prompt: str
    reference_images: Sequence[str] = ()
    num_images: int = 6
    aspect_ratio: str = "3:4"
    reference_weight: float = 0.85


class JimengImageClient:
    """req_key=jimeng_t2i_v46 — 文生图 4.6 with reference images."""

    def __init__(self,
                 access_key: str | None = None,
                 secret_key: str | None = None,
                 req_key: str = "jimeng_t2i_v46",
                 api_version: str = "2022-08-31"):
        self.access_key = access_key or os.environ.get("VOLC_ACCESS_KEY", "")
        self.secret_key = secret_key or os.environ.get("VOLC_SECRET_KEY", "")
        if not self.access_key or not self.secret_key:
            raise RuntimeError("Missing VOLC_ACCESS_KEY / VOLC_SECRET_KEY")
        self.req_key = req_key
        self.api_version = api_version

    def generate(self, request: JimengRequest) -> list[str]:
        payload = {
            "req_key": self.req_key,
            "prompt": request.prompt,
            "num_images": request.num_images,
            "aspect_ratio": request.aspect_ratio,
            "reference_weight": request.reference_weight,
        }
        if request.reference_images:
            payload["reference_images"] = list(request.reference_images)
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
            raise RuntimeError(f"即梦 4.6 error: {data}")
        return list(data.get("data", {}).get("image_urls", []))
