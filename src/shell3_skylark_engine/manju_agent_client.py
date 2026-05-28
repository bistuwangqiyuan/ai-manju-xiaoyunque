"""火山引擎「小云雀-短剧漫剧 Agent」专用客户端 (v9, 2026-05).

官方接口契约 (docs.volcengine.com /85621/):

  - 产品介绍:        /2432754  → docs/volc-manju/01_intro.md
  - 全流程示例:      /2459788
  - 剧本解析接口:    /2389851  → docs/volc-manju/02_script_parse.md
  - 图片生成接口:    /2389852  → docs/volc-manju/03_image_gen.md
  - 视频生成 fast:   /2389853  → docs/volc-manju/04_video_gen.md
  - 视频合成 fast:   /2407085  → docs/volc-manju/05_video_compose.md

一次完整调用 = 4 个子任务串行 (每个子任务都是 submit + poll):

  1. 剧本解析  (~4 min)  → 拿到 assets_id, thread_id, [EpisodeID,...]
  2. 图片生成  (~10 min) → 全剧角色/场景图就绪 (后续视频生成依赖)
  3. 视频生成  (~7 min × 集数, 可并发) → 各分镜视频 URL
  4. 视频合成  (~1 min × 集数, 不计费) → final_video_url + final_video_cover_url

所有 4 个子任务都用同一对 OpenAPI:

  POST https://visual.volcengineapi.com/?Action=CVSync2AsyncSubmitTask&Version=2022-08-31
  POST https://visual.volcengineapi.com/?Action=CVSync2AsyncGetResult&Version=2022-08-31

区别仅在 body 的 ``req_key`` 字段, 详见下方 ``MANJU_REQ_KEY_*`` 常量.

签名: V4-HMAC-SHA256, Service=``cv``, Region=``cn-north-1``.
"""
from __future__ import annotations

import enum
import io
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
# Contract constants — locked to official docs (2026-05)
# ---------------------------------------------------------------------------

# 4 个子任务的 req_key (官方实测固定值)
MANJU_REQ_KEY_SCRIPT_ANALYSIS  = "pippit_shortplay_cvtob_script_analysis"
MANJU_REQ_KEY_MATERIAL_DESIGN  = "pippit_shortplay_cvtob_material_design"
MANJU_REQ_KEY_VIDEO_GEN_FAST   = "pippit_shortplay_cvtob_video_generate_fast720p"
MANJU_REQ_KEY_VIDEO_COMPOSE    = "pippit_shortplay_cvtob_video_compose_fast720p"

# 标准 720p 模型 (备选, 通常画质略高但更慢)
MANJU_REQ_KEY_VIDEO_GEN_STD    = "pippit_shortplay_cvtob_video_generate_720p"
MANJU_REQ_KEY_VIDEO_COMPOSE_STD = "pippit_shortplay_cvtob_video_compose_720p"

# Backward-compat aliases (旧代码/测试用,指向 fast 720p)
MANJU_REQ_KEY_SEEDANCE_FAST_720P_DEFAULT = MANJU_REQ_KEY_VIDEO_GEN_FAST
MANJU_REQ_KEY_SEEDANCE_720P_DEFAULT      = MANJU_REQ_KEY_VIDEO_GEN_STD
MANJU_REQ_KEY_SYNTHESIZE_DEFAULT         = MANJU_REQ_KEY_VIDEO_COMPOSE

# OpenAPI endpoint
MANJU_HOST        = "visual.volcengineapi.com"
MANJU_REGION      = "cn-north-1"
MANJU_SERVICE     = "cv"
MANJU_VERSION     = "2022-08-31"
MANJU_ACTION_SUBMIT = "CVSync2AsyncSubmitTask"
MANJU_ACTION_QUERY  = "CVSync2AsyncGetResult"

# 字段映射 (logical name → wire field name).
#   - 上游接口实际字段是固定的, 这层主要保留 backward-compat 给现有测试用.
#   - to_payload 直接写官方字段名(req_key/visual_style/...)
MANJU_FIELDS: dict[str, str] = {
    "script_text":      "script_content",   # 内部上传后用 file_url; 这里仅 dev/test
    "script_url":       "file_url",         # 官方字段
    "style":            "visual_style",     # 官方字段
    "ratio":            "video_ratio",      # 官方字段
    "narration":        "narration_mode",   # 内部字段; 漫剧 Agent 自带旁白生成
    "episode_duration": "episode_duration", # 内部字段; Agent 端按剧本切分
    "episode_count":    "episode_count",    # 内部字段; Agent 端按剧本自动决定
    "voice":            "voice",            # 内部字段; Agent 端从角色档案选音色
    "watermark":        "enable_watermark", # 内部字段
    "task_id":          "task_id",
    "file_name":        "file_name",        # 官方字段
    "file_type":        "file_type",        # 官方字段
    "file_url":         "file_url",         # 官方字段
    "visual_style":     "visual_style",     # 官方字段
    "video_ratio":      "video_ratio",      # 官方字段
    "assets_id":        "assets_id",        # 官方字段
    "thread_id":        "thread_id",        # 官方字段
    "episode_id":       "episode_id",       # 官方字段
    "run_id":           "run_id",           # 官方字段
}

