"""ElevenLabs Sound Effects API — $0.12/clip, royalty-free."""
from __future__ import annotations

import json
import os
import pathlib

import urllib.request


class ElevenLabsSfxClient:
    def __init__(self,
                 api_key: str | None = None,
                 base_url: str = "https://api.elevenlabs.io/v1"):
        self.api_key = api_key or os.environ.get("ELEVENLABS_API_KEY", "")
        if not self.api_key:
            raise RuntimeError("Missing ELEVENLABS_API_KEY")
        self.base_url = base_url.rstrip("/")

    def generate(self, prompt: str, duration_seconds: float | None = None,
                 output_path: str | pathlib.Path = "sfx.mp3") -> str:
        payload: dict = {"text": prompt}
        if duration_seconds:
            payload["duration_seconds"] = duration_seconds
        body = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            f"{self.base_url}/sound-generation",
            data=body,
            headers={
                "xi-api-key": self.api_key,
                "Content-Type": "application/json",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=120) as resp:
            audio = resp.read()
        out = pathlib.Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(audio)
        return str(out)
