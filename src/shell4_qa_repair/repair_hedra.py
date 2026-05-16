"""Hedra Character-3 — close-up dialogue lip-sync repair (95%+ accuracy)."""
from __future__ import annotations

import json
import os
import time

import urllib.request

from .repair_router import RepairContext


class HedraRepair:
    """Render a talking-head video from a portrait + an audio track."""

    def __init__(self,
                 api_key: str | None = None,
                 base_url: str = "https://api.hedra.com/web-app/public"):
        self.api_key = api_key or os.environ.get("HEDRA_API_KEY", "")
        if not self.api_key:
            raise RuntimeError("Missing HEDRA_API_KEY")
        self.base_url = base_url.rstrip("/")

    def __call__(self, context: RepairContext) -> str:
        sidecar = json.loads(context.shot_prompt) if context.shot_prompt.startswith("{") else {}
        audio_url = sidecar.get("audio_url")
        portrait_url = sidecar.get("portrait_url", context.canonical_image_url)
        if not audio_url:
            raise ValueError("HedraRepair requires audio_url in sidecar JSON")

        payload = {
            "model": "character-3",
            "image_url": portrait_url,
            "audio_url": audio_url,
            "aspect_ratio": "9:16",
            "resolution": "720p",
            "lipsync_quality": "high",
        }
        body = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            f"{self.base_url}/generations",
            data=body,
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read())
        gen_id = data["id"]
        return self._poll(gen_id)

    def _poll(self, gen_id: str, *, interval: float = 5.0, timeout: float = 600.0) -> str:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            req = urllib.request.Request(
                f"{self.base_url}/generations/{gen_id}",
                headers={"Authorization": f"Bearer {self.api_key}"},
                method="GET",
            )
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = json.loads(resp.read())
            if data.get("status") == "complete":
                return data["url"]
            if data.get("status") == "error":
                raise RuntimeError(f"Hedra error: {data}")
            time.sleep(interval)
        raise TimeoutError("Hedra generation timed out")
