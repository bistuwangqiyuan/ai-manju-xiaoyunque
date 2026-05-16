"""Seedance 2.0 fallback when Skylark is queued out or saturated.

Seedance 2.0 is the underlying rendering muscle of Skylark; calling it
directly via ARK OpenAPI bypasses the agent-level orchestration but allows
larger throughput when Skylark is throttling.

Documented model id: doubao-seedance-2-0-260128 (火山方舟，2026/04 GA)
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Sequence


@dataclass
class SeedanceRequest:
    prompt: str
    reference_images: Sequence[str]
    aspect_ratio: str = "9:16"
    duration_seconds: int = 8
    resolution: str = "1080p"
    mode: str = "pro"


class SeedanceFallbackClient:
    """Thin stub for the ARK OpenAI-compatible endpoint of Seedance 2.0."""

    def __init__(self, api_key: str | None = None,
                 base_url: str = "https://ark.cn-beijing.volces.com/api/v3"):
        self.api_key = api_key or os.environ.get("VOLC_ARK_API_KEY", "")
        if not self.api_key:
            raise RuntimeError("Missing VOLC_ARK_API_KEY for Seedance 2.0")
        self.base_url = base_url.rstrip("/")

    def generate(self, request: SeedanceRequest) -> dict:
        """Submit a Seedance 2.0 video generation job and return ARK task descriptor.

        The ARK API uses a tasks/{id}/result polling pattern very similar to
        Skylark, but with the ARK `cgt-YYYYMMDD-xxxxx` task_id format and
        OpenAI-compatible headers. Wiring it up requires the official ARK SDK
        once the access keys are provisioned.
        """
        raise NotImplementedError(
            "Wire to ARK SDK after VOLC_ARK_API_KEY provisioning. "
            "See https://www.volcengine.com/docs/82379 for the latest ARK API."
        )
