from __future__ import annotations

from datetime import datetime, timedelta
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import desc
from sqlalchemy.orm import Session

from ..db import Job, JobLog, User, get_db
from ..schemas import JobCreateIn, JobLogOut, JobOut, job_to_out
from ..security import get_current_user
from ..settings import settings

router = APIRouter(prefix="/jobs", tags=["jobs"])


def _today_window() -> tuple[datetime, datetime]:
    """UTC day window [start, end). 用 UTC 一致就行，全球用户也用 UTC 计配额。"""
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    return today_start, today_start + timedelta(days=1)


def _free_jobs_today(db: Session, user_id: int) -> int:
    start, end = _today_window()
    return (
        db.query(Job)
        .filter(
            Job.user_id == user_id,
            Job.created_at >= start,
            Job.created_at < end,
            # 已取消的任务不计入今日配额（让用户能重试）
            Job.status != "cancelled",
        )
        .count()
    )


def _compute_cost_cents(tier: str, episodes: int) -> int:
    """按 tier 算扣费金额（分）。free / admin: 0；其余: base * 1.1 * episodes"""
    if tier in ("free", "admin"):
        return 0
    base = settings.EPISODE_BASE_COST_CENTS * episodes
    return int(round(base * settings.PROFIT_MULTIPLIER))


@router.get("", response_model=List[JobOut])
def list_jobs(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> List[JobOut]:
    rows = (
        db.query(Job)
        .filter(Job.user_id == user.id)
        .order_by(desc(Job.created_at))
        .limit(100)
        .all()
    )
    return [job_to_out(r) for r in rows]


@router.get("/quota")
def get_quota(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """前端 dashboard 用：当前 tier、今日已用、剩余、单集预估费用"""
    used = _free_jobs_today(db, user.id) if user.tier == "free" else 0
    cost_per_episode = _compute_cost_cents(user.tier, 1)
    return {
        "tier": user.tier,
        "credits_cents": user.credits_cents,
        "free_daily_limit": settings.FREE_DAILY_QUOTA,
        "free_used_today": used,
        "free_remaining_today": max(0, settings.FREE_DAILY_QUOTA - used) if user.tier == "free" else None,
        "cost_per_episode_cents": cost_per_episode,
        "episode_base_cost_cents": settings.EPISODE_BASE_COST_CENTS,
        "profit_multiplier": settings.PROFIT_MULTIPLIER,
    }


@router.post("", response_model=JobOut, status_code=201)
def create_job(
    payload: JobCreateIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> JobOut:
    # 1) Free 用户当日配额
    if user.tier == "free":
        used = _free_jobs_today(db, user.id)
        if used + 1 > settings.FREE_DAILY_QUOTA:
            raise HTTPException(
                status_code=429,
                detail=(
                    f"今日免费配额已用完（{settings.FREE_DAILY_QUOTA} 个/天）。"
                    f"充值任意金额自动升级为付费用户，配额无限制。"
                ),
            )
        # Free 用户超过 1 集不让做（避免一次性把额度吃完）
        if payload.episodes > 1:
            raise HTTPException(
                status_code=403,
                detail="免费用户单次只能生成 1 集。十集套装请升级为付费用户。",
            )

    # 2) 计算扣费
    cost = _compute_cost_cents(user.tier, payload.episodes)

    # 3) 余额校验（free 用户 cost=0，自然通过）
    if cost > 0 and user.credits_cents < cost:
        raise HTTPException(
            status_code=402,
            detail=f"余额不足：需要 ¥{cost/100:.2f}（按成本×{settings.PROFIT_MULTIPLIER} 计算），当前 ¥{user.credits_cents/100:.2f}",
        )
    if cost > 0:
        user.credits_cents -= cost

    job = Job(
        user_id=user.id,
        title=payload.title or "未命名漫剧",
        novel_excerpt=payload.novel_excerpt,
        style=payload.style,
        episodes=payload.episodes,
        cost_cents=cost,
        status="queued",
        progress=0,
    )
    db.add(job)
    db.flush()
    if user.tier == "free":
        used_after = _free_jobs_today(db, user.id)
        db.add(JobLog(job_id=job.id, level="INFO",
                      message=f"[free] 今日配额 {used_after}/{settings.FREE_DAILY_QUOTA} 已使用"))
    else:
        db.add(JobLog(job_id=job.id, level="INFO",
                      message=f"[{user.tier}] 扣费 ¥{cost/100:.2f}（成本 ¥{settings.EPISODE_BASE_COST_CENTS*payload.episodes/100:.2f} × {settings.PROFIT_MULTIPLIER}）"))
    db.commit()
    db.refresh(job)
    return job_to_out(job)


@router.get("/{job_id}", response_model=JobOut)
def get_job(
    job_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> JobOut:
    job = db.get(Job, job_id)
    if not job or job.user_id != user.id:
        raise HTTPException(status_code=404, detail="任务不存在")
    return job_to_out(job)


@router.get("/{job_id}/logs", response_model=List[JobLogOut])
def get_job_logs(
    job_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> List[JobLogOut]:
    job = db.get(Job, job_id)
    if not job or job.user_id != user.id:
        raise HTTPException(status_code=404, detail="任务不存在")
    rows = db.query(JobLog).filter(JobLog.job_id == job_id).order_by(JobLog.id).all()
    return [JobLogOut.model_validate(r) for r in rows]


@router.post("/{job_id}/cancel", response_model=JobOut)
def cancel_job(
    job_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> JobOut:
    job = db.get(Job, job_id)
    if not job or job.user_id != user.id:
        raise HTTPException(status_code=404, detail="任务不存在")
    if job.status in ("succeeded", "failed", "cancelled"):
        raise HTTPException(status_code=400, detail=f"任务已是 {job.status}，不可取消")

    # 退还剩余比例金额
    refund_ratio = max(0.0, 1.0 - job.progress / 100.0)
    refund = int(round(job.cost_cents * refund_ratio))
    if refund > 0:
        user.credits_cents += refund
        db.add(JobLog(job_id=job.id, level="INFO", message=f"取消，退回 ¥{refund/100:.2f}"))

    job.status = "cancelled"
    db.commit()
    db.refresh(job)
    return job_to_out(job)
