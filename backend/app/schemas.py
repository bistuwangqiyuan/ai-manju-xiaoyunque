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
    # {consistency, aesthetic, fidelity, subtitle, pacing} 全部 0-100 整数
    quality_breakdown: Optional[dict] = None
    quality_retries: int = 0
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


def job_to_out(job) -> "JobOut":
    """Convert SQLAlchemy Job → JobOut, parsing quality_breakdown JSON string."""
    import json
    qb = None
    if job.quality_breakdown:
        try:
            qb = json.loads(job.quality_breakdown)
        except Exception:
            qb = None
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
        quality_breakdown=qb,
        quality_retries=job.quality_retries,
        created_at=job.created_at,
        updated_at=job.updated_at,
    )


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
