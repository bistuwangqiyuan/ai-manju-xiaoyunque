"""Veo 3.1 — climax shot precision repair.

Veo 3.1 Fast: $0.15/sec, natively 9:16 1080P, native audio.
Veo 3.1 Standard: $0.40/sec, 4K up-sample available.
"""
from __future__ import annotations

import json
import os
import time

import urllib.request

from .repair_router import RepairContext


class Veo31Repair:
    """Google Vertex AI — Veo 3.1 reference-to-video repair."""

    def __init__(self,
                 project: str | None = None,
                 location: str = "us-central1",
                 model: str = "veo-3.1-fast-generate-001",
                 access_token: str | None = None,
                 duration_seconds: int = 6):
        self.project = project or os.environ.get("GOOGLE_CLOUD_PROJECT", "")
        if not self.project:
            raise RuntimeError("Missing GOOGLE_CLOUD_PROJECT")
        self.location = location
        self.model = model
        self.access_token = access_token or os.environ.get("GOOGLE_ACCESS_TOKEN", "")
        self.duration_seconds = duration_seconds

    def __call__(self, context: RepairContext) -> str:
        sidecar = json.loads(context.shot_prompt) if context.shot_prompt.startswith("{") else {}
        url = (
            f"https://{self.location}-aiplatform.googleapis.com/v1/projects/"
            f"{self.project}/locations/{self.location}/publishers/google/"
            f"models/{self.model}:predictLongRunning"
        )
        body = json.dumps({
            "instances": [{
                "prompt": sidecar.get("prompt", ""),
                "referenceImages": [
                    {"image": {"gcsUri": img}}
                    for img in sidecar.get("reference_image_urls", [context.canonical_image_url])
                ],
                "aspectRatio": "9:16",
                "durationSeconds": self.duration_seconds,
                "resolution": "1080p",
                "generateAudio": True,
            }],
            "parameters": {"sampleCount": 1},
        }).encode("utf-8")
        req = urllib.request.Request(
            url, data=body,
            headers={
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read())
        return self._poll_lro(data["name"])

    def _poll_lro(self, operation: str, *, interval: float = 10.0, timeout: float = 900.0) -> str:
        deadline = time.monotonic() + timeout
        url = (
            f"https://{self.location}-aiplatform.googleapis.com/v1/{operation}"
        )
        while time.monotonic() < deadline:
            req = urllib.request.Request(
                url,
                headers={"Authorization": f"Bearer {self.access_token}"},
                method="GET",
            )
            with urllib.request.urlopen(req, timeout=60) as resp:
                op = json.loads(resp.read())
            if op.get("done"):
                videos = op.get("response", {}).get("videos") or op.get("response", {}).get("generatedSamples", [])
                if not videos:
                    raise RuntimeError(f"Veo LRO complete but no video: {op}")
                v = videos[0]
                return v.get("gcsUri") or v.get("video", {}).get("uri") or v.get("uri", "")
            time.sleep(interval)
        raise TimeoutError("Veo 3.1 generation timed out")
