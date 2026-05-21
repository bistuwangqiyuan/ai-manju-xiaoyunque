from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, EmailStr, Field


class SignupIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    id: int
    email: str
    credits_cents: int
    tier: str = "free"
    created_at: datetime

    class Config:
        from_attributes = True


class AuthOut(BaseModel):
    token: str
    user: UserOut


class JobCreateIn(BaseModel):
    title: str = Field(default="未命名漫剧", max_length=120)
    novel_excerpt: str = Field(min_length=50, max_length=20000)
    style: str = Field(default="ancient_3d_guoman", max_length=60)
    episodes: int = Field(ge=1, le=10)


class JobOut(BaseModel):
    id: int
    title: str
    status: Literal["queued", "running", "succeeded", "failed", "cancelled"]
    progress: int
    cost_cents: int
    episodes: int
    novel_excerpt: str
    style: str
    result_url: Optional[str]
    cover_url: Optional[str]
    error: Optional[str]
    quality_score: Optional[int] = None
    quality_breakdown: Optional[dict] = None
    quality_retries: int = 0
    current_step: int = 0
    step_artifacts: Optional[dict] = None
    pipeline_version: str = "v6"
    scores_7d: Optional[dict] = None
    human_approved: bool = False
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


def _parse_json_field(raw: str | None) -> Optional[dict]:
    import json
    if not raw:
        return None
    try:
        return json.loads(raw)
    except Exception:
        return None


def job_to_out(job) -> "JobOut":
    """Convert SQLAlchemy Job → JobOut, parsing JSON fields."""
    return JobOut(
        id=job.id,
        title=job.title,
        status=job.status,
        progress=job.progress,
        cost_cents=job.cost_cents,
        episodes=job.episodes,
        novel_excerpt=job.novel_excerpt,
        style=job.style,
        result_url=job.result_url,
        cover_url=job.cover_url,
        error=job.error,
        quality_score=job.quality_score,
        quality_breakdown=_parse_json_field(job.quality_breakdown),
        quality_retries=job.quality_retries,
        current_step=getattr(job, "current_step", 0) or 0,
        step_artifacts=_parse_json_field(getattr(job, "step_artifacts", None)),
        pipeline_version=getattr(job, "pipeline_version", "v6") or "v6",
        scores_7d=_parse_json_field(getattr(job, "scores_7d", None)),
        human_approved=bool(getattr(job, "human_approved", False)),
        created_at=job.created_at,
        updated_at=job.updated_at,
    )


class JobVersionOut(BaseModel):
    id: int
    version_no: int
    quality_score: Optional[int]
    scores_7d: Optional[dict]
    result_url: Optional[str]
    cover_url: Optional[str]
    notes: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class RerollIn(BaseModel):
    shot_id: Optional[str] = None


class JobLogOut(BaseModel):
    ts: datetime
    level: str
    message: str

    class Config:
        from_attributes = True


class CheckoutIn(BaseModel):
    plan: Literal["starter", "series", "studio"]


class CheckoutOut(BaseModel):
    url: str
    mocked: bool


class TopUpIn(BaseModel):
    amount_cents: int = Field(ge=100, le=1000000)
