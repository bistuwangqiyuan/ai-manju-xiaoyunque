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
    novel_excerpt: str = Field(default="", max_length=200000)
    style: str = Field(default="ancient_3d_guoman", max_length=60)
    episodes: int = Field(ge=1, le=50)
    # New optional fields for multi-genre / theme generation / multilingual
    genre: str = Field(default="ancient", max_length=40)
    mode: Literal["excerpt", "theme", "novel"] = "excerpt"
    theme: Optional[str] = Field(default=None, max_length=400)
    language: str = Field(default="Chinese", max_length=20)
    # V10 §1.2 产出规格
    aspect_ratio: Literal["9:16", "16:9", "1:1"] = "9:16"
    resolution: Literal["1080p", "2k", "4k"] = "1080p"
    fps: Literal[24, 25, 30] = 24
    duration_per_episode_s: int = Field(default=80, ge=30, le=300)
    # V10 §1.1 自定义画风
    custom_style_id: Optional[str] = Field(default=None, max_length=60)
    # V10 §1.3 简易/专业模式（决定后端默认值是否覆盖）
    ui_mode: Literal["wizard", "pro"] = "wizard"


class JobOut(BaseModel):
    id: int
    title: str
    status: Literal["queued", "running", "succeeded", "failed", "cancelled", "paused"]
    progress: int
    cost_cents: int
    episodes: int
    novel_excerpt: str
    style: str
    genre: str = "ancient"
    mode: str = "excerpt"
    theme: Optional[str] = None
    language: str = "Chinese"
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
    # V10
    aspect_ratio: str = "9:16"
    resolution: str = "1080p"
    fps: int = 24
    duration_per_episode_s: int = 80
    custom_style_id: Optional[str] = None
    ui_mode: str = "wizard"
    parent_id: Optional[int] = None
    org_id: Optional[int] = None
    confirm_required_at_steps: Optional[list[int]] = None
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
        genre=getattr(job, "genre", "ancient") or "ancient",
        mode=getattr(job, "mode", "excerpt") or "excerpt",
        theme=getattr(job, "theme", None),
        language=getattr(job, "language", "Chinese") or "Chinese",
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
        aspect_ratio=getattr(job, "aspect_ratio", "9:16") or "9:16",
        resolution=getattr(job, "resolution", "1080p") or "1080p",
        fps=getattr(job, "fps", 24) or 24,
        duration_per_episode_s=getattr(job, "duration_per_episode_s", 80) or 80,
        custom_style_id=getattr(job, "custom_style_id", None),
        ui_mode=getattr(job, "ui_mode", "wizard") or "wizard",
        parent_id=getattr(job, "parent_id", None),
        org_id=getattr(job, "org_id", None),
        confirm_required_at_steps=_parse_json_field(getattr(job, "confirm_required_at_steps_json", None)),
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


# ---------------------------------------------------------------------
# Shot — per-shot detail for the storyboard / QA UI (requirement doc §自动修正)
# ---------------------------------------------------------------------


class ShotOut(BaseModel):
    id: int
    job_id: int
    episode_id: str
    shot_id: int
    duration_s: float
    description: Optional[str]
    shot_type: str
    status: str
    result_url: Optional[str]
    canonical_image_url: Optional[str]
    score_7d: Optional[dict] = None
    overall_score: Optional[float] = None
    passed: bool = False
    repair_iters: int = 0
    repair_routes: Optional[list[str]] = None
    feedback: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class ShotRepairIn(BaseModel):
    route: Optional[str] = Field(default=None, description="face_drift|costume_drift|...|auto")
    feedback: Optional[str] = Field(default=None, max_length=1000)


# ---------------------------------------------------------------------
# Genre templates (requirement doc §一)
# ---------------------------------------------------------------------


class GenreOut(BaseModel):
    id: str
    name_zh: str
    name_en: str
    description: str
    style_id: str
    aspect_ratio: str
    default_episodes: int
    sample_themes: list[str] = []
    preview_video_url: Optional[str] = None
    preview_cover_url: Optional[str] = None


# ---------------------------------------------------------------------
# Batch 转绘 (requirement doc §12)
# ---------------------------------------------------------------------


class BatchCreateIn(BaseModel):
    name: str = Field(default="批量转绘", max_length=120)
    style: str = Field(default="ancient_3d_guoman", max_length=60)
    genre: str = Field(default="ancient", max_length=40)
    aspect_ratio: str = Field(default="9:16", max_length=10)
    source_urls: list[str] = Field(default_factory=list, max_length=50)
    params: Optional[dict] = None


class BatchItemOut(BaseModel):
    id: int
    batch_id: int
    source_url: str
    result_url: Optional[str]
    params: Optional[dict] = None
    status: str
    score_7d: Optional[dict] = None
    overall_score: Optional[float] = None
    passed: bool = False
    repair_iters: int = 0
    feedback: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class BatchOut(BaseModel):
    id: int
    name: str
    style: str
    genre: str
    aspect_ratio: str
    status: str
    total_items: int
    finished_items: int
    params: Optional[dict] = None
    items: list[BatchItemOut] = []
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------
# Platform export (requirement doc §8)
# ---------------------------------------------------------------------


class ExportIn(BaseModel):
    platforms: list[Literal[
        "douyin", "kuaishou", "wechat_video", "xiaohongshu", "bilibili",
        "youtube_shorts",
    ]] = Field(default_factory=lambda: ["douyin"], max_length=10)
    add_watermark: bool = True
    account_handle: Optional[str] = Field(default=None, max_length=40)
    target_language: Optional[str] = Field(default=None)


class ExportOut(BaseModel):
    platform: str
    url: str
    cover_url: Optional[str] = None
    caption: Optional[str] = None
    hashtags: list[str] = []
    duration_s: Optional[float] = None
    width: Optional[int] = None
    height: Optional[int] = None


# ---------------------------------------------------------------------
# Marketing copy (requirement doc §8 文案配套)
# ---------------------------------------------------------------------


class MarketingOut(BaseModel):
    title: str
    summary: str
    hook_copy: str
    hashtags: list[str] = []
    language: str = "Chinese"


# ---------------------------------------------------------------------
# Advanced (continuation / restyle / interaction)
# ---------------------------------------------------------------------


class ContinueIn(BaseModel):
    extra_episodes: int = Field(default=1, ge=1, le=10)
    direction: Optional[str] = Field(default=None, max_length=400)


class RestyleIn(BaseModel):
    target: Literal["jpn_anime", "guoman", "realistic", "manhwa"] = "jpn_anime"


class TranslateIn(BaseModel):
    target_lang: Literal["en", "ja", "ko", "es", "fr", "de"] = "en"
    burn_subtitle: bool = True


# ---------------------------------------------------------------------
# Version mgmt
# ---------------------------------------------------------------------


class VersionRollbackIn(BaseModel):
    target_version_no: int = Field(ge=1)
    notes: Optional[str] = Field(default=None, max_length=400)
