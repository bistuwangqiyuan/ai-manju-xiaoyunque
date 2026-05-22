"""ElevenLabs Multilingual v3 — TTS for international markets.

Requirement doc §一键导入或切换各国语言: 多语言 TTS / 字幕 / 配音切换。
Currently supports: en (English), ja (Japanese), ko (Korean), es, fr, de.
"""
from __future__ import annotations

import json
import logging
import os
import pathlib
import urllib.request
from dataclasses import dataclass

_log = logging.getLogger(__name__)


_LANG_TO_VOICE = {
    # ElevenLabs default voice IDs by language (each can be overridden via env).
    "en": "21m00Tcm4TlvDq8ikWAM",   # "Rachel"
    "ja": "Mu5jxyqZOLIGltFpfalg",   # "Yuki" (multilingual v3)
    "ko": "lvDpJh1RNYHkD9c2X3VX",
    "es": "TxGEqnHWrfWFTfGW9XjX",
    "fr": "EXAVITQu4vr4xnSDxMaL",
    "de": "ErXwobaYiN019PkySvjV",
}


@dataclass
class IntlTTSRequest:
    text: str
    language: str = "en"
    voice_id: str | None = None
    stability: float = 0.5
    similarity_boost: float = 0.75


class ElevenLabsMultilingualClient:
    def __init__(self, api_key: str | None = None,
                 model_id: str = "eleven_multilingual_v3"):
        self.api_key = api_key or os.environ.get("ELEVENLABS_API_KEY", "")
        self.model_id = model_id
        if not self.api_key:
            raise RuntimeError("Missing ELEVENLABS_API_KEY")

    def synth(self, request: IntlTTSRequest, output_path: str | pathlib.Path) -> str:
        voice = (
            request.voice_id
            or os.environ.get(f"ELEVENLABS_VOICE_{request.language.upper()}")
            or _LANG_TO_VOICE.get(request.language, _LANG_TO_VOICE["en"])
        )
        endpoint = f"https://api.elevenlabs.io/v1/text-to-speech/{voice}"
        body = {
            "text": request.text,
            "model_id": self.model_id,
            "voice_settings": {
                "stability": request.stability,
                "similarity_boost": request.similarity_boost,
            },
        }
        req = urllib.request.Request(
            endpoint,
            data=json.dumps(body).encode("utf-8"),
            headers={
                "xi-api-key": self.api_key,
                "Content-Type": "application/json",
                "Accept": "audio/mpeg",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=180) as resp:
            audio = resp.read()
        out = pathlib.Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(audio)
        return str(out)


__all__ = ["ElevenLabsMultilingualClient", "IntlTTSRequest"]
