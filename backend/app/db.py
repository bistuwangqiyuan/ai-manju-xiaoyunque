from __future__ import annotations

from datetime import datetime
from typing import Generator

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    create_engine,
)
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    Session,
    mapped_column,
    relationship,
    sessionmaker,
)

from .settings import settings


class Base(DeclarativeBase):
    pass


def _engine():
    url = settings.DATABASE_URL
    # Vercel/Heroku 给的连接串常常是 postgres://，SQLAlchemy 2.x 只认 postgresql://
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://") :]

    kwargs: dict = {"future": True}
    if url.startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False}
    else:
        # Neon / Vercel Postgres / Railway Postgres 等 serverless Postgres
        # 会主动断开空闲连接，pool_pre_ping 在每次借出连接前发一个 SELECT 1 探活
        kwargs["pool_pre_ping"] = True
        # 连接复用 5 分钟后强制重建，避开 PgBouncer 的空闲断连
        kwargs["pool_recycle"] = 300
    return create_engine(url, **kwargs)


engine = _engine()
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False, future=True)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# --- Models ---


class User(Base):
    __tablename__ = "xyq_users"  # 前缀避开 Vercel/Neon 自带的 users 表

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    credits_cents: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    # 用户等级：free / pro / studio / admin
    tier: Mapped[str] = mapped_column(String(20), default="free", nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    jobs: Mapped[list["Job"]] = relationship(back_populates="user", cascade="all, delete-orphan")


class Job(Base):
    __tablename__ = "xyq_jobs"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("xyq_users.id", ondelete="CASCADE"), index=True)

    title: Mapped[str] = mapped_column(String(120), default="未命名漫剧")
    status: Mapped[str] = mapped_column(String(20), default="queued", index=True)  # queued/running/succeeded/failed/cancelled
    progress: Mapped[int] = mapped_column(Integer, default=0)
    cost_cents: Mapped[int] = mapped_column(Integer, default=0)
    episodes: Mapped[int] = mapped_column(Integer, default=1)
    novel_excerpt: Mapped[str] = mapped_column(Text, default="")
    style: Mapped[str] = mapped_column(String(60), default="ancient_3d_guoman")
    genre: Mapped[str] = mapped_column(String(40), default="ancient", nullable=False)
    mode: Mapped[str] = mapped_column(String(20), default="excerpt", nullable=False)  # excerpt|theme|novel
    theme: Mapped[str | None] = mapped_column(Text, nullable=True)
    language: Mapped[str] = mapped_column(String(20), default="Chinese", nullable=False)
    result_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    cover_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    # 质量评分（满分 100，目标 ≥ 90）
    quality_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # JSON 字符串：{"consistency": 92, "aesthetic": 88, ...}
    quality_breakdown: Mapped[str | None] = mapped_column(Text, nullable=True)
    quality_retries: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # 6-step workflow (流程和需求.docx)
    current_step: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    step_artifacts: Mapped[str | None] = mapped_column(Text, nullable=True)
    pipeline_version: Mapped[str] = mapped_column(String(20), default="v6", nullable=False)
    scores_7d: Mapped[str | None] = mapped_column(Text, nullable=True)
    human_approved: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # V10 §1.2 产出规格
    aspect_ratio: Mapped[str] = mapped_column(String(10), default="9:16", nullable=False)
    resolution: Mapped[str] = mapped_column(String(10), default="1080p", nullable=False)
    fps: Mapped[int] = mapped_column(Integer, default=24, nullable=False)
    duration_per_episode_s: Mapped[int] = mapped_column(Integer, default=80, nullable=False)
    # V10 §1.1 自定义画风
    custom_style_id: Mapped[str | None] = mapped_column(String(60), nullable=True)
    # V10 §1.3 / 9.1 / 9.4
    ui_mode: Mapped[str] = mapped_column(String(10), default="wizard", nullable=False)
    confirm_required_at_steps_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("xyq_jobs.id"), nullable=True)
    is_draft: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    template_id: Mapped[str | None] = mapped_column(String(60), nullable=True)
    # V10 §9.6 Org multi-tenant (nullable for personal tier)
    org_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user: Mapped["User"] = relationship(back_populates="jobs")
    logs: Mapped[list["JobLog"]] = relationship(back_populates="job", cascade="all, delete-orphan", order_by="JobLog.id")
    versions: Mapped[list["JobVersion"]] = relationship(
        back_populates="job", cascade="all, delete-orphan", order_by="JobVersion.version_no"
    )
    shots: Mapped[list["Shot"]] = relationship(
        back_populates="job", cascade="all, delete-orphan", order_by="Shot.shot_id"
    )


