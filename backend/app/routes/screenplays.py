"""V10 §3.2 — Screenplay routes (novel→screenplay + dialogue polish)."""
from __future__ import annotations

import json
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.text import dialogue_polish, novel_to_screenplay
from src.text.novel_to_screenplay import screenplay_to_json

from ..security import get_current_user
from ..db import Chapter, Novel, Scene, Screenplay, User, get_db


router = APIRouter(prefix="/screenplays", tags=["screenplays"])


class ScreenplayOut(BaseModel):
    id: int
    title: str
    episode_count: int
    target_duration_per_episode_s: int
    language: str
    polish_status: str
    scene_count: int
    created_at: str

    class Config:
        from_attributes = True


class ScreenplayCreateIn(BaseModel):
    novel_id: int
    episode_count: int = Field(default=10, ge=1, le=50)
    target_duration_per_episode_s: int = Field(default=80, ge=30, le=300)
    language: str = "Chinese"


class SceneOut(BaseModel):
    id: int
    episode: int
    index: int
    heading: str
    location: Optional[str] = None
    time_of_day: Optional[str] = None
    atmosphere: Optional[str] = None
    action_text: str
    dialogue: list[dict]
    pov_character: Optional[str] = None
    duration_estimate_s: int

    class Config:
        from_attributes = True


def _screenplay_to_out(s: Screenplay) -> ScreenplayOut:
    return ScreenplayOut(
        id=s.id, title=s.title, episode_count=s.episode_count,
        target_duration_per_episode_s=s.target_duration_per_episode_s,
        language=s.language, polish_status=s.polish_status,
        scene_count=len(s.scenes),
        created_at=s.created_at.isoformat() if s.created_at else "",
    )


@router.post("", response_model=ScreenplayOut, status_code=201)
def create_screenplay(payload: ScreenplayCreateIn,
                      user: User = Depends(get_current_user),
                      db: Session = Depends(get_db)) -> ScreenplayOut:
    novel = db.get(Novel, payload.novel_id)
    if not novel or novel.user_id != user.id:
        raise HTTPException(status_code=404, detail="小说不存在")
    chapter_dicts = [
        {"index": c.index, "title": c.title, "body": c.body,
         "summary": c.summary, "pov": c.pov}
        for c in sorted(novel.chapters, key=lambda c: c.index)
    ]
    doc = novel_to_screenplay.novel_to_screenplay(
        novel_title=novel.title,
        chapters=chapter_dicts,
        episode_count=payload.episode_count,
        target_duration_per_episode_s=payload.target_duration_per_episode_s,
        language=payload.language,
    )
    sp = Screenplay(
        novel_id=novel.id, title=novel.title,
        episode_count=payload.episode_count,
        target_duration_per_episode_s=payload.target_duration_per_episode_s,
        language=payload.language,
        formatted_md=doc.formatted_md,
        characters_json=json.dumps(doc.characters, ensure_ascii=False),
        polish_status="draft",
    )
    db.add(sp)
    db.flush()
    for sc in doc.scenes:
        db.add(Scene(
            screenplay_id=sp.id,
            episode=sc.episode, index=sc.index, heading=sc.heading,
            location=sc.location, time_of_day=sc.time_of_day,
            atmosphere=sc.atmosphere, action_text=sc.action_text,
            dialogue_json=json.dumps(
                [{"speaker": d.speaker, "line": d.line, "emotion": d.emotion}
                 for d in sc.dialogue], ensure_ascii=False),
            pov_character=sc.pov_character,
            duration_estimate_s=sc.duration_estimate_s,
        ))
    db.commit()
    db.refresh(sp)
    return _screenplay_to_out(sp)


@router.get("", response_model=List[ScreenplayOut])
def list_screenplays(user: User = Depends(get_current_user),
                     db: Session = Depends(get_db)) -> List[ScreenplayOut]:
    rows = db.query(Screenplay).join(Novel, Novel.id == Screenplay.novel_id, isouter=True).filter(
        (Novel.user_id == user.id) | (Screenplay.novel_id.is_(None))
    ).order_by(Screenplay.id.desc()).limit(100).all()
    return [_screenplay_to_out(s) for s in rows]


@router.get("/{sp_id}", response_model=dict)
def get_screenplay(sp_id: int, user: User = Depends(get_current_user),
                   db: Session = Depends(get_db)) -> dict:
    sp = db.get(Screenplay, sp_id)
    if not sp:
        raise HTTPException(status_code=404, detail="剧本不存在")
    if sp.novel_id is not None:
        n = db.get(Novel, sp.novel_id)
        if not n or n.user_id != user.id:
            raise HTTPException(status_code=403, detail="无权访问")
    return {
        "id": sp.id,
        "title": sp.title,
        "episode_count": sp.episode_count,
        "target_duration_per_episode_s": sp.target_duration_per_episode_s,
        "language": sp.language,
        "polish_status": sp.polish_status,
        "formatted_md": sp.formatted_md,
        "characters": json.loads(sp.characters_json) if sp.characters_json else [],
        "scenes": [
            {
                "id": s.id, "episode": s.episode, "index": s.index,
                "heading": s.heading, "location": s.location,
                "time_of_day": s.time_of_day, "atmosphere": s.atmosphere,
                "action_text": s.action_text,
                "dialogue": json.loads(s.dialogue_json) if s.dialogue_json else [],
                "pov_character": s.pov_character,
                "duration_estimate_s": s.duration_estimate_s,
            } for s in sp.scenes
        ],
    }


@router.post("/{sp_id}/polish", response_model=dict)
def polish_screenplay(sp_id: int, user: User = Depends(get_current_user),
                      db: Session = Depends(get_db)) -> dict:
    sp = db.get(Screenplay, sp_id)
    if not sp:
        raise HTTPException(status_code=404, detail="剧本不存在")
    if sp.novel_id is not None:
        n = db.get(Novel, sp.novel_id)
        if not n or n.user_id != user.id:
            raise HTTPException(status_code=403, detail="无权访问")
    polished_count = 0
    for sc in sp.scenes:
        raw = json.loads(sc.dialogue_json) if sc.dialogue_json else []
        if not raw:
            continue
        polished = dialogue_polish.polish_dialogue(raw)
        sc.dialogue_json = json.dumps([
            {"speaker": p.speaker, "line": p.polished, "emotion": p.emotion,
             "intensity": p.intensity, "estimated_seconds": p.estimated_seconds}
            for p in polished
        ], ensure_ascii=False)
        polished_count += len(polished)
    sp.polish_status = "polished"
    db.commit()
    return {"polished_lines": polished_count, "scenes": len(sp.scenes),
            "status": sp.polish_status}


@router.delete("/{sp_id}", status_code=204)
def delete_screenplay(sp_id: int, user: User = Depends(get_current_user),
                      db: Session = Depends(get_db)):
    sp = db.get(Screenplay, sp_id)
    if not sp:
        raise HTTPException(status_code=404, detail="剧本不存在")
    if sp.novel_id is not None:
        n = db.get(Novel, sp.novel_id)
        if not n or n.user_id != user.id:
            raise HTTPException(status_code=403, detail="无权访问")
    db.delete(sp)
    db.commit()
    return None
