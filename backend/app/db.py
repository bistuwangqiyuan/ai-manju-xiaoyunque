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

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user: Mapped["User"] = relationship(back_populates="jobs")
    logs: Mapped[list["JobLog"]] = relationship(back_populates="job", cascade="all, delete-orphan", order_by="JobLog.id")
    versions: Mapped[list["JobVersion"]] = relationship(
        back_populates="job", cascade="all, delete-orphan", order_by="JobVersion.version_no"
    )


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
