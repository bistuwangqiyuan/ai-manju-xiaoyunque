"""火山引擎「小云雀-短剧漫剧 Agent」专用客户端 (2026-05 新发布).

参考文档 (PDF 应放到 docs/volc-manju/, 我从中提取真实 req_key + 字段):
  - 产品介绍:     https://www.volcengine.com/docs/85621/2432754?lang=zh
  - 视频生成 fast: https://www.volcengine.com/docs/85621/2389853?lang=zh
  - 视频生成 720p: https://www.volcengine.com/docs/85621/2389854?lang=zh
  - 视频合成:     https://www.volcengine.com/docs/85621/2407085?lang=zh
  - 全流程示例:   https://www.volcengine.com/docs/85621/2459788?lang=zh

与上一代 ``pippit_iv2v_v20_cvtob_with_vinput`` ([`client.py`](client.py)) 的区别:

==============  ====================================  ======================================
能力            旧 IV2V                                短剧漫剧 Agent
==============  ====================================  ======================================
输入            参考图 + prompt                       完整剧本 .txt/.docx
单次时长上限    60s (需 chunk 拼接)                   一次出"分集成片" (每集 2-3 分钟)
角色一致性      要靠 prompt 块 + InfiniteYou 锚定     自动建"角色档案", 全剧本扫描一致
画风            prompt 描述                           显式选项: 2D / 3D / 真人写实
画幅            prompt 描述                           显式选项: 9:16 / 16:9
旁白            人工切 ASR + TTS                      自动改写内心独白 → 旁白
字幕            shell5 后期挂载                       Agent 自带
配音            MiniMax/豆包 TTS 后期合成             Agent 自带 (可选音色)
集成度          7 步管线手编排                        2 个 OpenAPI 调用 (submit + query)
==============  ====================================  ======================================

设计原则:

1. **PDF 未到** -> ``FORCE_MOCK_MANJU_AGENT=1`` (默认) 走 mock, 返回 fake mp4 url
2. **PDF 到** -> 替换 ``MANJU_REQ_KEY_*`` + ``MANJU_FIELDS`` 常量, 真调用
3. **双轨保留**: ``MANJU_AGENT_MODE`` 控制 orchestrator_v2 选哪条路, 旧 pippit 仍可用
4. **复用现有签名 + retry + storage**: 不重复造轮子

mock-mode 配置::

    FORCE_MOCK_MANJU_AGENT=1     # 默认 1; PDF 实装后改 0
    MANJU_AGENT_MODE=0/1         # orchestrator 路由开关
    MANJU_REQ_KEY=<official>     # 可注入, 优先级高于内置常量
"""
from __future__ import annotations

import enum
import json
import logging
import os
import time
import urllib.error
import urllib.request
import uuid
from dataclasses import dataclass, field
from typing import Any

from ..common.retry import retry
from ..common.storage import default_storage
from ..common.volc_credentials import (
    resolve_volc_access_key,
    volc_secret_key_candidates,
)
from ..common.volc_signer import sign_request


_log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Contract constants — locked once PDF parsed
# ---------------------------------------------------------------------------

# NOTE: 下面 3 个 req_key 是 PLACEHOLDER. PDF 实装时替换为真值.
# PDF 查找方法: PDF 内搜 "req_key" 或 "请求体"; submit 与 query 通常共用 req_key.
MANJU_REQ_KEY_SEEDANCE_FAST_720P_DEFAULT = "manju_agent_seedance_v20_fast_720p"
MANJU_REQ_KEY_SEEDANCE_720P_DEFAULT      = "manju_agent_seedance_v20_720p"
MANJU_REQ_KEY_SYNTHESIZE_DEFAULT         = "manju_agent_seedance_v20_synthesize"

# 字段映射 — PDF 解析后替换为真实 JSON 字段名 (key 是逻辑名, value 是 PDF 里写的字段)
# PDF 查找方法: 看 "请求参数" 表格的 "参数名" 列.
MANJU_FIELDS: dict[str, str] = {
    "script_text":      "script_content",   # 剧本正文 (str)
    "script_url":       "script_url",       # 剧本 URL 替代 (str, 若上传到 TOS)
    "style":            "style",            # 画风 (2d/3d/real)
    "ratio":            "ratio",            # 画幅 (16:9 / 9:16 / 4:3 / 3:4)
    "narration":        "narration_mode",   # 旁白 (auto/off)
    "episode_duration": "episode_duration", # 每集时长 (秒)
    "episode_count":    "episode_count",    # 集数
    "voice":            "voice",            # 音色 (str)
    "watermark":        "enable_watermark", # 水印 (bool)
    "task_id":          "task_id",          # 查询任务 ID (str)
}

