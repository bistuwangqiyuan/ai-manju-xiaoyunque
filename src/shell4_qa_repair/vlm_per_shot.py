"""豆包 Seed 1.6 Vision — per-shot semantic check."""
from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from typing import Iterable

import urllib.request


_log = logging.getLogger(__name__)


_CHECK_ITEMS = (
    "主角脸是否与参考图一致（参考 canonical_image）",
    "是否有越轴 / 180 度规则违反",
    "肢体是否完整（手指数、关节方向）",
    "嘴型是否对齐音频",
    "画面是否出现 AI 渲染的文字（应禁止）",
    "服装层次 / 配饰是否一致",
    "三大锁定符号：眉间朱砂痣 / 左肩黑藤 / 革囊苍白手 是否在位",
)

_SYSTEM_PROMPT = """你是漫剧逐镜质检员。
对每一个输入视频（或视频抽帧）按下列检查项逐条评估：
{items}

输出 JSON：
{{
  "shot_id": int,
  "passed": bool,
  "issues": [
    {{"category": "face_drift|motion_axis|limb|lipsync|ai_text|costume_drift|signature_missing|other",
      "severity": "low|medium|high",
      "evidence": "..."
    }}
  ],
  "summary": "..."
}}
"""


@dataclass
class ShotIssue:
    category: str
    severity: str
    evidence: str


@dataclass
class ShotReport:
    shot_id: int
    passed: bool
    issues: list[ShotIssue] = field(default_factory=list)
    summary: str = ""


class VlmPerShotChecker:
    def __init__(self,
                 api_key: str | None = None,
                 base_url: str = "https://ark.cn-beijing.volces.com/api/v3",
                 model: str = "doubao-seed-1-6-vision-250815"):
        self.api_key = api_key or os.environ.get("DOUBAO_API_KEY") or os.environ.get("VOLC_ARK_API_KEY", "")
        if not self.api_key:
            raise RuntimeError("Missing DOUBAO_API_KEY / VOLC_ARK_API_KEY")
        self.base_url = base_url.rstrip("/")
        self.model = model

    def check(self, shot_id: int, video_url: str, canonical_image_url: str) -> ShotReport:
        sys_prompt = _SYSTEM_PROMPT.format(items="\n".join(f"- {item}" for item in _CHECK_ITEMS))
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": sys_prompt},
                {"role": "user", "content": [
                    {"type": "video_url", "video_url": {"url": video_url}},
                    {"type": "image_url", "image_url": {"url": canonical_image_url}},
                    {"type": "text", "text": f"shot_id={shot_id}，按 JSON 输出。"},
                ]},
            ],
            "temperature": 0.0,
            "response_format": {"type": "json_object"},
            "max_tokens": 2000,
        }
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(
            f"{self.base_url}/chat/completions",
            data=body,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=180) as resp:
            raw = json.loads(resp.read())
        content = raw["choices"][0]["message"]["content"]
        parsed = json.loads(content)
        return ShotReport(
            shot_id=int(parsed.get("shot_id", shot_id)),
            passed=bool(parsed.get("passed", False)),
            issues=[ShotIssue(**iss) for iss in parsed.get("issues", [])],
            summary=parsed.get("summary", ""),
        )

    def check_batch(self, shots: Iterable[tuple[int, str, str]]) -> list[ShotReport]:
        return [self.check(sid, url, canon) for sid, url, canon in shots]
