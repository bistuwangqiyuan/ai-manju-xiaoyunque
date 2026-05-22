"""Genre & template listing endpoints (requirement doc §一 基础定位 + §模板化)."""
from __future__ import annotations

from typing import List

from fastapi import APIRouter, HTTPException

from ..schemas import GenreOut

router = APIRouter(prefix="/genres", tags=["genres"])


@router.get("", response_model=List[GenreOut])
def list_genres() -> List[GenreOut]:
    """Return the catalog of all available genre templates."""
    try:
        from src.genres import load_genres

        out: List[GenreOut] = []
        for g in load_genres().values():
            out.append(
                GenreOut(
                    id=g.id,
                    name_zh=g.name_zh,
                    name_en=g.name_en,
                    description=g.description,
                    style_id=g.style_id,
                    aspect_ratio=g.aspect_ratio,
                    default_episodes=g.default_episodes,
                    sample_themes=g.sample_themes,
                    preview_video_url=g.preview_video_url,
                    preview_cover_url=g.preview_cover_url,
                )
            )
        return out
    except Exception:
        # graceful fallback: hard-code the 5 doc'd genres
        return [
            GenreOut(
                id="ancient",
                name_zh="古风",
                name_en="Ancient Chinese",
                description="古代中国仙侠/古言/历史/志怪",
                style_id="ancient_3d_guoman",
                aspect_ratio="9:16",
                default_episodes=10,
                sample_themes=["聊斋·聂小倩", "山雨欲来"],
            ),
            GenreOut(
                id="modern",
                name_zh="现代",
                name_en="Modern",
                description="都市/职场/校园/家庭",
                style_id="modern_cinematic",
                aspect_ratio="9:16",
                default_episodes=10,
                sample_themes=["霸总隐婚", "高考重生"],
            ),
            GenreOut(
                id="sweet_pet",
                name_zh="甜宠",
                name_en="Sweet Romance",
                description="甜宠/校园爱情/年下/契约婚",
                style_id="sweet_anime_3d",
                aspect_ratio="9:16",
                default_episodes=8,
                sample_themes=["契约 100 天", "校园甜剧"],
            ),
            GenreOut(
                id="suspense",
                name_zh="悬疑",
                name_en="Suspense",
                description="悬疑/推理/惊悚/犯罪",
                style_id="noir_cinematic",
                aspect_ratio="9:16",
                default_episodes=12,
                sample_themes=["连环密码", "深夜地铁"],
            ),
            GenreOut(
                id="xuanhuan",
                name_zh="玄幻",
                name_en="Xuanhuan",
                description="玄幻/修仙/异世/魔法",
                style_id="xuanhuan_epic",
                aspect_ratio="9:16",
                default_episodes=12,
                sample_themes=["仙尊重生", "末法时代"],
            ),
        ]


@router.get("/{genre_id}", response_model=GenreOut)
def get_genre_detail(genre_id: str) -> GenreOut:
    from src.genres import load_genres

    g = load_genres().get(genre_id)
    if not g:
        raise HTTPException(status_code=404, detail="genre 不存在")
    return GenreOut(
        id=g.id,
        name_zh=g.name_zh,
        name_en=g.name_en,
        description=g.description,
        style_id=g.style_id,
        aspect_ratio=g.aspect_ratio,
        default_episodes=g.default_episodes,
        sample_themes=g.sample_themes,
        preview_video_url=g.preview_video_url,
        preview_cover_url=g.preview_cover_url,
    )
