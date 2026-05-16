"""InfiniteYou (ByteDance) — static ID-embedding injection.

Runtime: fal.ai endpoint `fal-ai/infinite-you`.
Use case: extract a 512-d ID embedding vector from the canonical character
sheet, then inject into downstream generations to lock face identity.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass

import urllib.request


@dataclass
class IdEmbedding:
    char_id: str
    embedding: list[float]
    canonical_image_url: str


class InfiniteYouClient:
    def __init__(self,
                 api_key: str | None = None,
                 endpoint: str = "https://fal.run/fal-ai/infinite-you"):
        self.api_key = api_key or os.environ.get("FAL_API_KEY", "")
        if not self.api_key:
            raise RuntimeError("Missing FAL_API_KEY")
        self.endpoint = endpoint

    def extract_id(self, char_id: str, canonical_image_url: str) -> IdEmbedding:
        payload = {
            "image_url": canonical_image_url,
            "mode": "extract_id",
        }
        body = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            self.endpoint, data=body,
            headers={
                "Authorization": f"Key {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read())
        return IdEmbedding(
            char_id=char_id,
            embedding=list(data.get("id_embedding", [])),
            canonical_image_url=canonical_image_url,
        )

    def apply_to_prompt(self, embedding: IdEmbedding, prompt: str,
                        image_size: str = "portrait_16_9") -> str:
        """Generate an image conditioned on a stored ID embedding."""

        payload = {
            "prompt": prompt,
            "id_embedding": embedding.embedding,
            "image_size": image_size,
            "num_images": 1,
        }
        body = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            self.endpoint, data=body,
            headers={
                "Authorization": f"Key {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=180) as resp:
            data = json.loads(resp.read())
        return data["images"][0]["url"]
