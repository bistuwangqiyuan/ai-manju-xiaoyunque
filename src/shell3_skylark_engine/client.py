"""Skylark Agent 2.0 (Pippit IV2V with vinput) — official spec client.

Reference: https://www.volcengine.com/docs/85621/2359610?lang=zh  (2026-05 真值)

Confirmed field contract (官方文档):
    Endpoint:    POST https://visual.volcengineapi.com
    Signing:     HMAC-SHA256 V4 (Region=cn-north-1, Service=cv)
    Action:      CVSync2AsyncSubmitTask  /  CVSync2AsyncGetResult
    Version:     2022-08-31
    req_key:     "pippit_iv2v_v20_cvtob_with_vinput"  (fixed single value)

    Submit body:
        req_key            : str        固定
        prompt             : str        ≤ 2000 chars，含人物设定块
        img_url_list       : [str]      参考图 URL 数组（含角色 + 场景 + 风格锚定）
        video_url_list     : [str]      参考视频 URL 数组（动作迁移用）
        ratio              : str        ["16:9", "9:16", "4:3", "3:4"]
        duration           : str        ["～15s", "～30s", "40～60s"]   ← 最长 60s!
        language           : str        默认 "Chinese"
        enable_watermark   : bool       默认 true（左上 "AI生成" + 右下 "小云雀AI生成"）

    Constraints:
        len(img_url_list) + len(video_url_list) ≤ 50
        single image ≤ 20MB, ≤ 4096×4096
        single video ≤ 3min, ≤ 200MB
        prompt ≤ 2000 字 / chars

    Query body:
        req_key + task_id
        req_json (optional, JSON-string) — 写入 AIGC 隐式标识：
            {"aigc_meta": {"content_producer", "producer_id",
                           "content_propagator", "propagate_id"}}

    Query response:
        data.status       : processing / in_queue / generating / done /
                            not_found / expired
        data.video_url    : 1h 有效（task_id 12h 有效）
        data.resp_data    : JSON string, e.g. {"Duration": 17.23,
                                                "InputVideoDurationSum": 5}
        data.aigc_meta_tagged : bool  — 隐式标识是否落库
"""
from __future__ import annotations

import json
import logging
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Sequence

from ..common.retry import retry
from ..common.storage import Storage, default_storage
from ..common.volc_credentials import (
    resolve_volc_access_key,
    volc_secret_key_candidates,
)
from ..common.volc_signer import sign_request


_log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Constants — locked to official documentation 2026-05
# ---------------------------------------------------------------------------

SKYLARK_REQ_KEY = "pippit_iv2v_v20_cvtob_with_vinput"
"""Official single canonical req_key for Skylark Agent 2.0 with vinput."""


RATIO_VALUES = ("16:9", "9:16", "4:3", "3:4")
DURATION_VALUES = ("～15s", "～30s", "40～60s")
DURATION_MAX_SECONDS = 60   # ★ 单次提交最长 60s；>60s 集走 chunk_renderer.py

LANGUAGE_VALUES = (
    "Chinese", "English", "Japanese", "Thai", "SouthAfrican", "French",
    "Turkish", "Malay", "German", "Korean", "Russian", "Spanish",
    "Indonesian", "Italian", "Portuguese", "Filipino", "Vietnamese",
    "Dutch", "Arabic",
)

MAX_REFS_PER_REQUEST = 50  # img + video combined
MAX_IMG_SIZE_BYTES = 20 * 1024 * 1024
MAX_IMG_RESOLUTION = 4096
MAX_VIDEO_DURATION_SECONDS = 180
MAX_VIDEO_SIZE_BYTES = 200 * 1024 * 1024
MAX_PROMPT_CHARS = 2000

# Status enum from official docs
STATUS_TERMINAL_DONE = "done"
STATUS_TERMINAL_NOT_FOUND = "not_found"
STATUS_TERMINAL_EXPIRED = "expired"
STATUS_RUNNING = {"processing", "in_queue", "generating"}

# Error code classification per official docs
RETRYABLE_CODES = {50429, 50430, 50500, 50501, 50511}
AUDIT_FATAL_CODES = {50411, 50412, 50413, 50512, 50513, 50514}


