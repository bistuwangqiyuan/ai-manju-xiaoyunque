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
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


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