# 推荐的 visual_style 字符串 (官方建议值)
RECOMMENDED_VISUAL_STYLES = (
    "2D, 国风, 平涂",
    "3D, CG动画, 写实都市",
    "真人写实, 电影风格, 冷色调",
    "2D, 赛璐璐, 半厚涂",
    "真人写实, 电视风格, 高清画质",
)

# 高层 style 关键字 → 官方 visual_style 字符串
STYLE_TO_VISUAL_STYLE: dict[str, str] = {
    "2d":   "2D, 赛璐璐, 半厚涂",
    "3d":   "3D, CG动画, 写实都市",
    "real": "真人写实, 电视风格, 高清画质",
}

# Enum 列表 (供测试 + 校验)
STYLE_VALUES     = ("2d", "3d", "real")
RATIO_VALUES     = ("16:9", "9:16", "4:3", "3:4")  # API 实际接受 16:9/9:16; 4:3/3:4 自动回退
NARRATION_VALUES = ("auto", "off")
FILE_TYPE_VALUES = ("txt", "docx")

MAX_SCRIPT_CHARS         = 100_000   # 官方上限 10 万字
MIN_EPISODE_DURATION_SEC = 30
MAX_EPISODE_DURATION_SEC = 180
MAX_EPISODE_COUNT        = 100

# Task 外层 status (官方枚举)
STATUS_TERMINAL_DONE       = "done"
STATUS_TERMINAL_NOT_FOUND  = "not_found"
STATUS_TERMINAL_EXPIRED    = "expired"
STATUS_TERMINAL_FAILED     = "failed"
STATUS_RUNNING = {"processing", "in_queue", "generating", "rendering", "scripting"}

# 内部进度状态 (script_overview_analysis.Status / Shots[].Status)
STAGE_STATUS_DONE       = 3
STAGE_STATUS_FAILED     = 4
STAGE_STATUS_AUDIT_FAIL = 5

# 业务错误码
RETRYABLE_CODES   = {50429, 50430, 50500, 50501, 50511}
AUDIT_FATAL_CODES = {50411, 50412, 50413, 50512, 50513, 50514}


# ---------------------------------------------------------------------------
# Mode + mock helpers
# ---------------------------------------------------------------------------

def is_mock_mode() -> bool:
    """是否走 mock (env 强制 / 无凭据自动回退)."""
    if os.environ.get("FORCE_MOCK_MANJU_AGENT", "").strip() in {"1", "true", "yes"}:
        return True
    if not resolve_volc_access_key():
        return True
    if not volc_secret_key_candidates():
        return True
    return False


def is_manju_agent_enabled() -> bool:
    """orchestrator_v2 路由开关."""
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
# Enums + domain models
# ---------------------------------------------------------------------------

class Style(str, enum.Enum):
    TWO_D = "2d"
    THREE_D = "3d"
    REAL = "real"


class Ratio(str, enum.Enum):
    LANDSCAPE_WIDE = "16:9"
    PORTRAIT       = "9:16"
    LANDSCAPE_4_3  = "4:3"
    PORTRAIT_3_4   = "3:4"


class NarrationMode(str, enum.Enum):
    AUTO = "auto"
    OFF  = "off"


def style_to_visual_style(style: str) -> str:
    """高层 style ('2d'/'3d'/'real') → 官方 visual_style 推荐字符串.

    若 ``style`` 已经看起来像官方字符串 (含 ',' 或 中文逗号),则原样返回,
    便于外部直接传入 ``"2D, 国风, 平涂"`` 之类的精细化风格描述.
    """
    s = (style or "real").strip()
    if "," in s or "，" in s:
        return s
    return STYLE_TO_VISUAL_STYLE.get(s.lower(), STYLE_TO_VISUAL_STYLE["real"])


def normalize_ratio(ratio: str) -> str:
    """API 只接受 16:9 / 9:16, 把 4:3/3:4 等回退到最接近的官方值."""
    r = (ratio or "").strip()
    if r in {"16:9", "9:16"}:
        return r
    if r in {"4:3"}:
        return "16:9"
    if r in {"3:4", "1:1"}:
        return "9:16"
    return "9:16"


