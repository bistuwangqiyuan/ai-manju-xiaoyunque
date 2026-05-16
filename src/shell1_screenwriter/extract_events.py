"""DeepSeek V4-Pro event extraction (1M context, 1/3 price of Opus)."""
from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from typing import Sequence

import urllib.request


_log = logging.getLogger(__name__)


_SYSTEM_PROMPT = """你是金牌网文编辑兼古典文学专家，正在为 AI 漫剧改编《聊斋志异·聂小倩》。

任务：把整部原著按主线压缩成事件列表 JSON，每条事件 1-3 句话，含「事件名称 / 核心冲突 / 钩子潜力（★1-★5）/ 视觉关键词」。
要求：
1. 严格忠于原著事件骨架，不要二次创作。
2. 过滤掉一切"水文"（重复描写、过场陈述）。
3. 输出 JSON 数组，每条包含 {id, name, summary, hook_score, visual_keywords, act}。
4. 章节标识 act ∈ {"第一幕 投宿兰若", "第二幕 揭妖救骨", "第三幕 归家收妖"}。
5. 钩子潜力评分：能成为漫剧 cliffhanger 的标 ★5。"""


@dataclass
class Event:
    id: str
    name: str
    summary: str
    hook_score: int
    visual_keywords: list[str]
    act: str


class EventExtractor:
    def __init__(self,
                 api_key: str | None = None,
                 base_url: str = "https://api.deepseek.com/v1",
                 model: str = "deepseek-v4-pro"):
        self.api_key = api_key or os.environ.get("DEEPSEEK_API_KEY", "")
        if not self.api_key:
            raise RuntimeError("Missing DEEPSEEK_API_KEY")
        self.base_url = base_url.rstrip("/")
        self.model = model

    def extract(self, novel_text: str) -> Sequence[Event]:
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": novel_text},
            ],
            "temperature": 0.3,
            "response_format": {"type": "json_object"},
            "max_tokens": 16000,
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
        items = parsed.get("events") if isinstance(parsed, dict) else parsed
        events = [
            Event(
                id=str(item["id"]),
                name=item["name"],
                summary=item["summary"],
                hook_score=int(item["hook_score"]),
                visual_keywords=list(item.get("visual_keywords", [])),
                act=item["act"],
            )
            for item in items
        ]
        _log.info("extracted %d events", len(events))
        return events
