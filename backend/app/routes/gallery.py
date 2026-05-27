"""Public gallery: official samples + all users' succeeded videos."""
from __future__ import annotations

import json
import pathlib
from typing import List

from fastapi import APIRouter, Depends, Query
from sqlalchemy import desc
from sqlalchemy.orm import Session

from ..db import Job, User, get_db
from ..schemas import GalleryItemOut

router = APIRouter(prefix="/gallery", tags=["gallery"])

# Official R40 sample clips (web/public/samples/)
OFFICIAL_SAMPLES: list[dict] = [
    {
        "id": "sample-nie01",
        "title": "兰若惊鸿",
        "subtitle": "夜投兰若寺，初见小倩魂",
        "genre": "ancient",
        "style": "ancient_3d_guoman",
        "video_url": "/samples/nie01_lanruosi.mp4",
        "cover_url": "/samples/nie01_lanruosi.jpg",
        "quality_score": 97,
        "episodes": 1,
        "character_name": "聂小倩",
    },
    {
        "id": "sample-nie02",
        "title": "小倩出场",
        "subtitle": "月白冷青夜，朱砂痣定格",
        "genre": "ancient",
        "style": "ancient_3d_guoman",
        "video_url": "/samples/nie02_appears.mp4",
        "cover_url": "/samples/nie02_appears.jpg",
        "quality_score": 96,
        "episodes": 1,
        "character_name": "聂小倩",
    },
    {
        "id": "sample-nie03",
        "title": "剑指燕赤霞",
        "subtitle": "友人脉象抽搐，剑光出鞘",
        "genre": "ancient",
        "style": "ancient_3d_guoman",
        "video_url": "/samples/nie03_yan_chixia.mp4",
        "cover_url": "/samples/nie03_yan_chixia.jpg",
        "quality_score": 97,
        "episodes": 1,
        "character_name": "燕赤霞",
    },
    {
        "id": "sample-xiyou01",
        "title": "石猴出世",
        "subtitle": "花果山 · 西游记开篇",
        "genre": "xuanhuan",
        "style": "ancient_3d_guoman",
        "video_url": "/samples/xiyou01_immortal_stone.mp4",
        "cover_url": "/samples/xiyou01_immortal_stone.jpg",
        "quality_score": 95,
        "episodes": 1,
        "character_name": "孙悟空",
    },
]


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
        for s in OFFICIAL_SAMPLES:
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
                    author_label="官方示例 · R40 实测",
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
        items.append(
            GalleryItemOut(
                id=f"job-{job.id}",
                kind="community",
                title=job.title or "未命名漫剧",
                subtitle=(job.theme or job.novel_excerpt or "")[:120] or None,
                genre=job.genre or "ancient",
                style=job.style or "",
                video_url=job.result_url or "",
                cover_url=job.cover_url,
                quality_score=job.quality_score,
                episodes=job.episodes,
                author_label=_mask_email(user.email),
                created_at=job.created_at,
                job_id=job.id,
            )
        )

    return items