# 官方 endpoint / 签名 region.  与 visual.volcengineapi.com 同 (PDF 应该确认)
MANJU_HOST = "visual.volcengineapi.com"
MANJU_REGION = "cn-north-1"
MANJU_SERVICE = "cv"
MANJU_VERSION = "2022-08-31"
MANJU_ACTION_SUBMIT = "CVSync2AsyncSubmitTask"
MANJU_ACTION_QUERY = "CVSync2AsyncGetResult"

# Enum 枚举值 — PDF 实装后用实际枚举更新
STYLE_VALUES = ("2d", "3d", "real")
RATIO_VALUES = ("16:9", "9:16", "4:3", "3:4")
NARRATION_VALUES = ("auto", "off")

MAX_SCRIPT_CHARS = 200_000          # 30 集 * 1500 字 + buffer; PDF 确认
MIN_EPISODE_DURATION_SEC = 30        # 每集最短 30 秒
MAX_EPISODE_DURATION_SEC = 180       # 每集 3 分钟上限 (PDF 确认)
MAX_EPISODE_COUNT = 100              # 一次任务最多 100 集

# Status 枚举 (同 IV2V; 漫剧 Agent 大概率沿用同一套)
STATUS_TERMINAL_DONE = "done"
STATUS_TERMINAL_NOT_FOUND = "not_found"
STATUS_TERMINAL_EXPIRED = "expired"
STATUS_TERMINAL_FAILED = "failed"
STATUS_RUNNING = {"processing", "in_queue", "generating", "rendering", "scripting"}

RETRYABLE_CODES = {50429, 50430, 50500, 50501, 50511}
AUDIT_FATAL_CODES = {50411, 50412, 50413, 50512, 50513, 50514}


# ---------------------------------------------------------------------------
# Mode + mock helpers
# ---------------------------------------------------------------------------

def is_mock_mode() -> bool:
    """Return True if manju agent is in mock mode (env / no creds)."""
    if os.environ.get("FORCE_MOCK_MANJU_AGENT", "").strip() in {"1", "true", "yes"}:
        return True
    # 没有 AK/SK 自动退回 mock
    if not resolve_volc_access_key():
        return True
    if not volc_secret_key_candidates():
        return True
    return False


def is_manju_agent_enabled() -> bool:
    """orchestrator_v2 选 manju agent 还是 pippit_iv2v_v20 (双轨)."""
    val = os.environ.get("MANJU_AGENT_MODE", "0").strip().lower()
    return val in {"1", "true", "yes", "on"}


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------

class ManjuAgentError(RuntimeError):
    pass


class ManjuAgentAuditError(ManjuAgentError):
    def __init__(self, code: int, message: str, request_id: str | None = None):
        super().__init__(f"[{code}] {message}")
        self.code = code
        self.request_id = request_id


class ManjuAgentRetryable(ManjuAgentError):
    def __init__(self, code: int, message: str):
        super().__init__(f"[{code}] {message}")
        self.code = code


class ManjuAgentTimeout(ManjuAgentError):
    pass


# ---------------------------------------------------------------------------
# Domain models
# ---------------------------------------------------------------------------

class Style(str, enum.Enum):
    TWO_D = "2d"
    THREE_D = "3d"
    REAL = "real"


class Ratio(str, enum.Enum):
    LANDSCAPE_WIDE = "16:9"
    PORTRAIT = "9:16"
    LANDSCAPE_4_3 = "4:3"
    PORTRAIT_3_4 = "3:4"


class NarrationMode(str, enum.Enum):
    AUTO = "auto"
    OFF = "off"


