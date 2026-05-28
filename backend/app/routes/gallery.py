"""Public gallery: official samples + all users' succeeded videos."""
from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, Query
from sqlalchemy import desc
from sqlalchemy.orm import Session

from src.common.sample_catalog import official_gallery_items, resolve_playable_url

from ..db import Job, User, get_db
from ..schemas import GalleryItemOut

router = APIRouter(prefix="/gallery", tags=["gallery"])


def _mask_email(email: str) -> str:
    if "@" not in email:
        return "创作者"
    local, domain = email.split("@", 1)
    if len(local) <= 2:
        masked = local[0] + "***"
    else:
        masked = local[0] + "***" + local[-1]
    return f"{masked}@{domain}"


@router.get("", response_model=List[GalleryItemOut])
def list_gallery(
    limit: int = Query(default=50, ge=1, le=200),
    include_samples: bool = Query(default=True),
    db: Session = Depends(get_db),
) -> List[GalleryItemOut]:
    """Public feed: official samples + community videos from all users."""
    items: list[GalleryItemOut] = []

    if include_samples:
        for s in official_gallery_items():
            items.append(
                GalleryItemOut(
                    id=s["id"],
                    kind="official",
                    title=s["title"],
                    subtitle=s.get("subtitle"),
                    genre=s.get("genre", "ancient"),
                    style=s.get("style", ""),
                    video_url=s["video_url"],
                    cover_url=s.get("cover_url"),
                    quality_score=s.get("quality_score"),
                    episodes=s.get("episodes", 1),
                    author_label=s.get("author_label", "官方示例 · R40 实测"),
                    created_at=None,
                    job_id=None,
                )
            )

    rows: list[tuple[Job, User]] = []
    try:
        rows = (
            db.query(Job, User)
            .join(User, Job.user_id == User.id)
            .filter(Job.status == "succeeded", Job.result_url.isnot(None))
            .order_by(desc(Job.updated_at))
            .limit(limit)
            .all()
        )
    except Exception:
        rows = []

    for job, user in rows:
        video_url, cover_url = resolve_playable_url(
            job.result_url, job.cover_url, seed=job.id
        )
        items.append(
            GalleryItemOut(
                id=f"job-{job.id}",
                kind="community",
                title=job.title or "未命名漫剧",
                subtitle=(job.theme or job.novel_excerpt or "")[:120] or None,
                genre=job.genre or "ancient",
                style=job.style or "",
                video_url=video_url,
                cover_url=cover_url,
                quality_score=job.quality_score,
                episodes=job.episodes,
                author_label=_mask_email(user.email),
                created_at=job.created_at,
                job_id=job.id,
            )
        )

    return items
