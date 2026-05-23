"""DashScope Wan 2.2-Animate — action/fight choreography transfer.

Reference: https://help.aliyun.com/zh/dashscope (model id ``wan-2.2-animate``).
Use case: any shot tagged ``shot_type=="fight"`` in the storyboard. The
orchestrator extracts a reference still of the main character (canonical
sheet) and a reference action video (martial-arts library clip) and Wan
2.2-Animate transfers the body motion onto the character.

Pricing (2026-05): 480p ¥0.52/秒, 720p ¥0.87/秒.

The client is intentionally tiny — it submits, polls, returns a video URL.
In mock mode (``FORCE_MOCK_WAN_ANIMATE=1`` or missing ``DASHSCOPE_API_KEY``)
the call short-circuits and returns the reference action video URL so the
downstream concat keeps working.
"""
from __future__ import annotations

import json
import logging
import os
import time
import urllib.request
from dataclasses import dataclass

_log = logging.getLogger(__name__)


WAN_ANIMATE_MODEL = "wan-2.2-animate"
WAN_ANIMATE_SUBMIT = (
    "https://dashscope.aliyuncs.com/api/v1/services/aigc/video-generation/video-synthesis"
)
WAN_ANIMATE_POLL = "https://dashscope.aliyuncs.com/api/v1/tasks/{task_id}"


@dataclass
class WanAnimateRequest:
    character_image_url: str        # 主角 canonical 图（脸 + 全身锁定）
    action_video_url: str           # 武打动作参考视频（最长 10s）
    prompt: str = ""
    aspect_ratio: str = "9:16"
    duration_seconds: int = 6       # ≤ 10s
    resolution: str = "720p"        # "480p" | "720p"


class WanAnimateClient:
    def __init__(
        self,
        api_key: str | None = None,
        *,
        poll_interval: float = 6.0,
        timeout: float = 600.0,
    ):
        self.api_key = api_key or os.environ.get("DASHSCOPE_API_KEY", "")
        if not self.api_key:
            raise RuntimeError(
                "Missing DASHSCOPE_API_KEY (Wan 2.2-Animate); "
                "set FORCE_MOCK_WAN_ANIMATE=1 to bypass."
            )
        self.poll_interval = poll_interval
        self.timeout = timeout

    def render(self, request: WanAnimateRequest) -> str:
        if request.duration_seconds > 10:
            raise ValueError("Wan 2.2-Animate max duration is 10s")
        body = {
            "model": WAN_ANIMATE_MODEL,
            "input": {
                "character_image_url": request.character_image_url,
                "action_video_url": request.action_video_url,
                "prompt": request.prompt or "中国古风武打动作迁移，保持角色 ID 锁定",
            },
            "parameters": {
                "aspect_ratio": request.aspect_ratio,
                "duration": request.duration_seconds,
                "resolution": request.resolution,
            },
        }
        req = urllib.request.Request(
            WAN_ANIMATE_SUBMIT,
            data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "X-DashScope-Async": "enable",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read())
        task_id = data.get("output", {}).get("task_id") or data.get("task_id")
        if not task_id:
            raise RuntimeError(f"Wan 2.2-Animate: no task_id in {data}")
        return self._poll(task_id)

    def _poll(self, task_id: str) -> str:
        deadline = time.monotonic() + self.timeout
        url = WAN_ANIMATE_POLL.format(task_id=task_id)
        while time.monotonic() < deadline:
            req = urllib.request.Request(
                url,
                headers={"Authorization": f"Bearer {self.api_key}"},
                method="GET",
            )
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = json.loads(resp.read())
            status = data.get("output", {}).get("task_status") or data.get("task_status")
            if status == "SUCCEEDED":
                return (
                    data.get("output", {}).get("video_url")
                    or data.get("output", {}).get("results", [{}])[0].get("url", "")
                )
            if status in {"FAILED", "UNKNOWN", "TIMEOUT"}:
                raise RuntimeError(f"Wan 2.2-Animate task {task_id} → {status}: {data}")
            time.sleep(self.poll_interval)
        raise TimeoutError(f"Wan 2.2-Animate task {task_id} timed out")


def render_fight_shot(
    *,
    character_image_url: str,
    action_video_url: str,
    prompt: str = "",
    duration_seconds: int = 6,
    mock: bool | None = None,
) -> str:
    """Top-level helper used by ``orchestrator_v2._step4_render``.

    Falls back to ``action_video_url`` when mock mode is requested or no
    DashScope key is configured — preserves end-to-end pipeline progress
    in unit tests and on free-tier deployments.
    """
    if mock is None:
        mock = (
            os.environ.get("FORCE_MOCK_WAN_ANIMATE") == "1"
            or not os.environ.get("DASHSCOPE_API_KEY")
        )
    if mock:
        _log.info("wan_animate mock → reusing reference action video")
        return action_video_url
    client = WanAnimateClient()
    return client.render(
        WanAnimateRequest(
            character_image_url=character_image_url,
            action_video_url=action_video_url,
            prompt=prompt,
            duration_seconds=duration_seconds,
        )
    )


__all__ = [
    "WanAnimateClient",
    "WanAnimateRequest",
    "render_fight_shot",
    "WAN_ANIMATE_MODEL",
    "WAN_ANIMATE_SUBMIT",
]
