"""V10 §9.3 — Timed publishing endpoints.

Routes:
    POST   /schedules               register a recurring/one-shot trigger
    GET    /schedules               list mine
    GET    /schedules/due           list jobs whose next_fire_at is in the past
    DELETE /schedules/{schedule_id} cancel
    POST   /schedules/poll          (internal) fire due jobs now
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, model_validator

from src.flow.scheduler import ScheduleSpec, get_registry

from ..security import get_current_user
from ..db import Job, User, get_db
from sqlalchemy.orm import Session


router = APIRouter(prefix="/schedules", tags=["schedules"])


class ScheduleIn(BaseModel):
    job_id: int
    description: str = ""
    cron: str | None = None
    date: str | None = None
    interval_seconds: int | None = None

    @model_validator(mode="after")
    def _exactly_one_trigger(self):
        n_set = sum(bool(x) for x in (self.cron, self.date, self.interval_seconds))
        if n_set != 1:
            raise ValueError("provide exactly one of cron / date / interval_seconds")
        return self


@router.post("")
def register_schedule(
    body: ScheduleIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    job = db.query(Job).filter(Job.id == body.job_id, Job.user_id == user.id).first()
    if job is None:
        raise HTTPException(status_code=404, detail="job not found")
    spec = ScheduleSpec(cron=body.cron, date=body.date,
                        interval_seconds=body.interval_seconds)
    reg = get_registry()
    sched = reg.register_job(body.job_id, spec,
                             owner_id=user.id, description=body.description)
    return sched.to_dict()


@router.get("")
def list_schedules(user: User = Depends(get_current_user)):
    reg = get_registry()
    return {"schedules": [s.to_dict() for s in reg.list_jobs(owner_id=user.id)]}


@router.get("/due")
def list_due(user: User = Depends(get_current_user)):
    reg = get_registry()
    return {"due": [s.to_dict()
                    for s in reg.list_jobs(owner_id=user.id, only_due=True)]}


@router.delete("/{schedule_id}")
def cancel_schedule(schedule_id: str, user: User = Depends(get_current_user)):
    reg = get_registry()
    items = reg.list_jobs(owner_id=user.id)
    if not any(s.schedule_id == schedule_id for s in items):
        raise HTTPException(status_code=404, detail="schedule not found")
    reg.cancel_job(schedule_id)
    return {"cancelled": schedule_id}


@router.post("/poll")
def poll_due_endpoint(user: User = Depends(get_current_user)):
    """Internal endpoint: APScheduler-less deployments call this from a cron
    or `/api/internal/worker/tick` to fire due schedules."""
    reg = get_registry()
    fired = reg.poll_due()
    return {"fired": [s.schedule_id for s in fired], "count": len(fired)}
