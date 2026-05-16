"""豆包 Seed-TTS 2.0 + ICL 2.0 — 97.5% voice clone, <300ms first packet.

The official endpoint requires a per-tenant 「应用 appid」 + access token plus
a server-side 「集群 cluster」. We expose the canonical OpenSpeech endpoints
for both the streaming and async batch APIs.

Reference: https://www.volcengine.com/docs/6561 (语音技术·TTS)
"""
from __future__ import annotations

import base64
import json
import logging
import os
import pathlib
from dataclasses import dataclass

import urllib.request


_log = logging.getLogger(__name__)


@dataclass
class TTSRequest:
    text: str
    voice_type: str                    # 复刻音色 ID（来自豆包音色训练台）
    speed_ratio: float = 1.0
    volume_ratio: float = 1.0
    pitch_ratio: float = 1.0
    emotion: str | None = None         # neutral / happy / sad / angry / fear
    sample_rate: int = 24000
    encoding: str = "mp3"


class DoubaoIclClient:
    """Synchronous TTS (best for ≤ 5000 字)."""

    def __init__(self,
                 appid: str | None = None,
                 access_token: str | None = None,
                 cluster: str = "volcano_icl",
                 endpoint: str = "https://openspeech.bytedance.com/api/v1/tts"):
        self.appid = appid or os.environ.get("DOUBAO_TTS_APPID", "")
        self.access_token = access_token or os.environ.get("DOUBAO_TTS_TOKEN", "")
        if not self.appid or not self.access_token:
            raise RuntimeError("Missing DOUBAO_TTS_APPID / DOUBAO_TTS_TOKEN")
        self.cluster = cluster
        self.endpoint = endpoint

    def synth(self, request: TTSRequest, output_path: str | pathlib.Path) -> str:
        payload = {
            "app": {
                "appid": self.appid,
                "token": self.access_token,
                "cluster": self.cluster,
            },
            "user": {"uid": "skylark_pipeline"},
            "audio": {
                "voice_type": request.voice_type,
                "encoding": request.encoding,
                "speed_ratio": request.speed_ratio,
                "volume_ratio": request.volume_ratio,
                "pitch_ratio": request.pitch_ratio,
                "rate": request.sample_rate,
                "emotion": request.emotion or "neutral",
            },
            "request": {
                "reqid": "skylark_" + str(os.urandom(8).hex()),
                "text": request.text,
                "operation": "query",
            },
        }
        body = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            self.endpoint, data=body,
            headers={
                "Authorization": f"Bearer; {self.access_token}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read())
        if data.get("code") != 3000:
            raise RuntimeError(f"豆包 TTS error: {data}")
        b64 = data.get("data") or data.get("audio_base64", "")
        audio = base64.b64decode(b64)
        out = pathlib.Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(audio)
        return str(out)