@dataclass
class ManjuSubmission:
    """High-level submission to ManjuAgent — flatten to PDF 字段 on send."""

    script_text: str = ""                 # 与 script_url 二选一
    script_url: str = ""                  # 剧本 URL (TOS / OSS 上传后)
    style: str = "real"                   # 画风
    ratio: str = "9:16"                   # 画幅
    narration: str = "auto"               # 旁白
    episode_duration_sec: int = 150       # 每集时长 (2.5 分钟)
    episode_count: int = 0                # 0 = 自动按剧本切分; >0 = 显式指定
    voice: str = ""                       # 音色 (留空走默认)
    enable_watermark: bool = False        # 商用关闭; PDF 实装时确认权限

    def validate(self) -> None:
        if not self.script_text and not self.script_url:
            raise ValueError("script_text or script_url required")
        if self.script_text and len(self.script_text) > MAX_SCRIPT_CHARS:
            raise ValueError(
                f"script_text {len(self.script_text)} > {MAX_SCRIPT_CHARS} chars; "
                "split into multiple submissions or upload as script_url"
            )
        if self.style not in STYLE_VALUES:
            raise ValueError(f"style={self.style!r} not in {STYLE_VALUES}")
        if self.ratio not in RATIO_VALUES:
            raise ValueError(f"ratio={self.ratio!r} not in {RATIO_VALUES}")
        if self.narration not in NARRATION_VALUES:
            raise ValueError(f"narration={self.narration!r} not in {NARRATION_VALUES}")
        if not (MIN_EPISODE_DURATION_SEC <= self.episode_duration_sec
                <= MAX_EPISODE_DURATION_SEC):
            raise ValueError(
                f"episode_duration_sec={self.episode_duration_sec} out of range "
                f"[{MIN_EPISODE_DURATION_SEC}, {MAX_EPISODE_DURATION_SEC}]"
            )
        if self.episode_count < 0 or self.episode_count > MAX_EPISODE_COUNT:
            raise ValueError(
                f"episode_count={self.episode_count} out of [0, {MAX_EPISODE_COUNT}]"
            )

    def to_payload(self, req_key: str) -> dict[str, Any]:
        self.validate()
        f = MANJU_FIELDS
        payload: dict[str, Any] = {"req_key": req_key}
        if self.script_text:
            payload[f["script_text"]] = self.script_text
        if self.script_url:
            payload[f["script_url"]] = self.script_url
        payload[f["style"]] = self.style
        payload[f["ratio"]] = self.ratio
        payload[f["narration"]] = self.narration
        payload[f["episode_duration"]] = self.episode_duration_sec
        if self.episode_count > 0:
            payload[f["episode_count"]] = self.episode_count
        if self.voice:
            payload[f["voice"]] = self.voice
        payload[f["watermark"]] = self.enable_watermark
        return payload


@dataclass
class ManjuEpisode:
    """An episode in the rendered output."""
    episode_no: int
    video_url: str              # 1h ~ 24h 有效 TTL; 必须立即转存
    archived_path: str = ""     # 转存到 TOS 后路径
    duration_seconds: float = 0.0
    subtitle_url: str = ""
    cover_url: str = ""
    metadata: dict = field(default_factory=dict)


@dataclass
class ManjuResult:
    task_id: str
    status: str
    episodes: list[ManjuEpisode] = field(default_factory=list)
    overall_duration_seconds: float = 0.0
    raw_response: dict = field(default_factory=dict)
    aigc_meta_tagged: bool = False


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------

