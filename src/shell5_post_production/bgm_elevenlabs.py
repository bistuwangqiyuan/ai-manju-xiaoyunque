"""ElevenLabs Music API — copyright-clean BGM.

Music API v1 (2026/03/24 terms) — trained on licensed stems.
$0.30/min, Self-Serve+ tier includes commercial use.
"""
from __future__ import annotations

import json
import os
import pathlib

import urllib.request


class ElevenLabsMusicClient:
    def __init__(self,
                 api_key: str | None = None,
                 base_url: str = "https://api.elevenlabs.io/v1"):
        self.api_key = api_key or os.environ.get("ELEVENLABS_API_KEY", "")
        if not self.api_key:
            raise RuntimeError("Missing ELEVENLABS_API_KEY")
        self.base_url = base_url.rstrip("/")

    def generate(self, prompt: str, duration_seconds: int = 90,
                 output_path: str | pathlib.Path = "bgm.mp3",
                 instrumental: bool = True) -> str:
        payload = {
            "prompt": prompt,
            "music_length_ms": duration_seconds * 1000,
            "instrumental": instrumental,
        }
        body = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            f"{self.base_url}/music/compose",
            data=body,
            headers={
                "xi-api-key": self.api_key,
                "Content-Type": "application/json",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=180) as resp:
            audio = resp.read()
        out = pathlib.Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(audio)
        return str(out)
