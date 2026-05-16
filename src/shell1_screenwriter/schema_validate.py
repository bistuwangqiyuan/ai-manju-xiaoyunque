"""Gemini 2.5 Pro — strict JSON schema validation of episode plans."""
from __future__ import annotations

import json
import logging
import os
from typing import Iterable

import urllib.request

from .write_episodes import Episode


_log = logging.getLogger(__name__)


# Strict JSON schema for episode plan (subset of Opus output worth validating)
EPISODE_JSON_SCHEMA = {
    "type": "object",
    "properties": {
        "episodes": {
            "type": "array",
            "minItems": 10,
            "maxItems": 12,
            "items": {
                "type": "object",
                "required": [
                    "episode_id", "title", "duration_seconds", "premium_tier",
                    "hook_3s", "synopsis", "twist_1", "twist_2", "cliffhanger",
                    "characters_in_episode", "scenes_in_episode",
                    "signatures_check", "shots",
                ],
                "properties": {
                    "episode_id": {"type": "string", "pattern": "^ep[0-9]{2}$"},
                    "title": {"type": "string", "minLength": 2, "maxLength": 16},
                    "duration_seconds": {"type": "integer", "minimum": 60, "maximum": 120},
                    "premium_tier": {
                        "type": "string",
                        "enum": ["standard", "veo_3_1_standard", "sora_2_pro"],
                    },
                    "hook_3s": {"type": "string"},
                    "synopsis": {"type": "string"},
                    "twist_1": {"type": "string"},
                    "twist_2": {"type": "string"},
                    "cliffhanger": {"type": "string"},
                    "characters_in_episode": {
                        "type": "array",
                        "minItems": 1,
                        "items": {"type": "string"},
                    },
                    "scenes_in_episode": {
                        "type": "array",
                        "minItems": 1,
                        "items": {"type": "string"},
                    },
                    "signatures_check": {
                        "type": "object",
                        "required": ["zhusha_visible", "black_vine_visibility", "white_hand_appears"],
                        "properties": {
                            "zhusha_visible": {"type": "boolean"},
                            "black_vine_visibility": {
                                "type": "number",
                                "minimum": 0.0,
                                "maximum": 1.0,
                            },
                            "white_hand_appears": {"type": "boolean"},
                        },
                    },
                    "shots": {
                        "type": "array",
                        "minItems": 8,
                        "maxItems": 50,
                        "items": {
                            "type": "object",
                            "required": [
                                "shot_id", "type", "duration_seconds", "scene",
                                "camera_motion", "action_desc", "key_visual",
                            ],
                        },
                    },
                },
            },
        },
    },
    "required": ["episodes"],
}


_SYSTEM_PROMPT = (
    "你是 JSON schema 严格校验器。对输入数组逐项按 schema 校验。"
    "如发现违反 schema 的字段，自动修复后输出符合 schema 的完整 JSON；"
    "禁止编造内容，仅做格式 / 范围修复。"
)


class SchemaValidator:
    def __init__(self,
                 api_key: str | None = None,
                 base_url: str = "https://generativelanguage.googleapis.com/v1beta",
                 model: str = "gemini-2.5-pro"):
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY", "")
        if not self.api_key:
            raise RuntimeError("Missing GEMINI_API_KEY")
        self.base_url = base_url.rstrip("/")
        self.model = model

    def validate_and_repair(self, episodes: Iterable[Episode]) -> list[Episode]:
        raw_list = [e.raw for e in episodes]
        request_body = {
            "contents": [{
                "role": "user",
                "parts": [
                    {"text": _SYSTEM_PROMPT},
                    {"text": json.dumps({"episodes": raw_list}, ensure_ascii=False)},
                ],
            }],
            "generationConfig": {
                "responseMimeType": "application/json",
                "responseSchema": EPISODE_JSON_SCHEMA,
                "temperature": 0.0,
                "maxOutputTokens": 32000,
            },
        }
        url = f"{self.base_url}/models/{self.model}:generateContent?key={self.api_key}"
        body = json.dumps(request_body, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(
            url, data=body, headers={"Content-Type": "application/json"}, method="POST",
        )
        with urllib.request.urlopen(req, timeout=300) as resp:
            payload = json.loads(resp.read())
        text = payload["candidates"][0]["content"]["parts"][0]["text"]
        parsed = json.loads(text)
        return [Episode(raw=item) for item in parsed["episodes"]]
