"""Claude Opus 4.7 master screenwriter — 10 episodes, Chinese 古风文采 #1."""
from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from typing import Sequence

import urllib.request

from .extract_events import Event


_log = logging.getLogger(__name__)


# 4-段式节拍（钩子-铺垫-高潮-反转-悬念）——content_report.md §A3.0
_NODE_STRUCTURE = (
    "[钩子 0–3s] 第一冲击点（视觉/悬念/冲突）\n"
    "[铺垫 3–25s] 事件背景 + 角色行为线\n"
    "[高潮 25–55s] 冲突顶点 / 第一反转\n"
    "[反转 55–70s] 第二反转 / 情绪释放\n"
    "[悬念 70–90s] cliffhanger 引向下一集"
)

_SYSTEM_PROMPT = f"""你是金牌漫剧编剧，正在改编《聊斋志异·聂小倩》成 10 集竖屏 9:16 古风 3D 国漫短剧。

# 项目锚定
- 美学：87 版徐克"仙气>阴森"小倩 + 2025 复古志怪"妖怪复杂动机"
- 风格：60% 白蛇缘起 + 30% 狐妖月红 + 10% 雾山五行（仅打斗段）
- 节拍（每集严格执行）：
{_NODE_STRUCTURE}
- 时长：标准集 75-80s，高光集 90s（第 4 / 8 / 9 集）
- 镜头规则：1.5-3s/镜，约 25-35 镜/集，紧张戏可 2.3-3 切换/秒
- 信息密度：每秒 8-12 字台词

# 三大原创视觉锁定符号（必须每集出现）
- 聂小倩眉间一点朱砂痣（CMYK 锁定）
- 聂小倩左肩黑色藤纹束缚标记（前 4 集隐约 → 第 8 集暴起 → 第 9 集消散）
- 革囊中伸出的苍白剑客之手（第 5 集埋伏 → 第 9 集回收）

# 版权红线（必须回避 87 版徐克独创元素）
- 长舌树妖姥姥外观 → 替换为「6 条黑藤根 + 白杨虚影」
- 浴桶之吻 → 替换为「月下溪水浣纱场景」
- 黑山老妖宇宙观 → 替换为「革囊中前剑客之魂」
- 投胎转世结局 → 用原著"鬼气消散真的活过来"

# 平台合规
- 抖音/快手红线：禁血腥 / 禁性暗示 / 禁宣扬迷信
- 足心锥孔 → 虚化为「白练入足心」
- 鬼骨化金 → 改为光效转化
- 小倩勾引 → 改为月下相邀

# 输出 JSON Schema
每集输出：
{{
  "episode_id": "ep01",
  "title": "荒寺月夜",
  "duration_seconds": 80,
  "premium_tier": "standard|veo_3_1_standard|sora_2_pro",
  "hook_3s": "...",
  "synopsis": "...",
  "twist_1": "...",
  "twist_2": "...",
  "cliffhanger": "...",
  "characters_in_episode": ["ningcaichen", "nie_xiaoqian", ...],
  "scenes_in_episode": ["lanruosi", ...],
  "signatures_check": {{
    "zhusha_visible": true,
    "black_vine_visibility": 0.0,
    "white_hand_appears": false
  }},
  "shots": [
    {{
      "shot_id": 1,
      "type": "close-up|medium|wide|aerial",
      "duration_seconds": 3.0,
      "subject_chars": ["nie_xiaoqian"],
      "scene": "lanruosi",
      "camera_motion": "slow push-in",
      "action_desc": "...",
      "dialogue": "" 或 "小倩低吟...",
      "voiceover": "三百年前的剑仙...",
      "audio_cues": ["蝙蝠惊飞", "夜风"],
      "key_visual": "月下白影，铜镜无人"
    }}
  ],
  "music_emotion_arc": "neutral->mystery->awe->tension->lingering",
  "subtitle_lines": [
    {{"start_s": 0.0, "end_s": 3.0, "text": "..."}}
  ]
}}

输出严格 JSON，不带任何 markdown 包装。"""


@dataclass
class Episode:
    raw: dict

    @property
    def episode_id(self) -> str:
        return self.raw["episode_id"]

    @property
    def title(self) -> str:
        return self.raw["title"]


class EpisodeWriter:
    """Anthropic Claude episode writer.

    认证模式（自动选择）：
      - 代理: ANTHROPIC_BASE_URL + ANTHROPIC_AUTH_TOKEN → Bearer auth + browser UA
      - 官方: ANTHROPIC_API_KEY → x-api-key + 默认 endpoint
    优先使用代理配置（如设置了 BASE_URL）。所有请求都注入 browser User-Agent 以
    绕过代理服务前置的 Cloudflare WAF（实测从 403 Blocked → 200 OK）。
    """

    def __init__(self,
                 api_key: str | None = None,
                 base_url: str | None = None,
                 model: str = "claude-opus-4-7-20260413",
                 max_tokens: int = 8000):
        env_base = os.environ.get("ANTHROPIC_BASE_URL", "").strip()
        # base_url 优先级：构造参数 > 环境变量 > 默认官方
        # 注意：anthropic SDK 默认追加 /v1，但用 urllib 直连需要手动追加
        resolved_base = (base_url or env_base or "https://api.anthropic.com").rstrip("/")
        # 兼容代理 URL 是否带 /v1 后缀
        if not resolved_base.endswith("/v1"):
            resolved_base = resolved_base + "/v1"
        self.base_url = resolved_base

        # 认证：Bearer token (代理) 优先 → x-api-key (官方)
        self.auth_token = os.environ.get("ANTHROPIC_AUTH_TOKEN", "").strip()
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY", "").strip()
        if not self.auth_token and not self.api_key:
            raise RuntimeError(
                "Missing Anthropic credentials — set either ANTHROPIC_AUTH_TOKEN "
                "(for proxy) or ANTHROPIC_API_KEY (for official endpoint)"
            )

        # 模型支持 env 覆盖
        self.model = os.environ.get("ANTHROPIC_MODEL", "").strip() or model
        self.max_tokens = max_tokens

    def _build_headers(self) -> dict:
        headers = {
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
            # ★ 代理服务通常套 Cloudflare WAF，会拦默认 Python urllib UA。注入
            # browser-like UA 是绕过此类拦截的必要措施。
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        }
        if self.auth_token:
            headers["Authorization"] = f"Bearer {self.auth_token}"
        else:
            headers["x-api-key"] = self.api_key
        return headers

    def write_all(self, events: Sequence[Event], outline_md: str) -> list[Episode]:
        user_msg = (
            "# 10 集大纲（必须严格遵循）\n\n"
            f"{outline_md}\n\n"
            "# 事件列表（来自原著）\n\n"
            + json.dumps([e.__dict__ for e in events], ensure_ascii=False, indent=2)
            + "\n\n# 任务\n输出 10 集完整 JSON 数组（episodes 字段），严格按 schema。"
        )
        payload = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "system": _SYSTEM_PROMPT,
            "messages": [{"role": "user", "content": user_msg}],
            "temperature": 0.7,
        }
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(
            f"{self.base_url}/messages",
            data=body,
            headers=self._build_headers(),
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=300) as resp:
            raw = json.loads(resp.read())
        text = "".join(block.get("text", "") for block in raw.get("content", []))
        parsed = json.loads(text)
        items = parsed.get("episodes") if isinstance(parsed, dict) else parsed
        return [Episode(raw=item) for item in items]
