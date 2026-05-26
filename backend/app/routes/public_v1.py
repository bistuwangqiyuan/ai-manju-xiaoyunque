"""V10 §11 — Public /api/v1 surface (auth via X-API-Key).

This is the SDK-facing API. It accepts a Bearer ``X-API-Key`` header,
resolves the org via :func:`src.enterprise.api_keys.lookup_key`, enforces
the per-key rate limit, then forwards to the same business logic the
dashboard uses.

Exposed routes:
    POST /api/v1/jobs              create a job
    GET  /api/v1/jobs/{id}         fetch status / outputs
    GET  /api/v1/jobs/{id}/shots   per-shot status
    POST /api/v1/jobs/{id}/cancel  cancel
    GET  /api/v1/usage             current org usage rollup
    GET  /api/v1/me                identify the calling key

All responses include ``X-Org-Id`` and ``X-RateLimit-Remaining`` headers.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.enterprise.api_keys import lookup_key
from src.enterprise.rate_limit import RateLimitExceeded, enforce

from ..db import ApiKey, Job, OrgUsage, User, get_db
from ..schemas import JobCreateIn, job_to_out


router = APIRouter(prefix="/api/v1", tags=["public-v1"])


class _AuthedRequest:
    def __init__(self, api_key: ApiKey, owner: User | None):
        self.api_key = api_key
        self.org_id = api_key.org_id
        self.owner = owner


def authed_key(
    response: Response,
    request: Request,
    db: Session = Depends(get_db),
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
) -> _AuthedRequest:
    if not x_api_key:
        raise HTTPException(status_code=401, detail="X-API-Key header required")
    row = lookup_key(db, ApiKey, x_api_key)
    if row is None:
        raise HTTPException(status_code=401, detail="invalid api key")
    bucket_key = f"apikey:{row.id}"
    try:
        enforce(bucket_key, per_min=row.rate_per_min)
    except RateLimitExceeded as exc:
        response.headers["Retry-After"] = str(int(exc.retry_after_seconds) + 1)
        raise HTTPException(
            status_code=429,
            detail=f"rate limit exceeded; retry in {exc.retry_after_seconds:.1f}s",
        )
    # Update usage
    row.monthly_used_calls = (row.monthly_used_calls or 0) + 1
    row.last_used_at = datetime.utcnow()
    db.commit()
    owner = db.query(User).filter(User.id == row.issued_by_user_id).first()
    response.headers["X-Org-Id"] = str(row.org_id)
    response.headers["X-RateLimit-Limit"] = str(row.rate_per_min)
    response.headers["X-Quota-Monthly"] = str(row.monthly_quota_calls)
    response.headers["X-Quota-Used"] = str(row.monthly_used_calls)
    return _AuthedRequest(row, owner)


# ---------- jobs ----------

@router.post("/jobs", status_code=202)
def v1_create_job(
    body: JobCreateIn,
    ctx: _AuthedRequest = Depends(authed_key),
    db: Session = Depends(get_db),
):
    owner_id = ctx.owner.id if ctx.owner is not None else ctx.api_key.issued_by_user_id
    if owner_id is None:
        raise HTTPException(status_code=400, detail="orphan api key (no owner)")
    job = Job(
        user_id=owner_id,
        org_id=ctx.org_id,
        title=body.title or "API job",
        status="pending",
        genre=body.genre or "ancient",
        mode=body.mode or "excerpt",
        novel_excerpt=body.novel_excerpt or "",
        theme=body.theme or "",
        episodes=body.episodes or 1,
        language=body.language or "Chinese",
        aspect_ratio=body.aspect_ratio or "9:16",
        resolution=body.resolution or "1080p",
        fps=body.fps or 24,
        duration_per_episode_s=body.duration_per_episode_s or 80,
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job_to_out(job)


@router.get("/jobs/{job_id}")
def v1_get_job(
    job_id: int,
    ctx: _AuthedRequest = Depends(authed_key),
    db: Session = Depends(get_db),
):
    job = db.query(Job).filter(Job.id == job_id, Job.org_id == ctx.org_id).first()
    if job is None:
        raise HTTPException(status_code=404, detail="job not found in your org")
    return job_to_out(job)


@router.get("/jobs/{job_id}/shots")
def v1_job_shots(
    job_id: int,
    ctx: _AuthedRequest = Depends(authed_key),
    db: Session = Depends(get_db),
):
    from ..db import Shot
    job = db.query(Job).filter(Job.id == job_id, Job.org_id == ctx.org_id).first()
    if job is None:
        raise HTTPException(status_code=404, detail="job not found")
    shots = db.query(Shot).filter(Shot.job_id == job_id).order_by(Shot.shot_id).all()
    return {"job_id": job_id, "shots": [
        {"shot_id": s.shot_id, "episode_id": s.episode_id,
         "status": s.status, "duration_s": s.duration_s,
         "result_url": s.result_url, "shot_type": s.shot_type}
        for s in shots
    ]}


@router.post("/jobs/{job_id}/cancel")
def v1_cancel_job(
    job_id: int,
    ctx: _AuthedRequest = Depends(authed_key),
    db: Session = Depends(get_db),
):
    job = db.query(Job).filter(Job.id == job_id, Job.org_id == ctx.org_id).first()
    if job is None:
        raise HTTPException(status_code=404, detail="job not found")
    if job.status in ("succeeded", "failed", "cancelled"):
        return {"id": job.id, "status": job.status, "noop": True}
    job.status = "cancelled"
    db.commit()
    return {"id": job.id, "status": "cancelled"}


@router.get("/usage")
def v1_usage(
    ctx: _AuthedRequest = Depends(authed_key),
    db: Session = Depends(get_db),
):
    from src.enterprise.usage import usage_summary
    return usage_summary(db, OrgUsage, org_id=ctx.org_id, days=30)


@router.get("/me")
def v1_me(ctx: _AuthedRequest = Depends(authed_key)) -> dict[str, Any]:
    return {
        "key_id": ctx.api_key.id,
        "key_prefix": ctx.api_key.prefix,
        "org_id": ctx.org_id,
        "name": ctx.api_key.name,
        "scopes": ctx.api_key.scopes.split(",") if ctx.api_key.scopes else [],
        "rate_per_min": ctx.api_key.rate_per_min,
        "monthly_quota_calls": ctx.api_key.monthly_quota_calls,
        "monthly_used_calls": ctx.api_key.monthly_used_calls,
    }
