"""Wan 2.7-FLF 14B repair — first/last-frame lock for face drift."""
from __future__ import annotations

import json
import os

import urllib.request

from .repair_router import RepairContext


class WanFlfRepair:
    """First/last-frame video generation via Wan 2.7-FLF-14B (Apache 2.0)."""

    def __init__(self,
                 api_token: str | None = None,
                 endpoint: str = "https://fal.run/fal-ai/wan-2.7-flf",
                 duration_seconds: int = 5):
        self.api_token = api_token or os.environ.get("FAL_API_KEY", "")
        if not self.api_token:
            raise RuntimeError("Missing FAL_API_KEY")
        self.endpoint = endpoint
        self.duration_seconds = duration_seconds

    def __call__(self, context: RepairContext) -> str:
        # The repair pipeline must have extracted first / last frames upstream
        # and uploaded them; we expect those paths in context.shot_prompt as
        # a JSON sidecar `{"first_frame_url": ..., "last_frame_url": ...}`.
        sidecar = json.loads(context.shot_prompt) if context.shot_prompt.startswith("{") else {}
        payload = {
            "first_frame_url": sidecar.get("first_frame_url"),
            "last_frame_url": sidecar.get("last_frame_url", context.canonical_image_url),
            "prompt": sidecar.get("prompt", ""),
            "duration_seconds": self.duration_seconds,
            "aspect_ratio": "9:16",
        }
        body = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            self.endpoint, data=body,
            headers={"Authorization": f"Key {self.api_token}", "Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=300) as resp:
            data = json.loads(resp.read())
        return data["video"]["url"]
