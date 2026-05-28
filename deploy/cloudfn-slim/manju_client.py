"""火山「小云雀-短剧漫剧 Agent」精简客户端 (SCF 单文件版).

精简自 cloudfunctions/xyq-api/src/shell3_skylark_engine/manju_agent_client.py，
零外部依赖（stdlib only），针对 CloudBase SCF 异步 submit+poll 场景设计：
  - submit_script_analysis(file_url, ...)        → manju_task_id  (≤3s)
  - submit_material_design(assets_id, thread_id) → manju_task_id  (≤3s)
  - submit_video_gen(assets_id, thread_id, ep_id)
  - submit_video_compose(assets_id, thread_id, ep_id)
  - query(req_key, task_id)                      → 解析后的 data dict

凭证：环境变量 VOLC_ACCESS_KEY / VOLC_SECRET_KEY（或 VOLC_AK / VOLC_SK）。

为什么不复用现有模块：
  - 现有模块依赖 ../common 下 5+ 文件 + Storage 抽象，部署体积太大。
  - SCF 函数只需要 submit + query，不做轮询（轮询交给浏览器 GET /api/jobs/{id}）。
"""
from __future__ import annotations

import datetime as dt
import hashlib
import hmac
import json
import logging
import os
import random
import time
import urllib.error
import urllib.request
from typing import Any

_log = logging.getLogger(__name__)


HOST = "visual.volcengineapi.com"
REGION = "cn-north-1"
SERVICE = "cv"
VERSION = "2022-08-31"
ALGO = "HMAC-SHA256"

ACTION_SUBMIT = "CVSync2AsyncSubmitTask"
ACTION_QUERY = "CVSync2AsyncGetResult"

REQ_KEY_SCRIPT_ANALYSIS = "pippit_shortplay_cvtob_script_analysis"
REQ_KEY_MATERIAL_DESIGN = "pippit_shortplay_cvtob_material_design"
REQ_KEY_VIDEO_GEN_FAST = "pippit_shortplay_cvtob_video_generate_fast720p"
REQ_KEY_VIDEO_COMPOSE = "pippit_shortplay_cvtob_video_compose_fast720p"

STATUS_DONE = "done"
STATUS_RUNNING = {"processing", "in_queue", "generating", "rendering", "scripting"}
STATUS_NOT_FOUND = "not_found"
STATUS_EXPIRED = "expired"
STATUS_FAILED = "failed"

# 50429 = QPS 限流；50430 = 并发数限流；50500/50501 = 服务端瞬时错误；50511 = 上游瞬时
RATE_LIMIT_CODES = {50429, 50430}
RETRYABLE_CODES = {50429, 50430, 50500, 50501, 50511}
AUDIT_FATAL_CODES = {50411, 50412, 50413, 50512, 50513, 50514}

# 进程内重试上限（每个 _http_post 调用）
_DEFAULT_RETRIES = 3
_BACKOFF_BASE_S = 2.0  # 第 N 次重试 sleep = 2^N + jitter


class ManjuError(RuntimeError):
    def __init__(self, code: int | None, message: str, request_id: str = ""):
        super().__init__(f"[{code}] {message} request_id={request_id}")
        self.code = code
        self.request_id = request_id


def _credentials() -> tuple[str, str]:
    ak = (os.environ.get("VOLC_ACCESS_KEY", "")
          or os.environ.get("VOLC_AK", "")).strip()
    sk = (os.environ.get("VOLC_SECRET_KEY", "")
          or os.environ.get("VOLC_SK", "")).strip()
    return ak, sk


def is_configured() -> bool:
    ak, sk = _credentials()
    return bool(ak and sk)


def _sign(secret_key: str, datestamp: str) -> bytes:
    def s(key: bytes, msg: str) -> bytes:
        return hmac.new(key, msg.encode("utf-8"), hashlib.sha256).digest()
    k_date = s(secret_key.encode("utf-8"), datestamp)
    k_region = s(k_date, REGION)
    k_service = s(k_region, SERVICE)
    return s(k_service, "request")


