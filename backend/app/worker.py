"""
DB-polled worker pool with quality scoring + auto-retry.

In MVP mode (no API keys), simulates the 5-shell pipeline:
  shell1 编剧 → shell2 角色资产 → shell3 小云雀渲染 → shell4 质检 → shell5 后期

The pool spawns settings.WORKER_CONCURRENCY parallel workers; they share the
DB queue and claim jobs atomically (Postgres uses SELECT ... FOR UPDATE SKIP
LOCKED; SQLite degrades to serial since it's single-writer anyway).

After a job finishes, the worker computes a quality_score (0-100). If the
score is below settings.QUALITY_PASS (default 90), it retries up to
settings.QUALITY_MAX_RETRIES times before declaring final.
"""
from __future__ import annotations

import asyncio
import json
import logging
import random
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from .db import Job, JobLog, SessionLocal
from .settings import settings

logger = logging.getLogger("xyq.worker")

# Five-shell mock pipeline stages (name, description, target progress %)
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


def _compute_quality(retry: int) -> tuple[int, dict]:
    """生成 5 维质量评分。重试次数越多分数趋势越高（修复发挥作用）。

    Returns (overall_score, breakdown_dict)
    """
    base_floor = 78 + retry * 4  # retry 0→78+, retry 1→82+, retry 2→86+
    base_ceil = 92 + retry * 2   # retry 0→92, retry 1→94, retry 2→96
    breakdown = {
        "consistency": random.randint(base_floor, min(98, base_ceil + 2)),
        "aesthetic":   random.randint(base_floor, min(98, base_ceil)),
        "fidelity":    random.randint(base_floor, min(98, base_ceil + 1)),
        "subtitle":    random.randint(min(95, base_floor + 5), 99),  # 字幕在 mock 里都很稳
        "pacing":      random.randint(base_floor, min(98, base_ceil)),
    }
    overall = int(round(sum(breakdown.values()) / len(breakdown)))
    return overall, breakdown


async def _run_mock(db: Session, job: Job) -> None:
    """Simulated 5-shell rendering with progressive logs + quality scoring."""
    _log(db, job, "INFO", f"[worker] pull job #{job.id} '{job.title}' ({job.episodes} 集)")
    await asyncio.sleep(0.5)

    attempt = job.quality_retries
    max_retries = settings.QUALITY_MAX_RETRIES
    pass_threshold = settings.QUALITY_PASS

    while True:
        if attempt > 0:
            _log(db, job, "INFO", f"⟳ 第 {attempt} 次质量重试 (上次评分 < {pass_threshold})")
            _set_progress(db, job, 0)  # reset progress for retry visualization

        for stage_id, stage_desc, target_prog in STAGES:
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
                await asyncio.sleep(random.uniform(0.15, 0.35))
                _set_progress(db, job, start_prog + i + 1, status="running" if job.status == "queued" else None)

            if stage_id == "shell3_skylark_engine":
                for ep in range(1, job.episodes + 1):
                    _log(db, job, "INFO", f"  ↳ episode {ep:02d}/{job.episodes:02d} 渲染完成")
                    await asyncio.sleep(0.05)

            if stage_id == "shell4_qa_repair":
                arcface = round(random.uniform(0.81, 0.95), 3)
                _log(db, job, "INFO", f"  ↳ ArcFace 跨集一致性 = {arcface} (阈值 0.80) ✅")

        # 质量评分阶段
        score, breakdown = _compute_quality(attempt)
        job.quality_score = score
        job.quality_breakdown = json.dumps(breakdown)
        job.quality_retries = attempt
        db.commit()

        _log(db, job, "INFO",
             f"📊 质量评分 = {score}/100"
             f" (一致性 {breakdown['consistency']} · "
             f"美学 {breakdown['aesthetic']} · "
             f"贴合 {breakdown['fidelity']} · "
             f"字幕 {breakdown['subtitle']} · "
             f"节奏 {breakdown['pacing']})")

        if score >= pass_threshold or attempt >= max_retries:
            break

        _log(db, job, "WARN", f"评分 {score} < {pass_threshold}，自动触发修复重试 ({attempt+1}/{max_retries})")
        attempt += 1

    # 最终产物
    job.result_url = SAMPLE_VIDEO_URL
    job.cover_url = SAMPLE_COVER_URL
    db.commit()

    if score >= pass_threshold:
        _log(db, job, "INFO", f"✅ 任务完成，质量 {score}/100 已达标，可下载 MP4")
    else:
        _log(db, job, "WARN", f"⚠ 重试 {attempt} 次后最终评分 {score}/100 仍未达 {pass_threshold}，已交付当前最优版本")

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

    质量评分：用 InsightFace 算 ArcFace 一致性，调 Gemini Vision 评美学等，
    填到 job.quality_score / quality_breakdown。
    """
    _log(db, job, "ERROR", "真实流水线尚未接入。请在 backend/app/worker.py 中实现 _run_real_pipeline()")
    _log(db, job, "INFO", "降级到 mock 渲染流程")
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


async def _claim_one() -> Optional[int]:
    """Atomically grab one queued job and mark it running. Returns its id or None."""
    db = SessionLocal()
    try:
        q = db.query(Job).filter(Job.status == "queued").order_by(Job.id.asc())
        if db.bind.dialect.name != "sqlite":
            q = q.with_for_update(skip_locked=True)
        job = q.first()
        if not job:
            return None
        job.status = "running"
        db.commit()
        return job.id
    finally:
        db.close()


async def _single_worker(worker_idx: int) -> None:
    """One worker coroutine. Multiple of these run in parallel."""
    logger.info("Worker[%d] started", worker_idx)
    while True:
        try:
            job_id = await _claim_one()
            if job_id is None:
                await asyncio.sleep(settings.WORKER_POLL_INTERVAL)
                continue
            logger.info("Worker[%d] picked job %s", worker_idx, job_id)
            await _process_one(job_id)
        except asyncio.CancelledError:
            logger.info("Worker[%d] cancelled", worker_idx)
            break
        except Exception:
            logger.exception("Worker[%d] crashed (will retry)", worker_idx)
            await asyncio.sleep(settings.WORKER_POLL_INTERVAL)


async def worker_loop() -> None:
    """Pool of N concurrent worker coroutines (settings.WORKER_CONCURRENCY)."""
    n = max(1, settings.WORKER_CONCURRENCY)
    logger.info("Worker pool starting: %d workers (poll=%.1fs, mock=%s, quality_pass=%d)",
                n, settings.WORKER_POLL_INTERVAL, settings.use_mock_worker, settings.QUALITY_PASS)
    tasks = [asyncio.create_task(_single_worker(i + 1)) for i in range(n)]
    try:
        await asyncio.gather(*tasks)
    except asyncio.CancelledError:
        for t in tasks:
            t.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        raise


__all__ = ["worker_loop"]
