"""Sora 2 Pro — top-god-tier repair for ep09 climax (revenant手伸出革囊).

WARNING: Sora 2 API禁止上传任何他人脸照（含动漫风格）。
This route is only safe for pure text-prompt or scene-only image prompts
without identifiable faces. The pipeline only dispatches this route to ep09's
revenant shot where the face is intentionally obscured (cloth/sleeve overlap).
"""
from __future__ import annotations

import json
import os
import time

import urllib.request

from .repair_router import RepairContext


class Sora2ProRepair:
    def __init__(self,
                 api_key: str | None = None,
                 base_url: str = "https://api.openai.com/v1",
                 model: str = "sora-2-pro",
                 resolution: str = "1080x1920",
                 duration_seconds: int = 8):
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY", "")
        if not self.api_key:
            raise RuntimeError("Missing OPENAI_API_KEY")
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.resolution = resolution
        self.duration_seconds = duration_seconds

    def __call__(self, context: RepairContext) -> str:
        sidecar = json.loads(context.shot_prompt) if context.shot_prompt.startswith("{") else {}
        prompt = sidecar.get("prompt", "")
        if sidecar.get("contains_face", True):
            raise RuntimeError(
                "Sora 2 Pro API禁止脸部参考；context.contains_face=True，路由拒绝。"
            )
        payload = {
            "model": self.model,
            "prompt": prompt,
            "size": self.resolution,
            "n_seconds": self.duration_seconds,
        }
        body = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            f"{self.base_url}/videos/generations",
            data=body,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read())
        return self._poll(data["id"])

    def _poll(self, video_id: str, *, interval: float = 8.0, timeout: float = 900.0) -> str:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            req = urllib.request.Request(
                f"{self.base_url}/videos/generations/{video_id}",
                headers={"Authorization": f"Bearer {self.api_key}"},
                method="GET",
            )
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = json.loads(resp.read())
            status = data.get("status")
            if status == "succeeded":
                return data["video"]["url"]
            if status == "failed":
                raise RuntimeError(f"Sora 2 failed: {data}")
            time.sleep(interval)
        raise TimeoutError("Sora 2 generation timed out")