class Shot(Base):
    """One shot of one episode (镜头).

    Each shot can be individually rerolled, scored on the 7 dims, and
    re-spliced into the master timeline.
    """

    __tablename__ = "xyq_shots"

    id: Mapped[int] = mapped_column(primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("xyq_jobs.id", ondelete="CASCADE"), index=True)
    episode_id: Mapped[str] = mapped_column(String(20), default="ep01", index=True)
    shot_id: Mapped[int] = mapped_column(Integer, default=1, index=True)
    duration_s: Mapped[float] = mapped_column(default=3.0, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    shot_type: Mapped[str] = mapped_column(String(20), default="medium")
    status: Mapped[str] = mapped_column(String(20), default="queued", index=True)
    result_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    canonical_image_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    score_7d_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    overall_score: Mapped[float | None] = mapped_column(nullable=True)
    passed: Mapped[bool] = mapped_column(Boolean, default=False)
    repair_iters: Mapped[int] = mapped_column(Integer, default=0)
    repair_routes_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    feedback: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    job: Mapped["Job"] = relationship(back_populates="shots")


class Batch(Base):
    """Batch 转绘 (multi-file redraw) job."""

    __tablename__ = "xyq_batches"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("xyq_users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(120), default="批量转绘")
    style: Mapped[str] = mapped_column(String(40), default="ancient_3d_guoman")
    genre: Mapped[str] = mapped_column(String(40), default="ancient")
    aspect_ratio: Mapped[str] = mapped_column(String(10), default="9:16")
    status: Mapped[str] = mapped_column(String(20), default="queued", index=True)
    total_items: Mapped[int] = mapped_column(Integer, default=0)
    finished_items: Mapped[int] = mapped_column(Integer, default=0)
    params_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    items: Mapped[list["BatchItem"]] = relationship(
        back_populates="batch", cascade="all, delete-orphan", order_by="BatchItem.id"
    )


class BatchItem(Base):
    __tablename__ = "xyq_batch_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    batch_id: Mapped[int] = mapped_column(ForeignKey("xyq_batches.id", ondelete="CASCADE"), index=True)
    source_url: Mapped[str] = mapped_column(String(500), default="")
    result_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    params_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="queued", index=True)
    score_7d_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    overall_score: Mapped[float | None] = mapped_column(nullable=True)
    passed: Mapped[bool] = mapped_column(Boolean, default=False)
    repair_iters: Mapped[int] = mapped_column(Integer, default=0)
    feedback: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    batch: Mapped["Batch"] = relationship(back_populates="items")


class JobVersion(Base):
    """Version history for generate→evaluate→fix loops."""

    __tablename__ = "xyq_job_versions"

    id: Mapped[int] = mapped_column(primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("xyq_jobs.id", ondelete="CASCADE"), index=True)
    version_no: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    params_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    scores_7d_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    quality_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    result_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    cover_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    job: Mapped["Job"] = relationship(back_populates="versions")


class JobLog(Base):
    __tablename__ = "xyq_job_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("xyq_jobs.id", ondelete="CASCADE"), index=True)
    ts: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    level: Mapped[str] = mapped_column(String(10), default="INFO")
    message: Mapped[str] = mapped_column(Text, default="")

    job: Mapped["Job"] = relationship(back_populates="logs")


class Payment(Base):
    __tablename__ = "xyq_payments"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("xyq_users.id", ondelete="CASCADE"), index=True)
    amount_cents: Mapped[int] = mapped_column(Integer, default=0)
    plan: Mapped[str] = mapped_column(String(40), default="")
    provider: Mapped[str] = mapped_column(String(20), default="mock")
    external_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="paid")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