# ---------------------------------------------------------------------------
# Error model
# ---------------------------------------------------------------------------

class SkylarkError(RuntimeError):
    """Base exception for Skylark client failures."""


class SkylarkAuditError(SkylarkError):
    """Risk-control审核 failure (50411 / 50412 / 50413 / 50512 / 50513 / 50514).

    These are fatal: prompt or asset content was rejected; do not retry.
    """

    def __init__(self, code: int, message: str, request_id: str | None = None):
        super().__init__(f"[{code}] {message}")
        self.code = code
        self.request_id = request_id


class SkylarkRetryable(SkylarkError):
    """Transient error per official spec (QPS / concurrent / internal)."""

    def __init__(self, code: int, message: str):
        super().__init__(f"[{code}] {message}")
        self.code = code


class SkylarkTimeout(SkylarkError):
    pass


# ---------------------------------------------------------------------------
# Domain models — high-level wrapper over the flat官方契约
# ---------------------------------------------------------------------------

@dataclass
class ReferencePack:
    """Aggregates all reference images / videos into the flat官方契约.

    The高层调用方（pilot / shell1 编剧 / shell2 资产）通常会按"角色"+"场景"+"风格"
    分类持有引用图；ReferencePack 把它们扁平化为 img_url_list[] 并保证 ≤ 50 张
    总配额，同时维护"重要性排序"（角色 > 场景 > 风格）以便超额时优先丢风格图。
    """

    character_images: Sequence[str] = ()       # 角色参考（前 ~70%）
    scene_images: Sequence[str] = ()           # 场景参考（中间 ~20%）
    style_images: Sequence[str] = ()           # 风格锚点（剩余 ~10%）
    video_references: Sequence[str] = ()       # 动作迁移参考视频

    def flatten_imgs(self) -> list[str]:
        budget = MAX_REFS_PER_REQUEST - len(self.video_references)
        ordered = list(self.character_images) + list(self.scene_images) + list(self.style_images)
        if len(ordered) > budget:
            _log.warning("img+video refs %d exceed cap %d; truncating tail (style first)",
                         len(ordered) + len(self.video_references), MAX_REFS_PER_REQUEST)
            ordered = ordered[:budget]
        return ordered


@dataclass
class EpisodeRequest:
    """High-level episode submission. The client flattens to the官方契约 on send."""

    prompt: str
    references: ReferencePack = field(default_factory=ReferencePack)
    ratio: str = "9:16"
    duration: str = "40～60s"        # 选取最长候选
    language: str = "Chinese"
    enable_watermark: bool = False   # 商用关闭；本地 ASS+水印自渲染

    def to_payload(self) -> dict[str, Any]:
        if self.ratio not in RATIO_VALUES:
            raise ValueError(f"ratio={self.ratio!r} not in {RATIO_VALUES}")
        if self.duration not in DURATION_VALUES:
            raise ValueError(f"duration={self.duration!r} not in {DURATION_VALUES}")
        if self.language not in LANGUAGE_VALUES:
            raise ValueError(f"language={self.language!r} not in {LANGUAGE_VALUES}")
        if len(self.prompt) > MAX_PROMPT_CHARS:
            raise ValueError(
                f"prompt {len(self.prompt)} chars > {MAX_PROMPT_CHARS}; "
                "split into shots or compress character lock block"
            )

        img_list = self.references.flatten_imgs()
        vid_list = list(self.references.video_references)
        if len(img_list) + len(vid_list) > MAX_REFS_PER_REQUEST:
            raise ValueError(
                f"img+video refs {len(img_list)+len(vid_list)} > {MAX_REFS_PER_REQUEST}"
            )

        payload: dict[str, Any] = {
            "req_key": SKYLARK_REQ_KEY,
            "prompt": self.prompt,
            "ratio": self.ratio,
            "duration": self.duration,
            "language": self.language,
            "enable_watermark": self.enable_watermark,
        }
        if img_list:
            payload["img_url_list"] = img_list
        if vid_list:
            payload["video_url_list"] = vid_list
        return payload


