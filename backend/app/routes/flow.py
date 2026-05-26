"""V10 §9.2 + §9.4 — Pause-gate + draft/fork endpoints.

Routes:
    GET    /flow/pauses/{job_id}            list pending pause events
    GET    /flow/pause/{job_id}/{step}      get one
    POST   /flow/pause/{job_id}/{step}      orchestrator triggers a pause
    POST   /flow/approve/{job_id}/{step}    user resolves: approve
    POST   /flow/reject/{job_id}/{step}     user resolves: reject
    POST   /flow/modify/{job_id}/{step}     user resolves: modify+resume
    WS     /flow/ws/pauses/{job_id}         WebSocket subscription

    POST   /flow/jobs/{job_id}/fork         clone job as draft branch
    POST   /flow/jobs/{job_id}/draft        mark as draft
    POST   /flow/jobs/{job_id}/publish      flip draft → pending
    GET    /flow/jobs/{job_id}/branches     enumerate branch tree
"""
from __future__ import annotations

import asyncio
import json
from typing import Any

from fastapi import (
    APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect,
)
from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.flow.drafts import (
    fork_job, list_branches, publish_draft, save_as_draft,
)
from src.flow.pause_gate import get_gate

from ..db import Job, User, get_db
from ..security import get_current_user

router = APIRouter(prefix="/flow", tags=["flow"])


class PauseTriggerIn(BaseModel):
    step: str
    summary: dict[str, Any] = {}


class PauseResolveIn(BaseModel):
    user_payload: dict[str, Any] = {}


class ForkIn(BaseModel):
    branch_name: str = "branch"


def _ensure_job_owned(db: Session, user: User, job_id: int) -> Job:
    job = db.query(Job).filter(Job.id == job_id, Job.user_id == user.id).first()
    if job is None:
        raise HTTPException(status_code=404, detail="job not found")
    return job


# ---------- pause-gate ----------

@router.get("/pauses/{job_id}")
def list_pauses(
    job_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _ensure_job_owned(db, user, job_id)
    gate = get_gate()
    return {"pending": [e.to_dict() for e in gate.list_pending(job_id=job_id)]}


@router.get("/pause/{job_id}/{step}")
def get_pause(
    job_id: int, step: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _ensure_job_owned(db, user, job_id)
    ev = get_gate().status(job_id, step)
    if ev is None:
        raise HTTPException(status_code=404, detail="no pause event for this step")
    return ev.to_dict()


@router.post("/pause/{job_id}/{step}")
def trigger_pause(
    job_id: int, step: str, body: PauseTriggerIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Orchestrator-only — typically called server-side rather than from the UI."""
    _ensure_job_owned(db, user, job_id)
    ev = get_gate().request_pause(job_id, step, summary=body.summary)
    return ev.to_dict()


@router.post("/approve/{job_id}/{step}")
def approve_pause(
    job_id: int, step: str, body: PauseResolveIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _ensure_job_owned(db, user, job_id)
    try:
        ev = get_gate().approve(job_id, step, body.user_payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return ev.to_dict()


@router.post("/reject/{job_id}/{step}")
def reject_pause(
    job_id: int, step: str, body: PauseResolveIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _ensure_job_owned(db, user, job_id)
    try:
        ev = get_gate().reject(job_id, step, body.user_payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return ev.to_dict()


@router.post("/modify/{job_id}/{step}")
def modify_pause(
    job_id: int, step: str, body: PauseResolveIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _ensure_job_owned(db, user, job_id)
    try:
        ev = get_gate().modify(job_id, step, body.user_payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return ev.to_dict()


@router.websocket("/ws/pauses/{job_id}")
async def ws_pauses(websocket: WebSocket, job_id: int):
    await websocket.accept()
    gate = get_gate()
    last_snapshot: list[dict[str, Any]] = []
    try:
        while True:
            pending = [e.to_dict() for e in gate.list_pending(job_id=job_id)]
            if pending != last_snapshot:
                await websocket.send_text(json.dumps(
                    {"job_id": job_id, "pending": pending},
                    ensure_ascii=False,
                ))
                last_snapshot = pending
            await asyncio.sleep(2.0)
    except WebSocketDisconnect:
        return
    except Exception:
        try:
            await websocket.close()
        except Exception:
            pass


# ---------- drafts / branches / fork ----------

@router.post("/jobs/{job_id}/fork")
def fork_endpoint(
    job_id: int, body: ForkIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        child = fork_job(db, Job, job_id, user.id, branch_name=body.branch_name)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return {"id": child.id, "parent_id": child.parent_id,
            "title": child.title, "status": child.status,
            "is_draft": child.is_draft}


@router.post("/jobs/{job_id}/draft")
def draft_endpoint(
    job_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        return save_as_draft(db, Job, job_id, user.id).to_dict()
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.post("/jobs/{job_id}/publish")
def publish_endpoint(
    job_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        return publish_draft(db, Job, job_id, user.id).to_dict()
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.get("/jobs/{job_id}/branches")
def branches_endpoint(
    job_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    branches = list_branches(db, Job, job_id, user.id)
    if not branches:
        raise HTTPException(status_code=404, detail="job not found")
    return {"branches": branches}
