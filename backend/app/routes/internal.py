"""
Serverless-only internal endpoints.

These are invoked by:
  - 腾讯云 SCF 定时触发器 (POST /api/internal/worker/tick every 60s)
  - 阿里云 函数计算 定时触发 (same shape)
  - Local cron / GitHub Actions / curl

Auth: a single shared secret in `X-Internal-Secret` header,
configured via env `INTERNAL_API_SECRET`. If empty, endpoints 503.
Use a random 48-byte token (the same one SCF stores in env).
"""
from __future__ import annotations

import asyncio
import hmac
import logging
import os

from fastapi import APIRouter, Header, HTTPException, status
from pydantic import BaseModel

from ..worker import tick_once

router = APIRouter(prefix="/internal", tags=["internal"])
logger = logging.getLogger("xyq.internal")


class TickRequest(BaseModel):
    max_jobs: int = 1
    max_seconds: float = 60.0


def _require_secret(header_secret: str | None) -> None:
    expected = os.environ.get("INTERNAL_API_SECRET", "").strip()
    if not expected:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="INTERNAL_API_SECRET not configured",
        )
    if not header_secret or not hmac.compare_digest(header_secret, expected):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="invalid internal secret",
        )


@router.post("/worker/tick")
async def worker_tick(
    body: TickRequest | None = None,
    x_internal_secret: str | None = Header(default=None),
) -> dict:
    """Process up to N queued jobs in a single invocation."""
    _require_secret(x_internal_secret)
    req = body or TickRequest()
    result = await tick_once(max_jobs=req.max_jobs, max_seconds=req.max_seconds)
    logger.info("worker_tick processed=%s remaining=%s elapsed=%.2fs",
                result["processed"], result["remaining_queued"], result["elapsed_sec"])
    return result


@router.get("/worker/ping")
async def worker_ping(x_internal_secret: str | None = Header(default=None)) -> dict:
    """Lightweight wake-up; just returns ok. Useful when CloudBase is scale-to-zero."""
    _require_secret(x_internal_secret)
    return {"ok": True, "service": "xiaoyunque-worker"}