@dataclass
class AigcMeta:
    """Implicit AIGC watermark embedded at query-time via req_json.

    Per 2025/09 国标 GB/T 45438-2025 隐式标识规范：
        - 可在 https://www.gcmark.com 验证落标成功
        - producer_id / content_propagator 为必填
    """

    content_producer: str = ""    # 内容生成服务 ID（如制作主体 18 位 USCC）
    producer_id: str = ""         # 视频唯一 ID（如 episode_id + uuid）
    content_propagator: str = ""  # 传播服务商 ID（如平台分发账号 ID）
    propagate_id: str = ""        # 传播服务商 ID 内部 ID

    def to_req_json(self) -> str:
        return json.dumps({"aigc_meta": {
            "content_producer": self.content_producer,
            "producer_id": self.producer_id,
            "content_propagator": self.content_propagator,
            "propagate_id": self.propagate_id,
        }}, ensure_ascii=False)


@dataclass
class EpisodeResult:
    task_id: str
    video_url: str                  # 1h 有效，必须立即转存
    archived_video_path: str
    input_video_duration_sum: float
    output_duration_seconds: float
    aigc_meta_tagged: bool
    raw_response: dict


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------

class SkylarkAgentV2WithRefClient:
    """Production client for Skylark Agent 2.0 (Pippit IV2V with vinput)."""

    api_action_submit = "CVSync2AsyncSubmitTask"
    api_action_query = "CVSync2AsyncGetResult"
    api_version = "2022-08-31"

    def __init__(
        self,
        access_key: str | None = None,
        secret_key: str | None = None,
        *,
        storage: Storage | None = None,
        poll_interval_seconds: float = 10.0,
        timeout_seconds: float = 2400.0,
        aigc_meta: AigcMeta | None = None,
    ):
        self.access_key = resolve_volc_access_key(access_key)
        self._secret_candidates = volc_secret_key_candidates(secret_key)
        if len(self._secret_candidates) == 0:
            raise SkylarkError(
                "Missing VOLC_SECRET_KEY / VOLC_SK (火山引擎 IAM Secret Key)"
            )
        if not self.access_key:
            raise SkylarkError(
                "Missing VOLC_ACCESS_KEY / VOLC_AK (火山引擎 IAM Access Key)"
            )
        self.secret_key = self._secret_candidates[0]
        self.storage = storage or default_storage()
        self.poll_interval = float(poll_interval_seconds)
        self.timeout = float(timeout_seconds)
        self.aigc_meta = aigc_meta

    # ---------------------------- public api ----------------------------

    def render_episode(self, request: EpisodeRequest, *,
                       ep_id: str | int = "ep",
                       chunk_id: str | int | None = None) -> EpisodeResult:
        """Submit + poll + archive for a single episode end-to-end."""

        task_id = self.submit(request)
        suffix = f"/chunk_{chunk_id}" if chunk_id is not None else ""
        _log.info("[%s%s] submitted task_id=%s", ep_id, suffix, task_id)
        return self.wait_and_archive(task_id, ep_id=ep_id, chunk_id=chunk_id)

    def submit(self, request: EpisodeRequest) -> str:
        payload = request.to_payload()
        last_err: SkylarkError | None = None
        for sk in self._secret_candidates:
            self.secret_key = sk
            try:
                response = self._http_post(self.api_action_submit, payload)
                self._raise_for_code(response)
                task_id = response.get("data", {}).get("task_id")
                if not task_id:
                    raise SkylarkError(f"missing task_id in success response: {response}")
                return str(task_id)
            except SkylarkError as exc:
                last_err = exc
                if "401" in str(exc):
                    continue
                raise
        raise last_err or SkylarkError("submit failed: exhausted secret key candidates")

    def wait_and_archive(self, task_id: str, *,
                         ep_id: str | int,
                         chunk_id: str | int | None = None) -> EpisodeResult:
        deadline = time.monotonic() + self.timeout
        while time.monotonic() < deadline:
            data = self._query(task_id)
            status = data.get("status")
            if status == STATUS_TERMINAL_DONE:
                return self._archive_result(task_id, data, ep_id=ep_id, chunk_id=chunk_id)
            if status == STATUS_TERMINAL_NOT_FOUND:
                raise SkylarkError(f"task {task_id} not_found (>12h or never existed)")
            if status == STATUS_TERMINAL_EXPIRED:
                raise SkylarkError(f"task {task_id} expired; resubmit required")
            if status not in STATUS_RUNNING:
                raise SkylarkError(f"unknown task status: {status!r} payload={data}")
            _log.debug("[%s] task %s status=%s", ep_id, task_id, status)
            time.sleep(self.poll_interval)
        raise SkylarkTimeout(f"task {task_id} did not finish in {self.timeout}s")

    # ---------------------------- internals ----------------------------

    @retry(
        exceptions=(urllib.error.URLError, urllib.error.HTTPError, TimeoutError, SkylarkRetryable),
        attempts=12, base_delay=4.0, max_delay=90.0,
    )
    def _http_post(self, action: str, payload: dict) -> dict:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        signed = sign_request(
            access_key=self.access_key,
            secret_key=self.secret_key,
            action=action,
            version=self.api_version,
            body=body,
        )
        req = urllib.request.Request(
            signed.url, data=signed.body, headers=signed.headers, method=signed.method,
        )
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                raw = resp.read()
        except urllib.error.HTTPError as e:
            # Try to parse JSON body even on 4xx/5xx (Volcengine returns JSON error)
            try:
                detail = json.loads(e.read())
            except Exception:  # noqa: BLE001
                raise
            code = int(detail.get("code", e.code))
            msg = detail.get("message", str(e))
            req_id = detail.get("request_id")
            if code in RETRYABLE_CODES:
                raise SkylarkRetryable(code, msg) from None
            if code in AUDIT_FATAL_CODES:
                raise SkylarkAuditError(code, msg, request_id=req_id) from None
            raise SkylarkError(f"[{code}] {msg} request_id={req_id}") from None
        try:
            return json.loads(raw)
        except json.JSONDecodeError as e:
            raise SkylarkError(f"non-JSON response: {raw[:512]!r}") from e

    def _query(self, task_id: str) -> dict:
        payload: dict[str, Any] = {"req_key": SKYLARK_REQ_KEY, "task_id": task_id}
        if self.aigc_meta is not None:
            payload["req_json"] = self.aigc_meta.to_req_json()
        resp = self._http_post(self.api_action_query, payload)
        self._raise_for_code(resp)
        return resp.get("data", {})

    @staticmethod
    def _raise_for_code(response: dict) -> None:
        code = int(response.get("code", -1))
        if code == 10000:
            return
        msg = response.get("message", "")
        req_id = response.get("request_id")
        if code in AUDIT_FATAL_CODES:
            raise SkylarkAuditError(code, msg, request_id=req_id)
        if code in RETRYABLE_CODES:
            raise SkylarkRetryable(code, msg)
        raise SkylarkError(f"[{code}] {msg} request_id={req_id}")

    def _archive_result(self, task_id: str, data: dict, *,
                        ep_id: str | int,
                        chunk_id: str | int | None = None) -> EpisodeResult:
        video_url = data.get("video_url", "")
        if not video_url:
            raise SkylarkError(f"missing video_url in completed task: {data}")

        suffix = "" if chunk_id is None else f"/chunk_{chunk_id}"
        key = f"episodes/{ep_id}{suffix}/full.mp4".lstrip("/")
        archived = self.storage.archive_url(key, video_url)

        resp_data = data.get("resp_data") or "{}"
        try:
            parsed = json.loads(resp_data) if isinstance(resp_data, str) else resp_data
        except json.JSONDecodeError:
            parsed = {}
        return EpisodeResult(
            task_id=task_id,
            video_url=video_url,
            archived_video_path=archived.path,
            input_video_duration_sum=float(parsed.get("InputVideoDurationSum", 0) or 0),
            output_duration_seconds=float(parsed.get("Duration", 0) or 0),
            aigc_meta_tagged=bool(data.get("aigc_meta_tagged", False)),
            raw_response=data,
        )
