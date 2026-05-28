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
    """查询任务状态。返回 output dict（含 task_status / video_url 等）。"""
    if not task_id:
        raise HappyHorseError(None, "task_id required")
    url = f"{_endpoint()}/api/v1/tasks/{task_id}"
    resp = _http("GET", url)
    return resp.get("output") or {}


def is_terminal(status: str) -> bool:
    s = (status or "").upper()
    return s in TERMINAL_OK or s in TERMINAL_FAIL


def is_success(status: str) -> bool:
    return (status or "").upper() in TERMINAL_OK


__all__ = [
    "HappyHorseError",
    "is_configured",
    "submit_i2v",
    "query",
    "is_terminal",
    "is_success",
    "STATUS_PENDING", "STATUS_RUNNING", "STATUS_SUCCEEDED",
    "STATUS_FAILED", "STATUS_CANCELED", "STATUS_UNKNOWN",
    "MODEL_I2V",
]
