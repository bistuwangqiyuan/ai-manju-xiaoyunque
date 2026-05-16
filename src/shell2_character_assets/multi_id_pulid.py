"""PuLID — multi-character lock for shared frames.

Runtime: Replicate endpoint `fofr/pulid`.
Use case: when more than one主角 appears in the same frame (e.g. 宁采臣 + 小倩
in the wedding shot), PuLID keeps each face on-model simultaneously.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Sequence

import urllib.request


@dataclass
class PuLIDCharSpec:
    char_id: str
    face_image_url: str
    weight: float = 1.0


@dataclass
class PuLIDRequest:
    prompt: str
    characters: Sequence[PuLIDCharSpec]
    aspect_ratio: str = "9:16"
    seed: int | None = None


class PuLIDClient:
    def __init__(self,
                 api_token: str | None = None,
                 endpoint: str = "https://api.replicate.com/v1/predictions",
                 model_version: str = "fofr/pulid"):
        self.api_token = api_token or os.environ.get("REPLICATE_API_TOKEN", "")
        if not self.api_token:
            raise RuntimeError("Missing REPLICATE_API_TOKEN")
        self.endpoint = endpoint
        self.model_version = model_version

    def generate(self, request: PuLIDRequest) -> str:
        if len(request.characters) > 4:
            raise ValueError("PuLID supports at most 4 simultaneous characters")
        payload = {
            "version": self.model_version,
            "input": {
                "prompt": request.prompt,
                "id_images": [c.face_image_url for c in request.characters],
                "id_weights": [c.weight for c in request.characters],
                "aspect_ratio": request.aspect_ratio,
                "seed": request.seed,
            },
        }
        body = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            self.endpoint, data=body,
            headers={
                "Authorization": f"Token {self.api_token}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=180) as resp:
            data = json.loads(resp.read())
        outputs = data.get("output") or []
        return outputs[0] if outputs else ""