class ManjuAgentClient:
    """火山引擎「小云雀-短剧漫剧 Agent」客户端.

    用法::

        client = ManjuAgentClient()
        task_id = client.submit_script(novel_text="...", style="real", ratio="9:16")
        result = client.wait_for_completion(task_id, ep_id="ep001")
        for ep in result.episodes:
            print(ep.episode_no, ep.archived_path, ep.duration_seconds)
    """

    api_action_submit = MANJU_ACTION_SUBMIT
    api_action_query = MANJU_ACTION_QUERY
    api_version = MANJU_VERSION

    def __init__(
        self,
        access_key: str | None = None,
        secret_key: str | None = None,
        *,
        req_key: str | None = None,
        storage = None,
        poll_interval_seconds: float = 30.0,
        timeout_seconds: float = 4 * 3600.0,    # 30 集大约 1-2h, 4h 充裕
        mock: bool | None = None,
    ):
        # PDF 实装后, MANJU_REQ_KEY 可被 env 覆盖
        self.req_key = (
            req_key
            or os.environ.get("MANJU_REQ_KEY", "").strip()
            or MANJU_REQ_KEY_SEEDANCE_FAST_720P_DEFAULT
        )
        # mock 模式: 显式 mock 参数 > FORCE_MOCK env > 无凭据自动 mock
        self.mock = mock if mock is not None else is_mock_mode()

        if not self.mock:
            self.access_key = resolve_volc_access_key(access_key)
            self._secret_candidates = volc_secret_key_candidates(secret_key)
            if not self.access_key or not self._secret_candidates:
                _log.warning(
                    "ManjuAgentClient: no VOLC_ACCESS_KEY/SECRET_KEY; falling back to mock"
                )
                self.mock = True
            else:
                self.secret_key = self._secret_candidates[0]
        if self.mock:
            self.access_key = ""
            self.secret_key = ""
            self._secret_candidates = [""]

        self.storage = storage or default_storage()
        self.poll_interval = float(poll_interval_seconds)
        self.timeout = float(timeout_seconds)

    # ---------------- public api ----------------

    def submit_script(
        self,
        novel_text: str = "",
        *,
        script_url: str = "",
        style: str = "real",
        ratio: str = "9:16",
        narration: str = "auto",
        episode_duration_sec: int = 150,
        episode_count: int = 0,
        voice: str = "",
        enable_watermark: bool = False,
    ) -> str:
        """提交一份剧本, 返回 task_id."""

        submission = ManjuSubmission(
            script_text=novel_text,
            script_url=script_url,
            style=style, ratio=ratio, narration=narration,
            episode_duration_sec=episode_duration_sec,
            episode_count=episode_count,
            voice=voice,
            enable_watermark=enable_watermark,
        )
        submission.validate()

        if self.mock:
            mock_id = f"mock-manju-{uuid.uuid4().hex[:12]}"
            _log.info("[manju-mock] submit -> %s (style=%s ratio=%s)",
                      mock_id, style, ratio)
            return mock_id

        payload = submission.to_payload(self.req_key)
        last_err: ManjuAgentError | None = None
        for sk in self._secret_candidates:
            self.secret_key = sk
            try:
                resp = self._http_post(self.api_action_submit, payload)
                self._raise_for_code(resp)
                task_id = (resp.get("data") or {}).get(MANJU_FIELDS["task_id"])
                if not task_id:
                    raise ManjuAgentError(f"missing task_id in response: {resp}")
                return str(task_id)
            except ManjuAgentError as exc:
                last_err = exc
                if "401" in str(exc):
                    continue
                raise
        raise last_err or ManjuAgentError("submit failed: exhausted SK candidates")

    def query_task(self, task_id: str) -> dict:
        """查询任务状态."""
        if self.mock:
            return _mock_query_response(task_id)
        payload = {"req_key": self.req_key, MANJU_FIELDS["task_id"]: task_id}
        resp = self._http_post(self.api_action_query, payload)
        self._raise_for_code(resp)
        return resp.get("data") or {}

    def wait_for_completion(self, task_id: str, *, ep_id: str = "ep") -> ManjuResult:
        """轮询 task_id 直到 done / failed / 超时."""

        deadline = time.monotonic() + self.timeout
        last_status = ""
        while time.monotonic() < deadline:
            data = self.query_task(task_id)
            status = (data.get("status") or "").lower()
            if status != last_status:
                _log.info("[%s] task=%s status=%s", ep_id, task_id, status)
                last_status = status

            if status == STATUS_TERMINAL_DONE:
                return self._archive_result(task_id, data, ep_id=ep_id)
            if status == STATUS_TERMINAL_NOT_FOUND:
                raise ManjuAgentError(f"task {task_id} not_found")
            if status == STATUS_TERMINAL_EXPIRED:
                raise ManjuAgentError(f"task {task_id} expired; resubmit")
            if status == STATUS_TERMINAL_FAILED:
                raise ManjuAgentError(
                    f"task {task_id} failed: {data.get('message') or data}"
                )
            if status and status not in STATUS_RUNNING:
                _log.warning("[%s] unknown status %r; continuing to poll", ep_id, status)
            time.sleep(self.poll_interval)
        raise ManjuAgentTimeout(f"task {task_id} did not complete in {self.timeout}s")

    def render_script(
        self,
        novel_text: str,
        *,
        ep_id: str = "ep",
        **submission_kwargs,
    ) -> ManjuResult:
        """便捷封装: submit -> wait -> archive 一次性."""
        task_id = self.submit_script(novel_text, **submission_kwargs)
        return self.wait_for_completion(task_id, ep_id=ep_id)

    # ---------------- internals ----------------

    @retry(
        exceptions=(urllib.error.URLError, urllib.error.HTTPError, TimeoutError, ManjuAgentRetryable),
        attempts=12, base_delay=4.0, max_delay=90.0,
    )
    def _http_post(self, action: str, payload: dict) -> dict:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        signed = sign_request(
            access_key=self.access_key, secret_key=self.secret_key,
            action=action, version=self.api_version, body=body,
        )
        req = urllib.request.Request(
            signed.url, data=signed.body, headers=signed.headers, method=signed.method,
        )
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                raw = resp.read()
        except urllib.error.HTTPError as e:
            try:
                detail = json.loads(e.read())
            except Exception:  # noqa: BLE001
                raise
            code = int(detail.get("code", e.code))
            msg = detail.get("message", str(e))
            req_id = detail.get("request_id")
            if code in RETRYABLE_CODES:
                raise ManjuAgentRetryable(code, msg) from None
            if code in AUDIT_FATAL_CODES:
                raise ManjuAgentAuditError(code, msg, request_id=req_id) from None
            raise ManjuAgentError(f"[{code}] {msg} request_id={req_id}") from None
        try:
            return json.loads(raw)
        except json.JSONDecodeError as e:
            raise ManjuAgentError(f"non-JSON response: {raw[:512]!r}") from e

    @staticmethod
    def _raise_for_code(response: dict) -> None:
        code = int(response.get("code", -1))
        if code == 10000 or code == 0:
            return
        msg = response.get("message", "")
        req_id = response.get("request_id")
        if code in AUDIT_FATAL_CODES:
            raise ManjuAgentAuditError(code, msg, request_id=req_id)
        if code in RETRYABLE_CODES:
            raise ManjuAgentRetryable(code, msg)
        raise ManjuAgentError(f"[{code}] {msg} request_id={req_id}")

    def _archive_result(self, task_id: str, data: dict, *, ep_id: str) -> ManjuResult:
        """把 Agent 返回的 episodes 全部转存到 TOS, 防 URL TTL 过期."""

        # 字段名 PDF 实装时确认; 这里按合理的命名探测兼容多版本
        eps_raw = (
            data.get("episodes")
            or data.get("output_episodes")
            or data.get("result_episodes")
            or []
        )
        episodes: list[ManjuEpisode] = []
        for idx, ep in enumerate(eps_raw, start=1):
            no = int(ep.get("episode_no") or ep.get("index") or idx)
            url = (ep.get("video_url") or ep.get("url") or ep.get("output_url") or "")
            if not url:
                _log.warning("episode #%d has no video_url; skip", no)
                continue
            archived = ""
            try:
                key = f"manju/{ep_id}/{task_id}/episode_{no:03d}.mp4"
                obj = self.storage.archive_url(key, url)
                archived = getattr(obj, "path", "") or ""
            except Exception as e:  # noqa: BLE001
                _log.warning("archive episode #%d failed: %s", no, e)
            episodes.append(ManjuEpisode(
                episode_no=no,
                video_url=url,
                archived_path=archived,
                duration_seconds=float(ep.get("duration") or ep.get("duration_seconds") or 0),
                subtitle_url=(ep.get("subtitle_url") or ep.get("srt_url") or ""),
                cover_url=(ep.get("cover_url") or ep.get("thumbnail_url") or ""),
                metadata={k: v for k, v in ep.items()
                          if k not in {"video_url", "url", "duration"}},
            ))

        total_duration = sum(ep.duration_seconds for ep in episodes)
        return ManjuResult(
            task_id=task_id,
            status=data.get("status", STATUS_TERMINAL_DONE),
            episodes=episodes,
            overall_duration_seconds=total_duration,
            raw_response=data,
            aigc_meta_tagged=bool(data.get("aigc_meta_tagged", False)),
        )


