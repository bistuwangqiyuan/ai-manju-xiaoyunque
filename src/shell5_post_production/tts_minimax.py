"""MiniMax Speech 2.5 HD — high-emotion TTS boost.

Reference: https://www.minimax.io/api  (model id ``speech-2.5-hd``).
Use case: lines tagged with strong emotional intent (cry / fury / plea /
fear). The orchestrator picks this route when the emotion field in a shot
exceeds ElevenLabs / Doubao's expressive range.

Pricing (2026-05): $0.08 / 1k chars.

In mock mode (``FORCE_MOCK_TTS_MINIMAX=1`` or no ``MINIMAX_API_KEY``) we
write a tiny silent placeholder so the downstream concat keeps working.
"""
from __future__ import annotations

import base64
import json
import logging
import os
import pathlib
import urllib.request
from dataclasses import dataclass

_log = logging.getLogger(__name__)


MINIMAX_TTS_ENDPOINT = "https://api.minimax.chat/v1/t2a_v2"
MINIMAX_TTS_MODEL = "speech-2.5-hd"


EMOTION_VALUES = ("happy", "sad", "angry", "fearful", "surprised", "disgusted", "neutral")


@dataclass
class MinimaxTtsRequest:
    text: str
    voice_id: str = "female-shaonv"
    emotion: str = "sad"
    speed: float = 1.0
    vol: float = 1.0
    pitch: int = 0
    sample_rate: int = 32000
    audio_format: str = "mp3"


class MinimaxTtsClient:
    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or os.environ.get("MINIMAX_API_KEY", "")
        if not self.api_key:
            raise RuntimeError(
                "Missing MINIMAX_API_KEY for MiniMax Speech 2.5 HD; "
                "set FORCE_MOCK_TTS_MINIMAX=1 to bypass."
            )

    def synth(
        self,
        request: MinimaxTtsRequest,
        output_path: str | pathlib.Path,
    ) -> str:
        if request.emotion not in EMOTION_VALUES:
            raise ValueError(f"emotion={request.emotion!r} not in {EMOTION_VALUES}")
        body = {
            "model": MINIMAX_TTS_MODEL,
            "text": request.text,
            "stream": False,
            "voice_setting": {
                "voice_id": request.voice_id,
                "speed": request.speed,
                "vol": request.vol,
                "pitch": request.pitch,
                "emotion": request.emotion,
            },
            "audio_setting": {
                "sample_rate": request.sample_rate,
                "format": request.audio_format,
            },
        }
        req = urllib.request.Request(
            MINIMAX_TTS_ENDPOINT,
            data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read())
        b64 = data.get("data", {}).get("audio") or data.get("audio")
        if not b64:
            raise RuntimeError(f"MiniMax Speech 2.5 returned no audio: {data}")
        audio = base64.b64decode(b64)
        out = pathlib.Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(audio)
        return str(out)


def _is_doubao_appid_numeric(appid: str) -> bool:
    """豆包 OpenSpeech 要求 numeric AppID (11 digits). API key 名字不可用."""
    appid = (appid or "").strip()
    if not appid:
        return False
    if appid.startswith("api-key-"):
        return False
    return appid.isdigit()


def _try_doubao_seed_tts(
    text: str,
    emotion: str,
    output_path: str | pathlib.Path,
    voice_id: str,
) -> str | None:
    """Best-effort Doubao Seed-TTS 2.0; return path on success else None."""
    appid = os.environ.get("DOUBAO_TTS_APPID", "").strip()
    token = os.environ.get("DOUBAO_TTS_TOKEN", "").strip()
    if not appid or not token:
        return None
    if not _is_doubao_appid_numeric(appid):
        _log.warning(
            "DOUBAO_TTS_APPID=%r is not numeric (expect 11-digit AppID, "
            "not 'api-key-...' string); skipping Doubao TTS, falling back",
            appid,
        )
        return None
    try:
        from .tts_doubao_icl import DoubaoIclClient, TTSRequest

        client = DoubaoIclClient(appid=appid, access_token=token)
        return client.synth(
            TTSRequest(
                text=text,
                voice_type=voice_id or "BV001_streaming",
                emotion=emotion if emotion != "fearful" else "fear",
            ),
            output_path,
        )
    except Exception as e:  # noqa: BLE001
        _log.warning("Doubao Seed-TTS failed (%s); will fallback to MiniMax", e)
        return None


def synth_high_emotion(
    *,
    text: str,
    emotion: str = "sad",
    output_path: str | pathlib.Path,
    voice_id: str = "female-shaonv",
    mock: bool | None = None,
) -> str:
    """Top-level helper. Returns the on-disk audio path.

    Routing (in order):
      1. ``TTS_PRIMARY=doubao`` + DOUBAO_TTS_APPID/TOKEN present
         → 豆包 Seed-TTS 2.0 (国产, 国内推荐)
      2. fall back to MiniMax Speech 2.5 HD (海外)
      3. mock mode (no creds / explicit ``FORCE_MOCK_TTS_MINIMAX=1``)

    Mock mode writes a tiny near-silent MP3 fragment so downstream concat
    keeps working without spending API budget.
    """
    tts_primary = (os.environ.get("TTS_PRIMARY", "") or "").strip().lower()

    # Route 1: 豆包优先 (国产)
    if tts_primary == "doubao":
        out = _try_doubao_seed_tts(text, emotion, output_path, voice_id)
        if out:
            return out

    # Mock check (only kicks in after we've tried Doubao)
    if mock is None:
        mock = (
            os.environ.get("FORCE_MOCK_TTS_MINIMAX") == "1"
            or not os.environ.get("MINIMAX_API_KEY")
        )
    if mock and tts_primary != "doubao":
        # If user explicitly wants doubao but didn't set keys, try one more
        # time to see if doubao keys came through env reload; else mock.
        out = _try_doubao_seed_tts(text, emotion, output_path, voice_id)
        if out:
            return out
    if mock:
        out = pathlib.Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(
            b"ID3\x03\x00\x00\x00\x00\x00\x00" + b"\xff\xfb\x90\x44" * 32
        )
        return str(out)

    # Route 2: MiniMax fallback (海外)
    client = MinimaxTtsClient()
    return client.synth(
        MinimaxTtsRequest(text=text, emotion=emotion, voice_id=voice_id),
        output_path,
    )


__all__ = [
    "MinimaxTtsClient",
    "MinimaxTtsRequest",
    "synth_high_emotion",
    "EMOTION_VALUES",
    "MINIMAX_TTS_ENDPOINT",
    "MINIMAX_TTS_MODEL",
]