@dataclass
class ManjuSubmission:
    """High-level submission, 旧测试契约保留.

    生产路径 (real-mode): script_text → 上传到 TOS → 转为 script_url, 然后
    script_analysis 用 file_url + file_type + file_name.
    """

    script_text: str = ""
    script_url: str = ""
    style: str = "real"
    ratio: str = "9:16"
    narration: str = "auto"
    episode_duration_sec: int = 150
    episode_count: int = 0
    voice: str = ""
    enable_watermark: bool = False
    file_type: str = "txt"
    file_name: str = ""

    def validate(self) -> None:
        if not self.script_text and not self.script_url:
            raise ValueError("script_text or script_url required")
        if self.script_text and len(self.script_text) > MAX_SCRIPT_CHARS:
            raise ValueError(
                f"script_text {len(self.script_text)} > {MAX_SCRIPT_CHARS} chars; "
                "split or upload as script_url"
            )
        if self.style not in STYLE_VALUES and "," not in self.style and "，" not in self.style:
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
        """通用 payload 序列化, 兼容旧 test (字段映射保留).

        注意: 此方法主要服务于单元测试. 真实调用 ``ManjuAgentClient`` 内部
        会调用 ``to_script_analysis_payload()`` 走官方契约.
        """
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

    def to_script_analysis_payload(self) -> dict[str, Any]:
        """官方 ``CVSync2AsyncSubmitTask`` payload, 用于 ``req_key=pippit_shortplay_cvtob_script_analysis``."""
        self.validate()
        if not self.script_url:
            raise ValueError("script_analysis requires script_url (public TXT/DOCX URL)")
        return {
            "req_key":      MANJU_REQ_KEY_SCRIPT_ANALYSIS,
            "visual_style": style_to_visual_style(self.style),
            "video_ratio":  normalize_ratio(self.ratio),
            "file_url":     self.script_url,
            "file_type":    (self.file_type or "txt").lower(),
            "file_name":    self.file_name or f"script.{(self.file_type or 'txt').lower()}",
        }


@dataclass
class ManjuEpisode:
    """合成完成的单集成片."""
    episode_no: int
    video_url: str               # final_video_url (短期 TTL, 必须转存)
    archived_path: str = ""
    duration_seconds: float = 0.0
    subtitle_url: str = ""
    cover_url: str = ""           # final_video_cover_url
    metadata: dict = field(default_factory=dict)


@dataclass
class ManjuResult:
    task_id: str
    status: str
    episodes: list[ManjuEpisode] = field(default_factory=list)
    overall_duration_seconds: float = 0.0
    raw_response: dict = field(default_factory=dict)
    aigc_meta_tagged: bool = False
    assets_id: str = ""           # 剧本解析返回, 后续流程依赖
    thread_id: str = ""           # 剧本解析返回, 后续流程依赖


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------

