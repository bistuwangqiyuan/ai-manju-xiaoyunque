"""V10 §9.4 — Draft / branch / fork support for jobs.

Builds on the existing ``Job.is_draft`` + ``Job.parent_id`` columns to
provide three operations the dashboard needs:

    fork_job(job_id, owner_id, *, branch_name)   — Make an editable child
                                                    that copies all
                                                    user-visible inputs.
    save_as_draft(job_id)                        — Mark a job as draft.
    publish_draft(job_id)                        — Flip a draft back to
                                                    enqueueable status.
    list_branches(job_id)                        — Return the tree of
                                                    descendants.

These are pure logic + ORM helpers — the actual REST endpoints live in
``backend/app/routes/flow.py``.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any

_log = logging.getLogger(__name__)


@dataclass
class DraftResult:
    job_id: int
    is_draft: bool
    note: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {"job_id": self.job_id, "is_draft": self.is_draft, "note": self.note}


def fork_job(session, job_cls, job_id: int, owner_id: int,
             *, branch_name: str = "branch") -> Any:
    """Create a NEW Job row with the same user-visible inputs, parented to ``job_id``.

    The result row has ``status='draft'``, ``is_draft=True`` and may be
    edited / queued by the owner. Output / log / version columns are NOT
    copied.
    """
    parent = session.query(job_cls).filter(
        job_cls.id == job_id, job_cls.user_id == owner_id,
    ).first()
    if parent is None:
        raise LookupError(f"job {job_id} not found or not owned by user {owner_id}")
    payload: dict[str, Any] = {}
    for col in parent.__table__.columns:
        name = col.name
        if name in {
            "id", "created_at", "updated_at", "status",
            "result_video_url", "result_video_path", "cover_url", "cover_path",
            "result_subtitle_path", "marketing_copy_path", "logs_path",
            "current_version_id", "is_draft",
        }:
            continue
        payload[name] = getattr(parent, name, None)
    payload["parent_id"] = parent.id
    payload["status"] = "draft"
    payload["is_draft"] = True
    payload["title"] = f"{getattr(parent, 'title', '')} · {branch_name}".strip(" ·")
    child = job_cls(**payload)
    session.add(child)
    session.commit()
    session.refresh(child)
    _log.info("forked job %s → %s as branch '%s'", parent.id, child.id, branch_name)
    return child


def save_as_draft(session, job_cls, job_id: int, owner_id: int) -> DraftResult:
    job = session.query(job_cls).filter(
        job_cls.id == job_id, job_cls.user_id == owner_id,
    ).first()
    if job is None:
        raise LookupError(f"job {job_id} not found or not owned by user {owner_id}")
    job.is_draft = True
    if job.status in ("pending", "running"):
        job.status = "draft"
    session.commit()
    return DraftResult(job_id=job.id, is_draft=True, note="saved as draft")


def publish_draft(session, job_cls, job_id: int, owner_id: int) -> DraftResult:
    job = session.query(job_cls).filter(
        job_cls.id == job_id, job_cls.user_id == owner_id,
    ).first()
    if job is None:
        raise LookupError(f"job {job_id} not found or not owned by user {owner_id}")
    if not job.is_draft:
        return DraftResult(job_id=job.id, is_draft=False, note="not a draft")
    job.is_draft = False
    if job.status == "draft":
        job.status = "pending"
    session.commit()
    return DraftResult(job_id=job.id, is_draft=False, note="published")


def list_branches(session, job_cls, root_job_id: int,
                  owner_id: int) -> list[dict[str, Any]]:
    """Return a flat list ``{id, parent_id, status, is_draft, title}``
    describing the descendant tree of ``root_job_id`` (inclusive)."""
    root = session.query(job_cls).filter(
        job_cls.id == root_job_id, job_cls.user_id == owner_id,
    ).first()
    if root is None:
        return []
    out: list[dict[str, Any]] = []
    queue = [root]
    seen: set[int] = set()
    while queue:
        node = queue.pop(0)
        if node.id in seen:
            continue
        seen.add(node.id)
        out.append({
            "id": node.id,
            "parent_id": getattr(node, "parent_id", None),
            "status": getattr(node, "status", "unknown"),
            "is_draft": getattr(node, "is_draft", False),
            "title": getattr(node, "title", ""),
        })
        children = session.query(job_cls).filter(
            job_cls.parent_id == node.id, job_cls.user_id == owner_id,
        ).all()
        queue.extend(children)
    return out


__all__ = [
    "DraftResult", "fork_job", "save_as_draft", "publish_draft", "list_branches",
]
