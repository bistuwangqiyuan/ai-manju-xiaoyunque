from __future__ import annotations

from datetime import datetime
from typing import Generator

from sqlalchemy import (
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

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user: Mapped["User"] = relationship(back_populates="jobs")
    logs: Mapped[list["JobLog"]] = relationship(back_populates="job", cascade="all, delete-orphan", order_by="JobLog.id")


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


def init_db() -> None:
    Base.metadata.create_all(bind=engine)