def _http_post(action: str, payload: dict, *, timeout: float = 30.0,
               retries: int = _DEFAULT_RETRIES) -> dict:
    """POST 并对 50429/50430/50500/50501/50511 自动指数退避重试。

    每次重试睡眠 ``2^attempt + jitter`` 秒（attempt 从 0 起），最长 ~14s。
    若所有重试都打到限流，抛 ManjuError（caller 可据此降级到 HappyHorse）。
    """
    ak, sk = _credentials()
    if not ak or not sk:
        raise ManjuError(None, "missing VOLC_ACCESS_KEY/VOLC_SECRET_KEY")

    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    last_err: ManjuError | None = None
    attempts = max(1, int(retries))
    for attempt in range(attempts):
        now = dt.datetime.now(dt.timezone.utc)
        amzdate = now.strftime("%Y%m%dT%H%M%SZ")
        datestamp = now.strftime("%Y%m%d")
        canonical_qs = f"Action={action}&Version={VERSION}"
        payload_hash = hashlib.sha256(body).hexdigest()
        canonical_headers = (
            "content-type:application/json; charset=utf-8\n"
            f"host:{HOST}\n"
            f"x-content-sha256:{payload_hash}\n"
            f"x-date:{amzdate}\n"
        )
        signed_headers = "content-type;host;x-content-sha256;x-date"
        canonical_request = "\n".join([
            "POST", "/", canonical_qs, canonical_headers, signed_headers, payload_hash,
        ])
        credential_scope = f"{datestamp}/{REGION}/{SERVICE}/request"
        sts = "\n".join([
            ALGO, amzdate, credential_scope,
            hashlib.sha256(canonical_request.encode()).hexdigest(),
        ])
        signing_key = _sign(sk, datestamp)
        signature = hmac.new(signing_key, sts.encode(), hashlib.sha256).hexdigest()
        authorization = (
            f"{ALGO} Credential={ak}/{credential_scope}, "
            f"SignedHeaders={signed_headers}, Signature={signature}"
        )
        url = f"https://{HOST}/?{canonical_qs}"
        req = urllib.request.Request(
            url, data=body,
            headers={
                "Content-Type": "application/json; charset=utf-8",
                "Host": HOST, "X-Date": amzdate, "X-Content-Sha256": payload_hash,
                "Authorization": authorization,
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read())
        except urllib.error.HTTPError as e:
            raw = e.read().decode("utf-8", errors="replace")
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                last_err = ManjuError(e.code, raw[:300])
                break
            try:
                _raise_for_code(data, http_status=e.code)
                return data
            except ManjuError as me:
                last_err = me
                if me.code in RETRYABLE_CODES and attempt < attempts - 1:
                    sleep_s = min(15.0, _BACKOFF_BASE_S ** (attempt + 1)) + random.uniform(0, 0.5)
                    _log.warning("manju %s [%s] %s — backoff %.1fs (attempt %d/%d)",
                                 action, me.code, me, sleep_s, attempt + 1, attempts)
                    time.sleep(sleep_s)
                    continue
                raise
        except urllib.error.URLError as e:
            last_err = ManjuError(None, f"network error: {e}")
            if attempt < attempts - 1:
                time.sleep(min(10.0, _BACKOFF_BASE_S ** (attempt + 1)))
                continue
            break
    assert last_err is not None  # 不可达
    raise last_err


def _raise_for_code(response: dict, *, http_status: int = 200) -> None:
    code_raw = response.get("code", -1)
    try:
        code = int(code_raw)
    except (TypeError, ValueError):
        code = -1
    if code in (10000, 0):
        return
    msg = response.get("message", "")
    rid = response.get("request_id", "")
    raise ManjuError(code, msg, request_id=rid)


# ---------------------------------------------------------------------------
# Stage submitters
# ---------------------------------------------------------------------------

VISUAL_STYLE_DEFAULT = "2D, 国风, 平涂"
VIDEO_RATIO_DEFAULT = "9:16"


def submit_script_analysis(file_url: str, *,
                           visual_style: str = VISUAL_STYLE_DEFAULT,
                           video_ratio: str = VIDEO_RATIO_DEFAULT,
                           file_type: str = "txt", file_name: str = "") -> str:
    """Stage 1 — submit script analysis. Returns manju task_id (string)."""
    payload = {
        "req_key": REQ_KEY_SCRIPT_ANALYSIS,
        "visual_style": visual_style,
        "video_ratio": video_ratio,
        "file_url": file_url,
        "file_type": (file_type or "txt").lower(),
        "file_name": file_name or file_url.rsplit("/", 1)[-1] or "script.txt",
    }
    resp = _http_post(ACTION_SUBMIT, payload)
    _raise_for_code(resp)
    tid = (resp.get("data") or {}).get("task_id")
    if not tid:
        raise ManjuError(None, f"missing task_id in submit response: {resp}")
    return str(tid)


def submit_material_design(assets_id: str, thread_id: str) -> str:
    """Stage 2 — material (character/scene) generation."""
    payload = {
        "req_key": REQ_KEY_MATERIAL_DESIGN,
        "assets_id": assets_id,
        "thread_id": thread_id,
    }
    resp = _http_post(ACTION_SUBMIT, payload)
    _raise_for_code(resp)
    tid = (resp.get("data") or {}).get("task_id")
    if not tid:
        raise ManjuError(None, f"missing task_id in submit response: {resp}")
    return str(tid)


def submit_video_generate(assets_id: str, thread_id: str, episode_id: str) -> str:
    """Stage 3 — per-episode shot videos."""
    payload = {
        "req_key": REQ_KEY_VIDEO_GEN_FAST,
        "assets_id": assets_id,
        "thread_id": thread_id,
        "episode_id": str(episode_id),
    }
    resp = _http_post(ACTION_SUBMIT, payload)
    _raise_for_code(resp)
    tid = (resp.get("data") or {}).get("task_id")
    if not tid:
        raise ManjuError(None, f"missing task_id in submit response: {resp}")
    return str(tid)


def submit_video_compose(assets_id: str, thread_id: str, episode_id: str) -> str:
    """Stage 4 — per-episode video compose. Returns task_id."""
    payload = {
        "req_key": REQ_KEY_VIDEO_COMPOSE,
        "assets_id": assets_id,
        "thread_id": thread_id,
        "episode_id": str(episode_id),
    }
    resp = _http_post(ACTION_SUBMIT, payload)
    _raise_for_code(resp)
    tid = (resp.get("data") or {}).get("task_id")
    if not tid:
        raise ManjuError(None, f"missing task_id in submit response: {resp}")
    return str(tid)


# ---------------------------------------------------------------------------
# Status query
# ---------------------------------------------------------------------------

def query(req_key: str, task_id: str) -> dict:
    """Query task status; returns the `data` dict from CVSync2AsyncGetResult."""
    resp = _http_post(ACTION_QUERY, {"req_key": req_key, "task_id": task_id})
    _raise_for_code(resp)
    return resp.get("data") or {}


def parse_resp_data(raw: Any) -> dict:
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str) and raw:
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return {}
    return {}


def extract_episode_ids(resp_data: dict) -> list[str]:
    """Pull EpisodeID list out of script_analysis resp_data (numeric-sorted)."""
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


__all__ = [
    "ManjuError",
    "is_configured",
    "submit_script_analysis",
    "submit_material_design",
    "submit_video_generate",
    "submit_video_compose",
    "query",
    "parse_resp_data",
    "extract_episode_ids",
    "REQ_KEY_SCRIPT_ANALYSIS",
    "REQ_KEY_MATERIAL_DESIGN",
    "REQ_KEY_VIDEO_GEN_FAST",
    "REQ_KEY_VIDEO_COMPOSE",
    "STATUS_DONE", "STATUS_RUNNING", "STATUS_FAILED",
    "STATUS_NOT_FOUND", "STATUS_EXPIRED",
]
