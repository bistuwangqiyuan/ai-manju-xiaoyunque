from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import desc
from sqlalchemy.orm import Session

from ..db import Job, JobLog, User, get_db
from ..schemas import JobCreateIn, JobLogOut, JobOut
from ..security import get_current_user

router = APIRouter(prefix="/jobs", tags=["jobs"])

PER_EPISODE_CENTS = 9900  # ¥99/集


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
    return [JobOut.model_validate(r) for r in rows]


@router.post("", response_model=JobOut, status_code=201)
def create_job(
    payload: JobCreateIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> JobOut:
    cost = payload.episodes * PER_EPISODE_CENTS
    if user.credits_cents < cost:
        raise HTTPException(
            status_code=402,
            detail=f"余额不足，需要 ¥{cost/100:.2f}，当前 ¥{user.credits_cents/100:.2f}",
        )
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
    db.add(JobLog(job_id=job.id, level="INFO", message="任务已创建，等待 worker 拉取"))
    db.commit()
    db.refresh(job)
    return JobOut.model_validate(job)


@router.get("/{job_id}", response_model=JobOut)
def get_job(
    job_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> JobOut:
    job = db.get(Job, job_id)
    if not job or job.user_id != user.id:
        raise HTTPException(status_code=404, detail="任务不存在")
    return JobOut.model_validate(job)


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
    return JobOut.model_validate(job)
