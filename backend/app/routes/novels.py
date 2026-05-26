"""V10 §3.1 — Novel routes (import / list / chapter / continuation / translate)."""
from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.compliance import scan_sensitive_text, get_registry
from src.text import (
    chapter_writer,
    novel_import,
    novel_translate,
    plot_state as plot_state_mod,
)

from ..security import get_current_user
from ..db import Chapter, Novel, TranslatedNovel, User, get_db


router = APIRouter(prefix="/novels", tags=["novels"])


class NovelOut(BaseModel):
    id: int
    title: str
    source: str
    source_format: str
    language: str
    genre: str
    total_chars: int
    target_total_chars: int
    chapter_target_chars: int
    summary: Optional[str] = None
    status: str
    detected_chapters: int = 0
    created_at: str

    class Config:
        from_attributes = True


class ChapterOut(BaseModel):
    id: int
    index: int
    title: str
    chars: int
    pov: Optional[str] = None
    summary: Optional[str] = None

    class Config:
        from_attributes = True


class ChapterDetail(ChapterOut):
    body: str


class WriteChapterIn(BaseModel):
    target_chars: int = Field(default=3000, ge=300, le=20000)
    theme_override: Optional[str] = None


class GenerateNovelIn(BaseModel):
    title: str = Field(default="未命名小说", max_length=200)
    theme: str = Field(..., min_length=4, max_length=400)
    genre: str = Field(default="ancient", max_length=40)
    target_total_chars: int = Field(default=50_000, ge=3_000, le=500_000)
    chapter_target_chars: int = Field(default=3000, ge=500, le=20000)
    language: str = "Chinese"


class TranslateIn(BaseModel):
    target_language: str = Field(..., max_length=30)
    engine_hint: Optional[str] = None


def _novel_to_out(novel: Novel, chapters: list[Chapter] | None = None) -> NovelOut:
    return NovelOut(
        id=novel.id,
        title=novel.title,
        source=novel.source,
        source_format=novel.source_format,
        language=novel.language,
        genre=novel.genre,
        total_chars=novel.total_chars,
        target_total_chars=novel.target_total_chars,
        chapter_target_chars=novel.chapter_target_chars,
        summary=novel.summary,
        status=novel.status,
        detected_chapters=len(chapters) if chapters is not None else (
            len(novel.chapters) if novel.chapters else 0),
        created_at=novel.created_at.isoformat() if novel.created_at else "",
    )


# ---------------------------------------------------------------------------
@router.get("", response_model=List[NovelOut])
def list_novels(user: User = Depends(get_current_user),
                db: Session = Depends(get_db)) -> List[NovelOut]:
    rows = db.query(Novel).filter(Novel.user_id == user.id).order_by(Novel.id.desc()).limit(100).all()
    return [_novel_to_out(n) for n in rows]


