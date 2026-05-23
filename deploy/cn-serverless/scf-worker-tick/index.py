"""
腾讯云 SCF 函数 · 定时唤醒 CloudBase 处理排队任务

触发方式: 定时触发器 (Cron 表达式: `* * * * * * *` 每秒 / 推荐 `*/1 * * * *` 每分钟)

环境变量:
  BACKEND_URL          https://your-service-xxxxx.ap-shanghai.tcbgateway.com
  INTERNAL_API_SECRET  与 backend 同一 secret
  MAX_JOBS             单次最多处理几个任务 (默认 3)
  MAX_SECONDS          单次最长处理秒 (默认 50, 留 10s 给冷启动)
  WAKE_ON_EMPTY        队列为空时是否仍 ping 一下 backend 保持热身 (默认 1)

返回:
  - 成功: {"ok": True, "processed": N, "remaining": M, "elapsed_sec": X}
  - 失败: {"ok": False, "error": "..."}
"""
from __future__ import annotations

import json
import os
import urllib.request
import urllib.error


def _post(url: str, data: dict, headers: dict, timeout: float = 55.0) -> dict:
    body = json.dumps(data).encode("utf-8")
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read().decode("utf-8")
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return {"raw": raw, "status": resp.status}


def _get(url: str, headers: dict, timeout: float = 10.0) -> dict:
    req = urllib.request.Request(url, headers=headers, method="GET")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read().decode("utf-8")
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return {"raw": raw, "status": resp.status}


def main_handler(event, context):
    backend_url = os.environ.get("BACKEND_URL", "").rstrip("/")
    secret = os.environ.get("INTERNAL_API_SECRET", "").strip()
    max_jobs = int(os.environ.get("MAX_JOBS", "3"))
    max_seconds = float(os.environ.get("MAX_SECONDS", "50"))
    wake_on_empty = os.environ.get("WAKE_ON_EMPTY", "1").strip() not in {"0", "false", "no"}

    if not backend_url or not secret:
        return {"ok": False, "error": "BACKEND_URL or INTERNAL_API_SECRET not set"}

    headers = {
        "Content-Type": "application/json",
        "X-Internal-Secret": secret,
    }

    try:
        result = _post(
            f"{backend_url}/api/internal/worker/tick",
            {"max_jobs": max_jobs, "max_seconds": max_seconds},
            headers,
            timeout=max_seconds + 5,
        )
        if result.get("remaining_queued", 0) == 0 and not wake_on_empty:
            return {"ok": True, **result, "wake": False}
        # 队列还有积压 → 主动再 ping 一次防止 CloudBase 缩容到 0
        try:
            _get(f"{backend_url}/api/internal/worker/ping", headers, timeout=5)
        except Exception:
            pass
        return {"ok": True, **result, "wake": True}

    except urllib.error.HTTPError as e:
        body = ""
        try:
            body = e.read().decode("utf-8")[:300]
        except Exception:
            pass
        return {"ok": False, "error": f"HTTP {e.code}: {body}"}
    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}
