"""阿里百炼「HappyHorse 图生视频」备用引擎（SCF 单文件版）.

当火山 Manju Agent 出现 50429/50430 等限流错误时，由 `real_jobs` 降级到
本模块继续完成 video_generate / video_compose 阶段。

工作流程（异步）:
    1. submit_i2v(first_frame_url, prompt, ...) → task_id    (POST, X-DashScope-Async: enable)
    2. query(task_id) → {status: PENDING/RUNNING/SUCCEEDED/FAILED, video_url}

无外部依赖，纯 stdlib。凭证:
    HAPPYHORSE_API_KEY  或  DASHSCOPE_API_KEY
"""
from __future__ import annotations

import http.client
import json
import logging
import os
import socket
import time
import urllib.error
import urllib.request
from typing import Any

_log = logging.getLogger(__name__)

# 默认走北京区域；可通过 HAPPYHORSE_REGION=intl/us/de 覆盖
REGION_ENDPOINTS = {
    "cn": "https://dashscope.aliyuncs.com",
    "intl": "https://dashscope-intl.aliyuncs.com",
    "us": "https://dashscope-us.aliyuncs.com",
}

MODEL_I2V = "happyhorse-1.0-i2v"
# DashScope WanX 文生图（用于生成首帧图）。
# 候选模型按优先级排序，逐个尝试直到接口接受（DashScope 各账户开放模型不同）。
T2I_MODEL_CANDIDATES = [
    "wanx2.1-t2i-plus",
    "wanx2.1-t2i-turbo",
    "wanx-v1",
]

STATUS_PENDING = "PENDING"
STATUS_RUNNING = "RUNNING"
STATUS_SUCCEEDED = "SUCCEEDED"
STATUS_FAILED = "FAILED"
STATUS_CANCELED = "CANCELED"
STATUS_UNKNOWN = "UNKNOWN"

TERMINAL_OK = {STATUS_SUCCEEDED}
TERMINAL_FAIL = {STATUS_FAILED, STATUS_CANCELED, STATUS_UNKNOWN}


class HappyHorseError(RuntimeError):
    """统一异常，code 为 HTTP 或业务码字符串。"""

    def __init__(self, code: str | int | None, message: str, request_id: str = ""):
        super().__init__(f"[{code}] {message} request_id={request_id}")
        self.code = code
        self.request_id = request_id


def _api_key() -> str:
    return (
        os.environ.get("HAPPYHORSE_API_KEY")
        or os.environ.get("DASHSCOPE_API_KEY")
        or ""
    ).strip()


def _endpoint() -> str:
    region = (os.environ.get("HAPPYHORSE_REGION") or "cn").strip().lower()
    return REGION_ENDPOINTS.get(region, REGION_ENDPOINTS["cn"])


def is_configured() -> bool:
    return bool(_api_key())


_RETRY_HTTP = (429, 500, 502, 503, 504)
_DEFAULT_NET_RETRIES = 3


def _http(method: str, url: str, *, body: dict | None = None,
          extra_headers: dict | None = None, timeout: float = 30.0,
          retries: int = _DEFAULT_NET_RETRIES) -> dict:
    """Call DashScope with light retry on transient network/HTTP errors.

    Retries on:
      - urllib.URLError (TLS hiccups, RemoteDisconnected, DNS)
      - HTTP 429/500/502/503/504
    Up to ``retries`` attempts with 2^n + jitter backoff.
    """
    api_key = _api_key()
    if not api_key:
        raise HappyHorseError(None, "missing HAPPYHORSE_API_KEY/DASHSCOPE_API_KEY")
    data = json.dumps(body, ensure_ascii=False).encode("utf-8") if body is not None else None
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Accept": "application/json",
    }
    if data is not None:
        headers["Content-Type"] = "application/json"
    if extra_headers:
        headers.update(extra_headers)

    attempts = max(1, int(retries))
    last_err: HappyHorseError | None = None
    for attempt in range(attempts):
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            raw = e.read().decode("utf-8", errors="replace")
            try:
                parsed = json.loads(raw)
            except json.JSONDecodeError:
                parsed = {}
            code = parsed.get("code") or parsed.get("Code") or e.code
            msg = parsed.get("message") or parsed.get("Message") or raw[:300]
            rid = parsed.get("request_id") or ""
            err = HappyHorseError(code, str(msg), request_id=str(rid))
            if e.code in _RETRY_HTTP and attempt < attempts - 1:
                sleep_s = min(15.0, 2 ** (attempt + 1)) + 0.3 * attempt
                _log.warning("happyhorse %s %s — backoff %.1fs (attempt %d/%d)",
                             method, e.code, sleep_s, attempt + 1, attempts)
                time.sleep(sleep_s)
                last_err = err
                continue
            raise err from None
        except (urllib.error.URLError,
                http.client.RemoteDisconnected,
                http.client.BadStatusLine,
                socket.timeout,
                ConnectionError,
                OSError) as e:
            last_err = HappyHorseError(None, f"network error: {e}")
            if attempt < attempts - 1:
                time.sleep(min(10.0, 2 ** (attempt + 1)))
                continue
            raise last_err from None
    assert last_err is not None
    raise last_err


