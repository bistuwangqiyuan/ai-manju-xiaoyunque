"""
DB-polled worker loop.

In MVP mode (no API keys), simulates the 5-shell pipeline:
  shell1 编剧 → shell2 角色资产 → shell3 小云雀渲染 → shell4 质检 → shell5 后期

When real keys are present (settings.use_mock_worker == False), this is where the
real Python pipeline (src/shell1_*, src/shell2_*, ...) should be plugged in.
The integration shim is documented in `_run_real_pipeline`.
"""
from __future__ import annotations

import asyncio
import logging
import os
import random
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional

from sqlalchemy.orm import Session

from .db import Job, JobLog, SessionLocal
from .settings import settings

logger = logging.getLogger("xyq.worker")

# Five-shell mock pipeline stages
STAGES = [
    ("shell1_screenwriter", "编剧四模型协同抽取节拍", 12),
    ("shell2_character_assets", "角色资产三重 ID 锁注入", 22),
    ("shell3_skylark_engine", "小云雀 v2 整集级渲染", 65),
    ("shell4_qa_repair", "ArcFace 质检 + 五道修复防线", 85),
    ("shell5_post_production", "TTS / BGM / 字幕 / 4K 上扫", 100),
]


def _log(db: Session, job: Job, level: str, msg: str) -> None:
    db.add(JobLog(job_id=job.id, level=level, message=msg))
    job.updated_at = datetime.utcnow()
    db.commit()


def _set_progress(db: Session, job: Job, progress: int, status: Optional[str] = None) -> None:
    job.progress = max(0, min(100, progress))
    if status:
        job.status = status
    job.updated_at = datetime.utcnow()
    db.commit()


SAMPLE_VIDEO_URL = "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/BigBuckBunny.mp4"
SAMPLE_COVER_URL = "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/images/BigBuckBunny.jpg"


async def _run_mock(db: Session, job: Job) -> None:
    """Simulated 5-shell rendering with progressive logs."""
    _log(db, job, "INFO", f"[worker] pull job #{job.id} '{job.title}' ({job.episodes} 集)")
    await asyncio.sleep(0.5)

    for stage_id, stage_desc, target_prog in STAGES:
        # check cancellation
        db.refresh(job)
        if job.status == "cancelled":
            _log(db, job, "WARN", "任务被用户取消")
            return

        _log(db, job, "INFO", f"[{stage_id}] {stage_desc}")
        start_prog = job.progress
        steps = max(1, target_prog - start_prog)
        for i in range(steps):
            db.refresh(job)
            if job.status == "cancelled":
                _log(db, job, "WARN", "任务被用户取消")
                return
            await asyncio.sleep(random.uniform(0.25, 0.55))
            _set_progress(db, job, start_prog + i + 1, status="running" if job.status == "queued" else None)

        if stage_id == "shell3_skylark_engine":
            for ep in range(1, job.episodes + 1):
                _log(db, job, "INFO", f"  ↳ episode {ep:02d}/{job.episodes:02d} 渲染完成")
                await asyncio.sleep(0.1)

        if stage_id == "shell4_qa_repair":
            score = round(random.uniform(0.81, 0.93), 3)
            _log(db, job, "INFO", f"  ↳ ArcFace 跨集一致性得分 = {score} (阈值 0.80) ✅")

    # 写入产物（mock 用外链）
    job.result_url = SAMPLE_VIDEO_URL
    job.cover_url = SAMPLE_COVER_URL
    db.commit()
    _log(db, job, "INFO", "✅ 任务完成，可下载 MP4")
    _set_progress(db, job, 100, status="succeeded")


async def _run_real_pipeline(db: Session, job: Job) -> None:
    """
    生产模式接入点（需要 API Keys）。

    在这里把 src/shell1_*, src/shell2_*, ..., src/shell5_* 的 Python 流水线串起来：
        from src.shell1_screenwriter import run as run_shell1
        from src.shell3_skylark_engine import render_episode
        ...

    建议用 asyncio.to_thread() 把同步阻塞代码包起来，渲染期间定时回写
    job.progress / JobLog 让前端能看到进度。

    成果文件应该上传到 S3/R2（settings.S3_*）或落地到 settings.STORAGE_DIR，
    然后把可访问的 URL 写到 job.result_url / job.cover_url。
    """
    _log(db, job, "ERROR", "真实流水线尚未接入。请在 backend/app/worker.py 中实现 _run_real_pipeline()")
    _log(db, job, "INFO", "降级到 mock 渲染流程，以便联调")
    await _run_mock(db, job)


async def _process_one(job_id: int) -> None:
    db = SessionLocal()
    try:
        job = db.get(Job, job_id)
        if not job:
            return
        try:
            if settings.use_mock_worker:
                await _run_mock(db, job)
            else:
                await _run_real_pipeline(db, job)
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.exception("Job %s failed", job_id)
            db.refresh(job)
            job.error = str(e)[:2000]
            job.status = "failed"
            db.add(JobLog(job_id=job.id, level="ERROR", message=f"渲染失败: {e}"))
            db.commit()
    finally:
        db.close()


async def worker_loop() -> None:
    """Single-process polling loop. For higher concurrency, run multiple worker
    instances pointing at the same DB (each will pick up a different queued job
    via the row-level claim below)."""
    logger.info("Worker loop started (poll=%.1fs, mock=%s)",
                settings.WORKER_POLL_INTERVAL, settings.use_mock_worker)
    while True:
        try:
            # Atomically claim one queued job
            db = SessionLocal()
            try:
                q = db.query(Job).filter(Job.status == "queued").order_by(Job.id.asc())
                if db.bind.dialect.name != "sqlite":
                    q = q.with_for_update(skip_locked=True)
                job = q.first()
                if not job:
                    await asyncio.sleep(settings.WORKER_POLL_INTERVAL)
                    continue
                job.status = "running"
                db.commit()
                job_id = job.id
            finally:
                db.close()

            await _process_one(job_id)
        except asyncio.CancelledError:
            logger.info("Worker loop cancelled")
            break
        except Exception:
            logger.exception("Worker loop error")
            await asyncio.sleep(settings.WORKER_POLL_INTERVAL)


__all__ = ["worker_loop"]