# ---------------------------------------------------------------------------
# Mock data — for tests and dev when PDF not yet integrated
# ---------------------------------------------------------------------------

def _mock_query_response(task_id: str) -> dict:
    """Return deterministic mock that simulates a fully-done task."""

    return {
        "status": STATUS_TERMINAL_DONE,
        "task_id": task_id,
        "episodes": [
            {
                "episode_no": 1,
                "video_url": f"https://mock.tos.local/{task_id}/ep001.mp4",
                "duration": 150.0,
                "subtitle_url": f"https://mock.tos.local/{task_id}/ep001.srt",
                "cover_url": f"https://mock.tos.local/{task_id}/ep001.jpg",
            },
            {
                "episode_no": 2,
                "video_url": f"https://mock.tos.local/{task_id}/ep002.mp4",
                "duration": 155.0,
                "subtitle_url": f"https://mock.tos.local/{task_id}/ep002.srt",
                "cover_url": f"https://mock.tos.local/{task_id}/ep002.jpg",
            },
            {
                "episode_no": 3,
                "video_url": f"https://mock.tos.local/{task_id}/ep003.mp4",
                "duration": 148.0,
            },
        ],
        "aigc_meta_tagged": False,
    }


__all__ = [
    "ManjuAgentClient",
    "ManjuSubmission",
    "ManjuResult",
    "ManjuEpisode",
    "ManjuAgentError",
    "ManjuAgentAuditError",
    "ManjuAgentRetryable",
    "ManjuAgentTimeout",
    "Style", "Ratio", "NarrationMode",
    "is_mock_mode", "is_manju_agent_enabled",
    "MANJU_REQ_KEY_SEEDANCE_FAST_720P_DEFAULT",
    "MANJU_REQ_KEY_SEEDANCE_720P_DEFAULT",
    "MANJU_FIELDS",
    "STYLE_VALUES", "RATIO_VALUES", "NARRATION_VALUES",
]