# ===========================================================================
# V10 §3 — Text creation layer tables
# ===========================================================================
class Novel(Base):
    __tablename__ = "xyq_novels"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("xyq_users.id", ondelete="CASCADE"), index=True)
    org_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    title: Mapped[str] = mapped_column(String(200), default="未命名小说")
    source: Mapped[str] = mapped_column(String(20), default="upload")  # upload | theme | continuation
    source_format: Mapped[str] = mapped_column(String(10), default="txt")  # txt | docx | pdf
    language: Mapped[str] = mapped_column(String(20), default="Chinese")
    genre: Mapped[str] = mapped_column(String(40), default="ancient")
    total_chars: Mapped[int] = mapped_column(Integer, default=0)
    target_total_chars: Mapped[int] = mapped_column(Integer, default=0)  # for continuation control
    chapter_target_chars: Mapped[int] = mapped_column(Integer, default=3000)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_text: Mapped[str | None] = mapped_column(Text, nullable=True)  # original imported text
    sensitive_review: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON
    copyright_check: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON
    plot_graph_json: Mapped[str | None] = mapped_column(Text, nullable=True)  # serialised plot_state graph
    status: Mapped[str] = mapped_column(String(20), default="draft", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    chapters: Mapped[list["Chapter"]] = relationship(
        back_populates="novel", cascade="all, delete-orphan", order_by="Chapter.index"
    )


class Chapter(Base):
    __tablename__ = "xyq_chapters"

    id: Mapped[int] = mapped_column(primary_key=True)
    novel_id: Mapped[int] = mapped_column(ForeignKey("xyq_novels.id", ondelete="CASCADE"), index=True)
    index: Mapped[int] = mapped_column(Integer, default=1, index=True)
    title: Mapped[str] = mapped_column(String(200), default="")
    body: Mapped[str] = mapped_column(Text, default="")
    chars: Mapped[int] = mapped_column(Integer, default=0)
    pov: Mapped[str | None] = mapped_column(String(40), nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    plot_beats_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="draft")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    novel: Mapped["Novel"] = relationship(back_populates="chapters")


class Screenplay(Base):
    __tablename__ = "xyq_screenplays"

    id: Mapped[int] = mapped_column(primary_key=True)
    novel_id: Mapped[int | None] = mapped_column(ForeignKey("xyq_novels.id", ondelete="SET NULL"), nullable=True, index=True)
    job_id: Mapped[int | None] = mapped_column(ForeignKey("xyq_jobs.id", ondelete="SET NULL"), nullable=True, index=True)
    title: Mapped[str] = mapped_column(String(200), default="未命名剧本")
    episode_count: Mapped[int] = mapped_column(Integer, default=10)
    target_duration_per_episode_s: Mapped[int] = mapped_column(Integer, default=80)
    language: Mapped[str] = mapped_column(String(20), default="Chinese")
    formatted_md: Mapped[str | None] = mapped_column(Text, nullable=True)  # full Markdown screenplay
    characters_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    polish_status: Mapped[str] = mapped_column(String(20), default="draft")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    scenes: Mapped[list["Scene"]] = relationship(
        back_populates="screenplay", cascade="all, delete-orphan", order_by="Scene.episode,Scene.index"
    )


class Scene(Base):
    __tablename__ = "xyq_scenes"

    id: Mapped[int] = mapped_column(primary_key=True)
    screenplay_id: Mapped[int] = mapped_column(ForeignKey("xyq_screenplays.id", ondelete="CASCADE"), index=True)
    episode: Mapped[int] = mapped_column(Integer, default=1, index=True)
    index: Mapped[int] = mapped_column(Integer, default=1)
    heading: Mapped[str] = mapped_column(String(200), default="")
    location: Mapped[str | None] = mapped_column(String(120), nullable=True)
    time_of_day: Mapped[str | None] = mapped_column(String(40), nullable=True)
    atmosphere: Mapped[str | None] = mapped_column(String(60), nullable=True)
    action_text: Mapped[str] = mapped_column(Text, default="")
    dialogue_json: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON list of {speaker, line, emotion}
    pov_character: Mapped[str | None] = mapped_column(String(60), nullable=True)
    duration_estimate_s: Mapped[int] = mapped_column(Integer, default=8)

    screenplay: Mapped["Screenplay"] = relationship(back_populates="scenes")


class TranslatedNovel(Base):
    __tablename__ = "xyq_translated_novels"

    id: Mapped[int] = mapped_column(primary_key=True)
    novel_id: Mapped[int] = mapped_column(ForeignKey("xyq_novels.id", ondelete="CASCADE"), index=True)
    language: Mapped[str] = mapped_column(String(20), default="English")
    translation_engine: Mapped[str] = mapped_column(String(40), default="claude-opus")
    body: Mapped[str] = mapped_column(Text, default="")
    glossary_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    quality_score: Mapped[float | None] = mapped_column(nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="draft")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


# ===========================================================================
# V10 §11 — Organization / team commercial layer
# ===========================================================================


class Organization(Base):
    """A team / company workspace.  All assets created by members are
    isolated by ``org_id``; quotas, billing and rate limits roll up here.
    """
    __tablename__ = "xyq_organizations"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    slug: Mapped[str] = mapped_column(String(80), unique=True, index=True, nullable=False)
    owner_user_id: Mapped[int] = mapped_column(ForeignKey("xyq_users.id", ondelete="CASCADE"), index=True)
    plan: Mapped[str] = mapped_column(String(20), default="team", nullable=False)  # team | enterprise
    seats_max: Mapped[int] = mapped_column(Integer, default=10, nullable=False)
    monthly_credits_cents: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    monthly_used_cents: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    sso_idp_url: Mapped[str | None] = mapped_column(String(400), nullable=True)  # SSO/OIDC P0
    private_deploy: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class OrgMember(Base):
    """An (Organization, User) membership with a role.

    Roles (see ``src.enterprise.rbac``):
        owner   — full control, billing, sso
        admin   — manage members + api keys
        editor  — create / edit / publish jobs
        viewer  — read-only
    """
    __tablename__ = "xyq_org_members"

    id: Mapped[int] = mapped_column(primary_key=True)
    org_id: Mapped[int] = mapped_column(ForeignKey("xyq_organizations.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("xyq_users.id", ondelete="CASCADE"), index=True)
    role: Mapped[str] = mapped_column(String(20), default="editor", nullable=False, index=True)
    joined_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    invited_by_user_id: Mapped[int | None] = mapped_column(Integer, nullable=True)


class ApiKey(Base):
    """Public API token; carries (org_id) so server-side authn maps to
    the right tenant + quota.

    The full secret is hashed at rest (SHA-256).  ``prefix`` is the first
    8 chars of the raw token — stored cleartext so the UI can list keys
    without persisting the full secret.
    """
    __tablename__ = "xyq_api_keys"

    id: Mapped[int] = mapped_column(primary_key=True)
    org_id: Mapped[int] = mapped_column(ForeignKey("xyq_organizations.id", ondelete="CASCADE"), index=True)
    issued_by_user_id: Mapped[int] = mapped_column(ForeignKey("xyq_users.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(80), default="default")
    prefix: Mapped[str] = mapped_column(String(16), unique=True, index=True, nullable=False)
    secret_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    scopes: Mapped[str] = mapped_column(String(400), default="job:write,job:read")
    rate_per_min: Mapped[int] = mapped_column(Integer, default=60, nullable=False)
    monthly_quota_calls: Mapped[int] = mapped_column(Integer, default=10000, nullable=False)
    monthly_used_calls: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)


class OrgUsage(Base):
    """Daily aggregated usage counters; powers Grafana + invoices."""
    __tablename__ = "xyq_org_usage"

    id: Mapped[int] = mapped_column(primary_key=True)
    org_id: Mapped[int] = mapped_column(ForeignKey("xyq_organizations.id", ondelete="CASCADE"), index=True)
    day: Mapped[str] = mapped_column(String(10), index=True, nullable=False)  # YYYY-MM-DD UTC
    jobs_count: Mapped[int] = mapped_column(Integer, default=0)
    episodes_count: Mapped[int] = mapped_column(Integer, default=0)
    minutes_rendered: Mapped[float] = mapped_column(default=0.0)
    cost_cents: Mapped[int] = mapped_column(Integer, default=0)
    api_calls: Mapped[int] = mapped_column(Integer, default=0)
    api_4xx: Mapped[int] = mapped_column(Integer, default=0)
    api_5xx: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class OrgInvite(Base):
    """Pending email invites; one-shot consumable token."""
    __tablename__ = "xyq_org_invites"

    id: Mapped[int] = mapped_column(primary_key=True)
    org_id: Mapped[int] = mapped_column(ForeignKey("xyq_organizations.id", ondelete="CASCADE"), index=True)
    email: Mapped[str] = mapped_column(String(200), index=True, nullable=False)
    role: Mapped[str] = mapped_column(String(20), default="editor")
    token: Mapped[str] = mapped_column(String(80), unique=True, index=True, nullable=False)
    invited_by_user_id: Mapped[int] = mapped_column(ForeignKey("xyq_users.id", ondelete="CASCADE"))
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    accepted_by_user_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


def _apply_simple_migrations(connection) -> None:
    """
    幂等小迁移：对于新加的列，自动 ALTER TABLE ADD COLUMN IF NOT EXISTS。
    避免每次 schema 演进都要手动 drop table。

    只支持 Postgres（IF NOT EXISTS 需要 Postgres ≥ 9.6）。
    SQLite 直接跳过（dev DB 反正会重建）。
    """
    from sqlalchemy import text
    dialect = connection.dialect.name
    if dialect != "postgresql":
        return

    # (table_name, column_name, column_type_sql)
    migrations = [
        ("xyq_users", "tier", "VARCHAR(20) DEFAULT 'free' NOT NULL"),
        ("xyq_jobs", "quality_score", "INTEGER"),
        ("xyq_jobs", "quality_breakdown", "TEXT"),
        ("xyq_jobs", "quality_retries", "INTEGER DEFAULT 0 NOT NULL"),
        ("xyq_jobs", "current_step", "INTEGER DEFAULT 0 NOT NULL"),
        ("xyq_jobs", "step_artifacts", "TEXT"),
        ("xyq_jobs", "pipeline_version", "VARCHAR(20) DEFAULT 'v6' NOT NULL"),
        ("xyq_jobs", "scores_7d", "TEXT"),
        ("xyq_jobs", "human_approved", "BOOLEAN DEFAULT FALSE NOT NULL"),
        ("xyq_jobs", "genre", "VARCHAR(40) DEFAULT 'ancient' NOT NULL"),
        ("xyq_jobs", "mode", "VARCHAR(20) DEFAULT 'excerpt' NOT NULL"),
        ("xyq_jobs", "theme", "TEXT"),
        ("xyq_jobs", "language", "VARCHAR(20) DEFAULT 'Chinese' NOT NULL"),
        # V10 additions
        ("xyq_jobs", "aspect_ratio", "VARCHAR(10) DEFAULT '9:16' NOT NULL"),
        ("xyq_jobs", "resolution", "VARCHAR(10) DEFAULT '1080p' NOT NULL"),
        ("xyq_jobs", "fps", "INTEGER DEFAULT 24 NOT NULL"),
        ("xyq_jobs", "duration_per_episode_s", "INTEGER DEFAULT 80 NOT NULL"),
        ("xyq_jobs", "custom_style_id", "VARCHAR(60)"),
        ("xyq_jobs", "ui_mode", "VARCHAR(10) DEFAULT 'wizard' NOT NULL"),
        ("xyq_jobs", "confirm_required_at_steps_json", "TEXT"),
        ("xyq_jobs", "parent_id", "INTEGER"),
        ("xyq_jobs", "is_draft", "BOOLEAN DEFAULT FALSE NOT NULL"),
        ("xyq_jobs", "template_id", "VARCHAR(60)"),
        ("xyq_jobs", "org_id", "INTEGER"),
    ]
    for table, col, coltype in migrations:
        try:
            connection.execute(text(
                f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {col} {coltype}"
            ))
        except Exception as e:
            # 表可能还没建，create_all 之后会建好，这里忽略即可
            import logging
            logging.getLogger("xyq.db").warning("migration %s.%s skipped: %s", table, col, e)
    connection.commit()


def init_db() -> None:
    Base.metadata.create_all(bind=engine)
    # 在 create_all 之后跑迁移：如果是新装库，create_all 已带新列；
    # 如果是旧库，create_all 跳过已存在的表，这里负责把缺的列补上
    with engine.connect() as conn:
        _apply_simple_migrations(conn)
