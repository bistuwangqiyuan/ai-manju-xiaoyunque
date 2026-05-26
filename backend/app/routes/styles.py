"""Custom user-defined picture style endpoints (V10 §1.1).

Routes:
    POST   /styles            multipart upload of 3-8 reference images
    GET    /styles            list user's own + global custom styles
    DELETE /styles/{style_id} delete (only owner or admin)
"""
from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.genres import custom_style as cs
from src.genres import load_genres

from ..security import get_current_user
from ..db import User, get_db


router = APIRouter(prefix="/styles", tags=["styles"])


class StyleSummary(BaseModel):
    style_id: str
    name: str
    palette: List[str]
    style_tags: List[str]
    owner_user_id: Optional[int] = None


class StyleCreateOut(BaseModel):
    style_id: str
    name: str
    palette: List[str]
    style_lock_prompt: str
    style_tags: List[str]
    n_reference_images: int
    has_clip_embedding: bool


@router.get("", response_model=List[StyleSummary])
def list_styles(user: User = Depends(get_current_user)) -> List[StyleSummary]:
    items = cs.list_custom_styles(user_id=user.id)
    return [StyleSummary(**i) for i in items]


@router.post("", response_model=StyleCreateOut, status_code=201)
async def create_style(
    name: str = Form(..., max_length=60),
    files: List[UploadFile] = File(..., description="3-8 张参考图 (jpg/png)"),
    user: User = Depends(get_current_user),
) -> StyleCreateOut:
    if len(files) < 3:
        raise HTTPException(status_code=400, detail="至少需要 3 张参考图")
    if len(files) > 8:
        raise HTTPException(status_code=400, detail="最多支持 8 张参考图")
    blobs: list[bytes] = []
    for f in files:
        if (f.content_type or "").lower() not in {"image/jpeg", "image/jpg", "image/png", "image/webp"}:
            raise HTTPException(status_code=400, detail=f"不支持的图片格式: {f.content_type}")
        data = await f.read()
        if len(data) < 1_000:
            raise HTTPException(status_code=400, detail=f"图片过小: {f.filename}")
        if len(data) > 8 * 1024 * 1024:
            raise HTTPException(status_code=400, detail=f"图片过大 (>8MB): {f.filename}")
        blobs.append(data)
    try:
        fp = cs.fingerprint_style(blobs, name=name, user_id=user.id, include_clip=True)
        cs.materialise_genre_yaml(fp)
        load_genres.cache_clear()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"风格分析失败: {exc}")
    return StyleCreateOut(
        style_id=fp.style_id,
        name=fp.name,
        palette=fp.palette_hex,
        style_lock_prompt=fp.style_lock_prompt,
        style_tags=fp.style_tags,
        n_reference_images=fp.n_reference_images,
        has_clip_embedding=fp.clip_embedding is not None,
    )


@router.delete("/{style_id}", status_code=204)
def delete_style(
    style_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not style_id.startswith("custom_"):
        raise HTTPException(status_code=400, detail="只能删除自定义画风")
    ok = cs.delete_custom_style(style_id, user_id=user.id)
    if not ok:
        raise HTTPException(status_code=404, detail="风格不存在或无权限删除")
    load_genres.cache_clear()
    return None