def submit_i2v(first_frame_url: str, prompt: str, *,
               resolution: str = "720P", duration: int = 5,
               watermark: bool = False, seed: int | None = None) -> str:
    """提交「首帧→视频」任务，返回 task_id。"""
    if not first_frame_url:
        raise HappyHorseError(None, "first_frame_url required")
    url = f"{_endpoint()}/api/v1/services/aigc/video-generation/video-synthesis"
    params: dict[str, Any] = {
        "resolution": resolution,
        "duration": int(duration),
        "watermark": bool(watermark),
    }
    if seed is not None:
        params["seed"] = int(seed)
    payload = {
        "model": MODEL_I2V,
        "input": {
            "prompt": (prompt or "")[:2500],
            "media": [{"type": "first_frame", "url": first_frame_url}],
        },
        "parameters": params,
    }
    resp = _http("POST", url, body=payload,
                 extra_headers={"X-DashScope-Async": "enable"})
    out = resp.get("output") or {}
    tid = out.get("task_id")
    if not tid:
        raise HappyHorseError(None,
                              f"submit_i2v: missing task_id in response: {resp}",
                              request_id=resp.get("request_id", ""))
    _log.info("happyhorse submit task_id=%s status=%s", tid, out.get("task_status"))
    return str(tid)


def query(task_id: str) -> dict:
    """查询任务状态。返回 output dict（含 task_status / video_url 或 results 等）。

    对 i2v：output 里有 video_url（任务成功时）。
    对 t2i：output 里有 results=[{url, ...}]（任务成功时）。
    """
    if not task_id:
        raise HappyHorseError(None, "task_id required")
    url = f"{_endpoint()}/api/v1/tasks/{task_id}"
    resp = _http("GET", url)
    return resp.get("output") or {}


# ---------------------------------------------------------------------------
# DashScope WanX 文生图（用于生成 i2v 的首帧图）
# ---------------------------------------------------------------------------

def submit_t2i(prompt: str, *, size: str = "720*1280",
               n: int = 1, seed: int | None = None,
               negative_prompt: str = "",
               model: str | None = None) -> tuple[str, str]:
    """提交「文生图」异步任务，返回 (task_id, used_model)。

    DashScope 不同账户开放模型不同；若指定 model 失败，会按
    T2I_MODEL_CANDIDATES 顺序自动降级尝试。
    """
    if not prompt:
        raise HappyHorseError(None, "prompt required")
    url = f"{_endpoint()}/api/v1/services/aigc/text2image/image-synthesis"
    input_obj: dict[str, Any] = {"prompt": (prompt or "")[:2500]}
    if negative_prompt:
        input_obj["negative_prompt"] = negative_prompt[:500]
    params: dict[str, Any] = {"size": size, "n": int(n)}
    if seed is not None:
        params["seed"] = int(seed)
    candidates = [model] if model else list(T2I_MODEL_CANDIDATES)
    last_err: HappyHorseError | None = None
    for m in candidates:
        payload = {"model": m, "input": input_obj, "parameters": params}
        try:
            resp = _http("POST", url, body=payload,
                         extra_headers={"X-DashScope-Async": "enable"})
        except HappyHorseError as e:
            # 模型不可用 / 无权限 → 试下一个
            txt = str(e).lower()
            if any(k in txt for k in ("model", "permission", "not support",
                                       "not found", "noaccessperm")):
                _log.warning("t2i model=%s rejected: %s; try next", m, e)
                last_err = e
                continue
            raise
        out = resp.get("output") or {}
        tid = out.get("task_id")
        if not tid:
            last_err = HappyHorseError(
                None, f"submit_t2i: missing task_id in response: {resp}",
                request_id=resp.get("request_id", ""))
            continue
        _log.info("dashscope t2i submit task_id=%s model=%s", tid, m)
        return str(tid), m
    raise last_err or HappyHorseError(None, "all t2i model candidates failed")


def query_t2i_first_url(task_id: str) -> str:
    """查询 t2i 任务；成功且有 result 时返回第一张图的 URL，否则返回空串。"""
    out = query(task_id)
    status = (out.get("task_status") or "").upper()
    if status != STATUS_SUCCEEDED:
        return ""
    results = out.get("results") or []
    if not results:
        return ""
    first = results[0] or {}
    return first.get("url") or ""


def is_terminal(status: str) -> bool:
    s = (status or "").upper()
    return s in TERMINAL_OK or s in TERMINAL_FAIL


def is_success(status: str) -> bool:
    return (status or "").upper() in TERMINAL_OK


__all__ = [
    "HappyHorseError",
    "is_configured",
    "submit_i2v",
    "submit_t2i",
    "query",
    "query_t2i_first_url",
    "is_terminal",
    "is_success",
    "STATUS_PENDING", "STATUS_RUNNING", "STATUS_SUCCEEDED",
    "STATUS_FAILED", "STATUS_CANCELED", "STATUS_UNKNOWN",
    "MODEL_I2V", "T2I_MODEL_CANDIDATES",
]
