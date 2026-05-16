"""Runway Aleph — cross-episode style unification (V2V)."""
from __future__ import annotations

import json
import os
import time

import urllib.request

from .repair_router import RepairContext


class AlephRepair:
    """Apply Runway Aleph V2V to align an episode's color/grade to the canonical reel."""

    def __init__(self,
                 api_key: str | None = None,
                 base_url: str = "https://api.dev.runwayml.com/v1"):
        self.api_key = api_key or os.environ.get("RUNWAY_API_KEY", "")
        if not self.api_key:
            raise RuntimeError("Missing RUNWAY_API_KEY")
        self.base_url = base_url.rstrip("/")

    def __call__(self, context: RepairContext) -> str:
        sidecar = json.loads(context.shot_prompt) if context.shot_prompt.startswith("{") else {}
        payload = {
            "model": "aleph",
            "videoUri": sidecar.get("input_video_url", context.shot_url),
            "promptText": sidecar.get("style_prompt",
                "古风3D国漫风：60%《白蛇缘起》+30%《狐妖小红娘月红篇》+10%《雾山五行》"),
            "referenceImages": [{"uri": context.canonical_image_url}],
            "duration": int(sidecar.get("duration", 6)),
            "ratio": "1080:1920",
        }
        body = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            f"{self.base_url}/video_to_video",
            data=body,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "X-Runway-Version": "2024-11-06",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read())
        return self._poll(data["id"])

    def _poll(self, task_id: str, *, interval: float = 8.0, timeout: float = 900.0) -> str:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            req = urllib.request.Request(
                f"{self.base_url}/tasks/{task_id}",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "X-Runway-Version": "2024-11-06",
                },
                method="GET",
            )
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = json.loads(resp.read())
            status = data.get("status")
            if status == "SUCCEEDED":
                outputs = data.get("output") or []
                return outputs[0] if outputs else ""
            if status == "FAILED":
                raise RuntimeError(f"Aleph failed: {data}")
            time.sleep(interval)
        raise TimeoutError("Aleph generation timed out")