@router.post("/import", response_model=NovelOut, status_code=201)
async def import_novel(
    file: UploadFile = File(...),
    title: str = Form(default=""),
    genre: str = Form(default="ancient"),
    language: str = Form(default="Chinese"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> NovelOut:
    raw = await file.read()
    if len(raw) > 30 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="单文件最大 30 MB")
    try:
        imported = novel_import.import_any(file.filename or "novel.txt", raw)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    sensitive = scan_sensitive_text(imported.text)
    if sensitive.get("blocked"):
        raise HTTPException(status_code=400, detail=f"内容含敏感词：{sensitive.get('matches')[:3]}")
    copyright_hit = get_registry().check_text(imported.text)
    if copyright_hit["is_match"]:
        raise HTTPException(status_code=409,
                            detail=f"内容与已登记版权高度相似：{copyright_hit['hits'][0]}")
    chapters_parsed = novel_import.split_into_chapters(
        imported.text, target_chars=3000)
    novel = Novel(
        user_id=user.id,
        title=title or (file.filename or "未命名").rsplit(".", 1)[0],
        source="upload",
        source_format=imported.source_format,
        language=language,
        genre=genre,
        total_chars=imported.total_chars,
        target_total_chars=imported.total_chars,
        raw_text=imported.text,
        status="ready",
        sensitive_review=str(sensitive),
        copyright_check=str(copyright_hit),
    )
    db.add(novel)
    db.flush()
    for ch in chapters_parsed:
        db.add(Chapter(
            novel_id=novel.id,
            index=ch["index"],
            title=ch["title"],
            body=ch["body"],
            chars=ch["chars"],
        ))
    db.commit()
    db.refresh(novel)
    return _novel_to_out(novel, chapters_parsed)


@router.post("/generate", response_model=NovelOut, status_code=201)
def generate_novel(
    payload: GenerateNovelIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> NovelOut:
    novel = Novel(
        user_id=user.id,
        title=payload.title,
        source="theme",
        source_format="txt",
        language=payload.language,
        genre=payload.genre,
        total_chars=0,
        target_total_chars=payload.target_total_chars,
        chapter_target_chars=payload.chapter_target_chars,
        summary=payload.theme,
        status="generating",
    )
    db.add(novel)
    db.flush()
    chapters, plot = chapter_writer.write_full_novel(
        novel_title=payload.title,
        genre=payload.genre,
        theme=payload.theme,
        target_total_chars=payload.target_total_chars,
        chars_per_chapter=payload.chapter_target_chars,
        language=payload.language,
    )
    total = 0
    for ch in chapters:
        db.add(Chapter(
            novel_id=novel.id, index=len(novel.chapters) + 1,
            title=ch.title, body=ch.body, chars=ch.chars, pov=ch.pov,
            summary=ch.summary,
            plot_beats_json=str(ch.beats),
        ))
        total += ch.chars
    novel.total_chars = total
    novel.status = "ready"
    novel.plot_graph_json = plot.to_json()
    db.commit()
    db.refresh(novel)
    return _novel_to_out(novel)


@router.get("/{novel_id}", response_model=NovelOut)
def get_novel(novel_id: int, user: User = Depends(get_current_user),
              db: Session = Depends(get_db)) -> NovelOut:
    n = db.get(Novel, novel_id)
    if not n or n.user_id != user.id:
        raise HTTPException(status_code=404, detail="小说不存在")
    return _novel_to_out(n)


@router.get("/{novel_id}/chapters", response_model=List[ChapterOut])
def list_chapters(novel_id: int, user: User = Depends(get_current_user),
                  db: Session = Depends(get_db)) -> List[ChapterOut]:
    n = db.get(Novel, novel_id)
    if not n or n.user_id != user.id:
        raise HTTPException(status_code=404, detail="小说不存在")
    return [
        ChapterOut(id=c.id, index=c.index, title=c.title, chars=c.chars,
                   pov=c.pov, summary=c.summary)
        for c in sorted(n.chapters, key=lambda c: c.index)
    ]


@router.get("/{novel_id}/chapters/{chapter_index}", response_model=ChapterDetail)
def get_chapter(novel_id: int, chapter_index: int,
                user: User = Depends(get_current_user),
                db: Session = Depends(get_db)) -> ChapterDetail:
    n = db.get(Novel, novel_id)
    if not n or n.user_id != user.id:
        raise HTTPException(status_code=404, detail="小说不存在")
    c = next((c for c in n.chapters if c.index == chapter_index), None)
    if not c:
        raise HTTPException(status_code=404, detail="章节不存在")
    return ChapterDetail(id=c.id, index=c.index, title=c.title, chars=c.chars,
                         pov=c.pov, summary=c.summary, body=c.body)


@router.post("/{novel_id}/continue", response_model=ChapterDetail, status_code=201)
def continue_novel(
    novel_id: int,
    payload: WriteChapterIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ChapterDetail:
    n = db.get(Novel, novel_id)
    if not n or n.user_id != user.id:
        raise HTTPException(status_code=404, detail="小说不存在")
    existing = sorted(n.chapters, key=lambda c: c.index)
    next_index = (existing[-1].index + 1) if existing else 1
    plot = (plot_state_mod.PlotState.from_json(n.plot_graph_json)
            if n.plot_graph_json
            else chapter_writer.extract_plot_from_chapters(
                [{"index": c.index, "title": c.title, "body": c.body,
                  "summary": c.summary} for c in existing]))
    previous_summary = existing[-1].summary if existing else ""
    ch = chapter_writer.write_next_chapter(
        novel_title=n.title, genre=n.genre,
        theme=payload.theme_override or (n.summary or n.title),
        index=next_index, target_chars=payload.target_chars,
        plot=plot, previous_summary=previous_summary or "", language=n.language,
    )
    row = Chapter(
        novel_id=n.id, index=next_index, title=ch.title, body=ch.body,
        chars=ch.chars, pov=ch.pov, summary=ch.summary,
        plot_beats_json=str(ch.beats),
    )
    db.add(row)
    n.total_chars = (n.total_chars or 0) + ch.chars
    n.plot_graph_json = plot.to_json()
    db.commit()
    db.refresh(row)
    return ChapterDetail(id=row.id, index=row.index, title=row.title,
                         chars=row.chars, pov=row.pov, summary=row.summary,
                         body=row.body)


@router.post("/{novel_id}/translate", response_model=dict, status_code=201)
def translate(
    novel_id: int,
    payload: TranslateIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    n = db.get(Novel, novel_id)
    if not n or n.user_id != user.id:
        raise HTTPException(status_code=404, detail="小说不存在")
    try:
        lang = novel_translate.normalise_language(payload.target_language)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    src = "\n\n".join(c.body for c in sorted(n.chapters, key=lambda c: c.index))
    doc = novel_translate.translate_novel(source_text=src, target_language=lang)
    row = TranslatedNovel(
        novel_id=n.id, language=lang, translation_engine=doc.engine,
        body=doc.body,
        glossary_json=str(doc.glossary),
        quality_score=doc.quality_score,
        status="ready",
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return {
        "id": row.id, "language": lang, "engine": doc.engine,
        "chunk_count": doc.chunk_count, "quality_score": doc.quality_score,
        "preview": doc.body[:600],
    }


@router.delete("/{novel_id}", status_code=204)
def delete_novel(novel_id: int, user: User = Depends(get_current_user),
                 db: Session = Depends(get_db)):
    n = db.get(Novel, novel_id)
    if not n or n.user_id != user.id:
        raise HTTPException(status_code=404, detail="小说不存在")
    db.delete(n)
    db.commit()
    return None