class ManjuAgentClient:
    """火山「小云雀-短剧漫剧 Agent」客户端 (4 阶段 OpenAPI 编排).

    高层 (单次调用全流程)::

        client = ManjuAgentClient()
        task_id = client.submit_script(novel_text="...", style="real", ratio="9:16")
        result  = client.wait_for_completion(task_id, ep_id="job001")
        for ep in result.episodes:
            print(ep.episode_no, ep.archived_path, ep.duration_seconds)

    低层 (按需手动编排, 测试/特殊场景)::

        analysis = client.analyze_script(file_url="https://x.docx", visual_style="...", video_ratio="9:16")
        client.generate_materials(analysis["assets_id"], analysis["thread_id"])
        for ep_id in analysis["episode_ids"]:
            client.generate_episode_videos(analysis["assets_id"], analysis["thread_id"], ep_id)
            mp4 = client.compose_episode_video(analysis["assets_id"], analysis["thread_id"], ep_id)
            print(ep_id, mp4["final_video_url"])
    """

    api_action_submit = MANJU_ACTION_SUBMIT
    api_action_query  = MANJU_ACTION_QUERY
    api_version       = MANJU_VERSION

    def __init__(
        self,
        access_key: str | None = None,
        secret_key: str | None = None,
        *,
        req_key: str | None = None,
        storage=None,
        poll_interval_seconds: float = 30.0,
        timeout_seconds: float = 4 * 3600.0,
        mock: bool | None = None,
    ):
        # 视频生成的默认 req_key (可被 env / 参数覆盖, 切换 fast/std)
        self.req_key = (
            req_key
            or os.environ.get("MANJU_REQ_KEY", "").strip()
            or MANJU_REQ_KEY_VIDEO_GEN_FAST
        )
        self.req_key_compose = (
            MANJU_REQ_KEY_VIDEO_COMPOSE
            if self.req_key == MANJU_REQ_KEY_VIDEO_GEN_FAST
            else MANJU_REQ_KEY_VIDEO_COMPOSE_STD
        )

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

        # task_id (analysis stage) → 完整 submission 上下文 (供 wait_for_completion 链下游)
        self._pending: dict[str, dict[str, Any]] = {}

    # ---------------- public API (backward-compat) ----------------

    def submit_script(
        self,
        novel_text: str = "",
        *,
        script_url: str = "",
        file_type: str = "txt",
        file_name: str = "",
        style: str = "real",
        ratio: str = "9:16",
        narration: str = "auto",
        episode_duration_sec: int = 150,
        episode_count: int = 0,
        voice: str = "",
        enable_watermark: bool = False,
    ) -> str:
        """提交一份剧本.

        生产路径: 若 ``novel_text`` 非空, 先上传到 TOS 拿到 public URL,
        再调用剧本解析接口. 返回剧本解析 stage 的 ``task_id``.
        """
        submission = ManjuSubmission(
            script_text=novel_text,
            script_url=script_url,
            style=style, ratio=ratio, narration=narration,
            episode_duration_sec=episode_duration_sec,
            episode_count=episode_count,
            voice=voice,
            enable_watermark=enable_watermark,
            file_type=file_type,
            file_name=file_name,
        )
        submission.validate()

        if self.mock:
            mock_id = f"mock-manju-{uuid.uuid4().hex[:12]}"
            _log.info("[manju-mock] submit -> %s (style=%s ratio=%s)",
                      mock_id, style, ratio)
            return mock_id

        # Real path: ensure file_url
        if not submission.script_url and submission.script_text:
            submission.script_url = self._upload_script_to_tos(
                submission.script_text, submission.file_type,
                submission.file_name or f"script-{uuid.uuid4().hex[:8]}.{submission.file_type}",
            )
            if not submission.file_name:
                submission.file_name = submission.script_url.rsplit("/", 1)[-1]

        payload = submission.to_script_analysis_payload()
        resp = self._http_post_retry(self.api_action_submit, payload,
                                     req_key=MANJU_REQ_KEY_SCRIPT_ANALYSIS)
        self._raise_for_code(resp)
        task_id = (resp.get("data") or {}).get("task_id")
        if not task_id:
            raise ManjuAgentError(f"missing task_id in submit response: {resp}")
        self._pending[str(task_id)] = {
            "stage": "script_analysis",
            "submission": submission,
            "started_at": time.time(),
        }
        return str(task_id)

    def query_task(self, task_id: str) -> dict:
        """通用查询入口, 兼容旧测试 (mock 模式直接返回 done+episodes)."""
        if self.mock:
            return _mock_query_response(task_id)
        # 真实模式: 默认按 script_analysis 查询. 想查其它 stage,
        # 用 _query_subtask(req_key, task_id).
        return self._query_subtask(MANJU_REQ_KEY_SCRIPT_ANALYSIS, task_id)

    def wait_for_completion(self, task_id: str, *, ep_id: str = "ep") -> ManjuResult:
        """轮询 ``task_id`` (script_analysis stage) 直到全 4 阶段完成,返回 ManjuResult.

        在 mock 模式下直接返回固定 fixtures (供 orchestrator 集成测试).
        """
        if self.mock:
            data = _mock_query_response(task_id)
            return self._archive_mock_result(task_id, data, ep_id=ep_id)
        return self._run_full_pipeline(task_id, ep_id=ep_id)

    def render_script(
        self,
        novel_text: str,
        *,
        ep_id: str = "ep",
        **submission_kwargs,
    ) -> ManjuResult:
        """便捷封装: submit + wait."""
        task_id = self.submit_script(novel_text, **submission_kwargs)
        return self.wait_for_completion(task_id, ep_id=ep_id)

    # ---------------- 4-stage public methods (low-level) ----------------

    def analyze_script(
        self,
        *,
        file_url: str,
        visual_style: str,
        video_ratio: str = "9:16",
        file_type: str = "txt",
        file_name: str = "",
    ) -> dict[str, Any]:
        """剧本解析. submit + poll. 返回 resp_data 解析后字典."""
        payload = {
            "req_key":      MANJU_REQ_KEY_SCRIPT_ANALYSIS,
            "visual_style": style_to_visual_style(visual_style),
            "video_ratio":  normalize_ratio(video_ratio),
            "file_url":     file_url,
            "file_type":    file_type.lower(),
            "file_name":    file_name or file_url.rsplit("/", 1)[-1],
        }
        task_id = self._submit_subtask(MANJU_REQ_KEY_SCRIPT_ANALYSIS, payload)
        data = self._wait_subtask(MANJU_REQ_KEY_SCRIPT_ANALYSIS, task_id, ep_id="analyze")
        resp_data = _parse_resp_data(data.get("resp_data"))
        return {
            "task_id":     task_id,
            "assets_id":   resp_data.get("assets_id"),
            "thread_id":   resp_data.get("thread_id"),
            "episode_ids": _extract_episode_ids(resp_data),
            "script_detail": resp_data.get("script_detail") or {},
            "raw":         resp_data,
        }

    def generate_materials(
        self,
        assets_id: str,
        thread_id: str,
        *,
        run_id: str | None = None,
    ) -> dict[str, Any]:
        """图片生成 (角色/场景图). submit + poll."""
        payload = {
            "req_key":   MANJU_REQ_KEY_MATERIAL_DESIGN,
            "assets_id": assets_id,
            "thread_id": thread_id,
        }
        if run_id:
            payload["run_id"] = run_id[:32]
        task_id = self._submit_subtask(MANJU_REQ_KEY_MATERIAL_DESIGN, payload)
        data = self._wait_subtask(MANJU_REQ_KEY_MATERIAL_DESIGN, task_id, ep_id="material")
        resp_data = _parse_resp_data(data.get("resp_data"))
        _verify_material_rendering(resp_data)
        return {"task_id": task_id, "raw": resp_data}

    def generate_episode_videos(
        self,
        assets_id: str,
        thread_id: str,
        episode_id: str,
        *,
        run_id: str | None = None,
        fast: bool = True,
    ) -> dict[str, Any]:
        """单集分镜视频生成. submit + poll."""
        req_key = MANJU_REQ_KEY_VIDEO_GEN_FAST if fast else MANJU_REQ_KEY_VIDEO_GEN_STD
        payload = {
            "req_key":    req_key,
            "assets_id":  assets_id,
            "thread_id":  thread_id,
            "episode_id": str(episode_id),
        }
        if run_id:
            payload["run_id"] = run_id[:32]
        task_id = self._submit_subtask(req_key, payload)
        data = self._wait_subtask(req_key, task_id, ep_id=f"vidgen-{episode_id}")
        resp_data = _parse_resp_data(data.get("resp_data"))
        _verify_shot_statuses(resp_data, episode_id)
        return {"task_id": task_id, "raw": resp_data}

    def compose_episode_video(
        self,
        assets_id: str,
        thread_id: str,
        episode_id: str,
        *,
        fast: bool = True,
    ) -> dict[str, Any]:
        """单集视频合成. submit + poll. 返回 final_video_url + final_video_cover_url."""
        req_key = (
            MANJU_REQ_KEY_VIDEO_COMPOSE if fast else MANJU_REQ_KEY_VIDEO_COMPOSE_STD
        )
        payload = {
            "req_key":    req_key,
            "assets_id":  assets_id,
            "thread_id":  thread_id,
            "episode_id": str(episode_id),
        }
        task_id = self._submit_subtask(req_key, payload)
        data = self._wait_subtask(req_key, task_id, ep_id=f"compose-{episode_id}")
        resp_data = _parse_resp_data(data.get("resp_data"))
        if not resp_data.get("final_video_url"):
            raise ManjuAgentError(
                f"compose ep#{episode_id}: missing final_video_url in {resp_data!r}"
            )
        return {
            "task_id":            task_id,
            "final_video_url":    resp_data.get("final_video_url"),
            "final_video_cover":  resp_data.get("final_video_cover_url", ""),
            "raw":                resp_data,
        }

    # ---------------- internals (real-mode pipeline) ----------------

    def _run_full_pipeline(self, analysis_task_id: str, *, ep_id: str) -> ManjuResult:
        """从 analysis 阶段开始, 串行跑完 4 阶段."""
        ctx = self._pending.get(analysis_task_id)
        # Stage 1: 等剧本解析完成
        data = self._wait_subtask(MANJU_REQ_KEY_SCRIPT_ANALYSIS, analysis_task_id, ep_id=ep_id)
        resp = _parse_resp_data(data.get("resp_data"))
        assets_id = resp.get("assets_id")
        thread_id = resp.get("thread_id")
        episode_ids = _extract_episode_ids(resp)
        if not assets_id or not thread_id:
            raise ManjuAgentError(
                f"script_analysis: missing assets_id/thread_id in resp_data {resp!r}"
            )
        if not episode_ids:
            raise ManjuAgentError(f"script_analysis: no EpisodeID in {resp!r}")
        _log.info("[%s] script_analysis done: assets=%s thread=%s eps=%s",
                  ep_id, assets_id, thread_id, len(episode_ids))

        # Stage 2: 图片生成 (全剧一次)
        run_id_material = f"{ep_id}-mat-{uuid.uuid4().hex[:8]}"[:32]
        self.generate_materials(assets_id, thread_id, run_id=run_id_material)
        _log.info("[%s] material_design done", ep_id)

        # Stage 3+4: 每集 video_generate → video_compose 串行
        fast = (self.req_key == MANJU_REQ_KEY_VIDEO_GEN_FAST)
        episodes: list[ManjuEpisode] = []
        for idx, ep in enumerate(episode_ids, start=1):
            run_id_vid = f"{ep_id}-v{ep}-{uuid.uuid4().hex[:6]}"[:32]
            self.generate_episode_videos(assets_id, thread_id, ep,
                                         run_id=run_id_vid, fast=fast)
            compose = self.compose_episode_video(assets_id, thread_id, ep, fast=fast)
            url = compose["final_video_url"]
            archived = ""
            try:
                key = f"manju/{ep_id}/{analysis_task_id}/episode_{idx:03d}.mp4"
                obj = self.storage.archive_url(key, url)
                archived = getattr(obj, "path", "") or ""
            except Exception as e:  # noqa: BLE001
                _log.warning("[%s] archive ep#%d failed: %s", ep_id, idx, e)
            episodes.append(ManjuEpisode(
                episode_no=idx,
                video_url=url,
                archived_path=archived,
                duration_seconds=0.0,
                cover_url=compose.get("final_video_cover", ""),
                metadata={"episode_id": ep, "compose_raw": compose["raw"]},
            ))
            _log.info("[%s] ep#%d done (episode_id=%s)", ep_id, idx, ep)

        return ManjuResult(
            task_id=analysis_task_id,
            status=STATUS_TERMINAL_DONE,
            episodes=episodes,
            overall_duration_seconds=sum(e.duration_seconds for e in episodes),
            raw_response=resp,
            aigc_meta_tagged=False,
            assets_id=assets_id,
            thread_id=thread_id,
        )

    def _submit_subtask(self, req_key: str, payload: dict) -> str:
        """submit + 解析 task_id."""
        resp = self._http_post_retry(self.api_action_submit, payload, req_key=req_key)
        self._raise_for_code(resp)
        tid = (resp.get("data") or {}).get("task_id")
        if not tid:
            raise ManjuAgentError(f"missing task_id (req_key={req_key}): {resp}")
        return str(tid)

    def _query_subtask(self, req_key: str, task_id: str) -> dict:
        resp = self._http_post_retry(
            self.api_action_query, {"req_key": req_key, "task_id": task_id},
            req_key=req_key,
        )
        self._raise_for_code(resp)
        return resp.get("data") or {}

    def _wait_subtask(self, req_key: str, task_id: str, *, ep_id: str) -> dict:
        deadline = time.monotonic() + self.timeout
        last_status = ""
        while time.monotonic() < deadline:
            data = self._query_subtask(req_key, task_id)
            status = (data.get("status") or "").lower()
            if status != last_status:
                _log.info("[%s] req_key=%s task=%s status=%s",
                          ep_id, req_key, task_id, status)
                last_status = status
            if status == STATUS_TERMINAL_DONE:
                return data
            if status == STATUS_TERMINAL_NOT_FOUND:
                raise ManjuAgentError(f"task {task_id} not_found (req_key={req_key})")
            if status == STATUS_TERMINAL_EXPIRED:
                raise ManjuAgentError(f"task {task_id} expired; resubmit")
            if status == STATUS_TERMINAL_FAILED:
                raise ManjuAgentError(
                    f"task {task_id} failed (req_key={req_key}): {data.get('message') or data}"
                )
            if status and status not in STATUS_RUNNING:
                _log.warning("[%s] unknown status %r; continuing", ep_id, status)
            time.sleep(self.poll_interval)
        raise ManjuAgentTimeout(
            f"task {task_id} (req_key={req_key}) did not complete in {self.timeout}s"
        )

    @retry(
        exceptions=(urllib.error.URLError, urllib.error.HTTPError, TimeoutError,
                    ManjuAgentRetryable),
        attempts=12, base_delay=4.0, max_delay=90.0,
    )
    def _http_post_retry(self, action: str, payload: dict, *, req_key: str) -> dict:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        signed = sign_request(
            access_key=self.access_key, secret_key=self.secret_key,
            action=action, version=self.api_version, body=body,
            host=MANJU_HOST, region=MANJU_REGION, service=MANJU_SERVICE,
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
            msg  = detail.get("message", str(e))
            rid  = detail.get("request_id")
            if code in RETRYABLE_CODES:
                raise ManjuAgentRetryable(code, msg) from None
            if code in AUDIT_FATAL_CODES:
                raise ManjuAgentAuditError(code, msg, request_id=rid) from None
            raise ManjuAgentError(f"[{code}] {msg} request_id={rid}") from None
        try:
            return json.loads(raw)
        except json.JSONDecodeError as e:
            raise ManjuAgentError(f"non-JSON response: {raw[:512]!r}") from e

    @staticmethod
    def _raise_for_code(response: dict) -> None:
        code = int(response.get("code", -1))
        if code in (10000, 0):
            return
        msg  = response.get("message", "")
        rid  = response.get("request_id")
        if code in AUDIT_FATAL_CODES:
            raise ManjuAgentAuditError(code, msg, request_id=rid)
        if code in RETRYABLE_CODES:
            raise ManjuAgentRetryable(code, msg)
        raise ManjuAgentError(f"[{code}] {msg} request_id={rid}")

    def _upload_script_to_tos(
        self, script_text: str, file_type: str, file_name: str,
    ) -> str:
        """把剧本写到 TOS, 返回公网可读 URL.

        要求 storage 实现 ``put_bytes(key, payload, public=True)`` 并返回
        含 ``public_url`` 的对象.
        """
        if file_type.lower() == "docx":
            # 用 python-docx 优雅地把纯文本塞进 docx 里, 失败则把 .docx 当 .txt 上传
            try:
                from docx import Document  # type: ignore[import-not-found]
                doc = Document()
                for line in script_text.splitlines() or [""]:
                    doc.add_paragraph(line)
                buf = io.BytesIO()
                doc.save(buf)
                payload = buf.getvalue()
            except Exception:  # noqa: BLE001
                payload = script_text.encode("utf-8")
                file_type = "txt"
                file_name = file_name.replace(".docx", ".txt")
        else:
            payload = script_text.encode("utf-8")

        key = f"manju/scripts/{file_name}"
        obj = self.storage.put_bytes(key, payload, public=True)
        url = getattr(obj, "public_url", "") or getattr(obj, "url", "")
        if not url:
            raise ManjuAgentError(
                f"upload_script_to_tos failed: storage backend "
                f"{type(self.storage).__name__} did not return public_url"
            )
        _log.info("[manju] uploaded script to %s (%d bytes, type=%s)",
                  url, len(payload), file_type)
        return url

    def _archive_mock_result(self, task_id: str, data: dict, *, ep_id: str) -> ManjuResult:
        """Mock-mode archive: 复制 mock data → ManjuResult (含 storage 转存)."""
        eps_raw = data.get("episodes") or []
        episodes: list[ManjuEpisode] = []
        for idx, ep in enumerate(eps_raw, start=1):
            no  = int(ep.get("episode_no") or idx)
            url = ep.get("video_url") or ""
            if not url:
                continue
            archived = ""
            try:
                key = f"manju/{ep_id}/{task_id}/episode_{no:03d}.mp4"
                obj = self.storage.archive_url(key, url)
                archived = getattr(obj, "path", "") or ""
            except Exception as e:  # noqa: BLE001
                _log.warning("archive mock ep#%d failed: %s", no, e)
            episodes.append(ManjuEpisode(
                episode_no=no,
                video_url=url,
                archived_path=archived,
                duration_seconds=float(ep.get("duration") or 0),
                subtitle_url=ep.get("subtitle_url", ""),
                cover_url=ep.get("cover_url", ""),
                metadata={k: v for k, v in ep.items()
                          if k not in {"video_url", "duration"}},
            ))
        return ManjuResult(
            task_id=task_id,
            status=data.get("status", STATUS_TERMINAL_DONE),
            episodes=episodes,
            overall_duration_seconds=sum(e.duration_seconds for e in episodes),
            raw_response=data,
            aigc_meta_tagged=bool(data.get("aigc_meta_tagged", False)),
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_resp_data(raw: Any) -> dict:
    """官方 resp_data 是 JSON 字符串, 解析为 dict.也兼容已是 dict 的情况."""
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str) and raw:
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            _log.warning("resp_data is not valid JSON: %s", raw[:200])
            return {}
    return {}


def _extract_episode_ids(resp_data: dict) -> list[str]:
    """从剧本解析的 resp_data 提取所有 EpisodeID, 按数字序排序."""
    eps = (resp_data.get("script_detail") or {}).get("EpisodeAssets") or []
    ids: list[str] = []
    for ep in eps:
        eid = ep.get("EpisodeID") if isinstance(ep, dict) else None
        if eid:
            ids.append(str(eid))
    try:
        ids.sort(key=lambda x: int(x))
    except ValueError:
        ids.sort()
    return ids


def _verify_material_rendering(resp_data: dict) -> None:
    """图片生成完成后,检查所有角色/场景的 Expect==Actual."""
    char_failed = []
    for c in resp_data.get("character_detail") or []:
        if not isinstance(c, dict):
            continue
        if c.get("ExpectRenderImageCount", 0) != c.get("ActualRenderImageCount", 0):
            char_failed.append(c.get("CharacterName") or c.get("CharacterID"))
    scene_failed = []
    for s in resp_data.get("scene_detail") or []:
        if not isinstance(s, dict):
            continue
        if s.get("ExpectRenderImageCount", 0) != s.get("ActualRenderImageCount", 0):
            scene_failed.append(s.get("Name") or s.get("SceneID"))
    if char_failed or scene_failed:
        _log.warning(
            "material_design partial fail: characters=%s scenes=%s",
            char_failed, scene_failed,
        )


def _verify_shot_statuses(resp_data: dict, episode_id: str) -> None:
    """视频生成完成后, 检查所有 Shots[].Status == 3 (done). 否则视频合成会失败."""
    details = resp_data.get("storyboard_detail") or []
    for det in details:
        if not isinstance(det, dict):
            continue
        if str(det.get("EpisodeID")) != str(episode_id):
            continue
        failed: list[str] = []
        for shot in det.get("Shots") or []:
            if not isinstance(shot, dict):
                continue
            if int(shot.get("Status", 0)) != STAGE_STATUS_DONE:
                failed.append(str(shot.get("ShotID")))
        if failed:
            raise ManjuAgentError(
                f"video_generate ep#{episode_id}: {len(failed)} shot(s) not done: "
                f"{failed[:5]}{'...' if len(failed) > 5 else ''} "
                "(视频合成会失败, 需第三方工具重生成后拼接)"
            )


def _mock_query_response(task_id: str) -> dict:
    """Deterministic mock for tests / dev when AKSK not provided."""
    from src.common.sample_catalog import catalog_samples

    samples = catalog_samples()
    episodes = []
    for i, ep_no in enumerate((1, 2, 3), start=0):
        s = samples[i % len(samples)]
        episodes.append(
            {
                "episode_no": ep_no,
                "video_url": s["video_url"],
                "duration": 150.0,
                "subtitle_url": f"{s['video_url'].rsplit('.', 1)[0]}.srt",
                "cover_url": s.get("cover_url"),
            }
        )
    return {
        "status": STATUS_TERMINAL_DONE,
        "task_id": task_id,
        "episodes": episodes,
        "aigc_meta_tagged": False,
    }


__all__ = [
    # Client + result types
    "ManjuAgentClient",
    "ManjuSubmission",
    "ManjuResult",
    "ManjuEpisode",
    # Errors
    "ManjuAgentError",
    "ManjuAgentAuditError",
    "ManjuAgentRetryable",
    "ManjuAgentTimeout",
    # Enums
    "Style", "Ratio", "NarrationMode",
    # Mode helpers
    "is_mock_mode", "is_manju_agent_enabled",
    # Constants (4 stages)
    "MANJU_REQ_KEY_SCRIPT_ANALYSIS",
    "MANJU_REQ_KEY_MATERIAL_DESIGN",
    "MANJU_REQ_KEY_VIDEO_GEN_FAST",
    "MANJU_REQ_KEY_VIDEO_COMPOSE",
    "MANJU_REQ_KEY_VIDEO_GEN_STD",
    "MANJU_REQ_KEY_VIDEO_COMPOSE_STD",
    # Backward-compat aliases
    "MANJU_REQ_KEY_SEEDANCE_FAST_720P_DEFAULT",
    "MANJU_REQ_KEY_SEEDANCE_720P_DEFAULT",
    "MANJU_REQ_KEY_SYNTHESIZE_DEFAULT",
    # Field map + enums
    "MANJU_FIELDS",
    "STYLE_VALUES", "RATIO_VALUES", "NARRATION_VALUES", "FILE_TYPE_VALUES",
    "RECOMMENDED_VISUAL_STYLES",
    "STYLE_TO_VISUAL_STYLE",
    # Helpers
    "style_to_visual_style", "normalize_ratio",
]
