"""Veo 3.1 upscaler — 1080P → 4K master for Top 1-3 episodes."""
from __future__ import annotations

import json
import os
import time

import urllib.request


class Veo31Upscaler:
    def __init__(self,
                 project: str | None = None,
                 location: str = "us-central1",
                 access_token: str | None = None,
                 model: str = "veo-3.1-upscaler"):
        self.project = project or os.environ.get("GOOGLE_CLOUD_PROJECT", "")
        if not self.project:
            raise RuntimeError("Missing GOOGLE_CLOUD_PROJECT")
        self.location = location
        self.access_token = access_token or os.environ.get("GOOGLE_ACCESS_TOKEN", "")
        self.model = model

    def upscale(self, source_video_url: str, target_resolution: str = "2160x3840") -> str:
        url = (
            f"https://{self.location}-aiplatform.googleapis.com/v1/projects/"
            f"{self.project}/locations/{self.location}/publishers/google/"
            f"models/{self.model}:predictLongRunning"
        )
        body = json.dumps({
            "instances": [{
                "videoUri": source_video_url,
                "outputResolution": target_resolution,
            }],
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
        return self._poll(data["name"])

    def _poll(self, operation: str, *, interval: float = 10.0, timeout: float = 1800.0) -> str:
        deadline = time.monotonic() + timeout
        url = (
            f"https://{self.location}-aiplatform.googleapis.com/v1/{operation}"
        )
        while time.monotonic() < deadline:
            req = urllib.request.Request(
                url, headers={"Authorization": f"Bearer {self.access_token}"},
                method="GET",
            )
            with urllib.request.urlopen(req, timeout=60) as resp:
                op = json.loads(resp.read())
            if op.get("done"):
                videos = op.get("response", {}).get("videos", [])
                if not videos:
                    raise RuntimeError(f"Upscaler LRO complete but no video: {op}")
                return videos[0].get("gcsUri") or videos[0].get("uri", "")
            time.sleep(interval)
        raise TimeoutError("Veo 3.1 upscaler timed out")
