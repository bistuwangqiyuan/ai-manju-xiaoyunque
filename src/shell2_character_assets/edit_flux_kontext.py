"""FLUX.1 Kontext (Pro / Max) — edit-mode fallback.

Use case: in-painting / wardrobe-fix when a single shot drifts from the
canonical wardrobe. Achieves CLIP similarity ≥ 0.92 in edit mode (the
highest among production-grade APIs as of 2026/05).
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass

import urllib.request


@dataclass
class FluxKontextEditRequest:
    source_image_url: str
    edit_prompt: str
    mask_image_url: str | None = None
    aspect_ratio: str = "9:16"
    strength: float = 0.75


class FluxKontextClient:
    def __init__(self,
                 api_key: str | None = None,
                 endpoint: str = "https://fal.run/fal-ai/flux-kontext/pro"):
        self.api_key = api_key or os.environ.get("FAL_API_KEY", "")
        if not self.api_key:
            raise RuntimeError("Missing FAL_API_KEY")
        self.endpoint = endpoint

    def edit(self, request: FluxKontextEditRequest) -> str:
        payload = {
            "image_url": request.source_image_url,
            "prompt": request.edit_prompt,
            "strength": request.strength,
            "aspect_ratio": request.aspect_ratio,
        }
        if request.mask_image_url:
            payload["mask_url"] = request.mask_image_url
        body = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            self.endpoint, data=body,
            headers={
                "Authorization": f"Key {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=180) as resp:
            data = json.loads(resp.read())
        return data["images"][0]["url"]
