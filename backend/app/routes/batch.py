"""Batch 转绘 endpoints (requirement doc §12)."""
from __future__ import annotations

import json
import os
import pathlib
import shutil
import uuid
from datetime import datetime
from typing import List

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy import desc
from sqlalchemy.orm import Session

from ..db import Batch, BatchItem, User, get_db
from ..schemas import BatchCreateIn, BatchItemOut, BatchOut
from ..security import get_current_user
from ..settings import settings

router = APIRouter(prefix="/batch", tags=["batch"])


def _item_to_out(it: BatchItem) -> BatchItemOut:
    sc = json.loads(it.score_7d_json) if it.score_7d_json else None
    params = json.loads(it.params_json) if it.params_json else None
    return BatchItemOut(
        id=it.id,
        batch_id=it.batch_id,
        source_url=it.source_url,
        result_url=it.result_url,
        params=params,
        status=it.status,
        score_7d=sc,
        overall_score=it.overall_score,
        passed=it.passed,
        repair_iters=it.repair_iters,
        feedback=it.feedback,
        created_at=it.created_at,
        updated_at=it.updated_at,
    )


def _batch_to_out(b: Batch, items: list[BatchItem] | None = None) -> BatchOut:
    items = items if items is not None else b.items
    return BatchOut(
        id=b.id,
        name=b.name,
        style=b.style,
        genre=b.genre,
        aspect_ratio=b.aspect_ratio,
        status=b.status,
        total_items=b.total_items,
        finished_items=b.finished_items,
        params=json.loads(b.params_json) if b.params_json else None,
        items=[_item_to_out(i) for i in items],
        created_at=b.created_at,
        updated_at=b.updated_at,
    )


@router.get("", response_model=List[BatchOut])
def list_batches(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> List[BatchOut]:
    rows = (
        db.query(Batch)
        .filter(Batch.user_id == user.id)
        .order_by(desc(Batch.created_at))
        .limit(100)
        .all()
    )
    return [_batch_to_out(b) for b in rows]


@router.post("", response_model=BatchOut, status_code=201)
def create_batch(
    payload: BatchCreateIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> BatchOut:
    if not payload.source_urls:
        raise HTTPException(status_code=400, detail="至少需要 1 个 source_url")
    b = Batch(
        user_id=user.id,
        name=payload.name,
        style=payload.style,
        genre=payload.genre,
        aspect_ratio=payload.aspect_ratio,
        total_items=len(payload.source_urls),
        finished_items=0,
        status="queued",
        params_json=json.dumps(payload.params or {}, ensure_ascii=False),
    )
    db.add(b)
    db.flush()
    for url in payload.source_urls:
        item = BatchItem(
            batch_id=b.id,
            source_url=url,
            status="queued",
            params_json=json.dumps(payload.params or {}, ensure_ascii=False),
        )
        db.add(item)
    db.commit()
    db.refresh(b)
    return _batch_to_out(b)


@router.post("/upload", response_model=BatchOut, status_code=201)
async def upload_files(
    files: List[UploadFile] = File(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> BatchOut:
    """Multipart upload + auto-batch creation (requirement doc §12 多文件上传)."""
    if not files:
        raise HTTPException(status_code=400, detail="请上传至少 1 个文件")

    upload_root = pathlib.Path(settings.STORAGE_DIR) / "uploads" / str(user.id) / uuid.uuid4().hex
    upload_root.mkdir(parents=True, exist_ok=True)

    source_urls: list[str] = []
    for f in files:
        if not f.filename:
            continue
        dest = upload_root / f.filename
        with dest.open("wb") as out:
            shutil.copyfileobj(f.file, out)
        rel = dest.relative_to(pathlib.Path(settings.STORAGE_DIR))
        url = f"/storage/{str(rel).replace(os.sep, '/')}"
        source_urls.append(url)

    b = Batch(
        user_id=user.id,
        name=f"上传 {len(source_urls)} 个文件",
        total_items=len(source_urls),
        finished_items=0,
        status="queued",
    )
    db.add(b)
    db.flush()
    for url in source_urls:
        db.add(BatchItem(batch_id=b.id, source_url=url, status="queued"))
    db.commit()
    db.refresh(b)
    return _batch_to_out(b)


@router.get("/{batch_id}", response_model=BatchOut)
def get_batch(
    batch_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> BatchOut:
    b = db.get(Batch, batch_id)
    if not b or b.user_id != user.id:
        raise HTTPException(status_code=404, detail="批次不存在")
    return _batch_to_out(b)


@router.post("/{batch_id}/run", response_model=BatchOut)
def run_batch(
    batch_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> BatchOut:
    """Inline-run the batch transcribe pipeline (mock-friendly).

    For SaaS scaling this would normally publish to a worker; here we do it
    in-request so the dev/test experience is end-to-end without extra infra.
    """
    b = db.get(Batch, batch_id)
    if not b or b.user_id != user.id:
        raise HTTPException(status_code=404, detail="批次不存在")
    if b.status == "running":
        return _batch_to_out(b)
    b.status = "running"
    db.commit()

    from src.transcribe import RedrawEngine, RedrawParams, run_quality_loop

    work_root = pathlib.Path(settings.STORAGE_DIR) / "batch" / str(b.id)
    work_root.mkdir(parents=True, exist_ok=True)
    engine = RedrawEngine(work_root)

    default_params = RedrawParams.from_dict(
        json.loads(b.params_json) if b.params_json else {}
    )
    default_params.style = b.style
    default_params.genre = b.genre
    default_params.aspect_ratio = b.aspect_ratio

    rows = db.query(BatchItem).filter(BatchItem.batch_id == b.id).order_by(BatchItem.id).all()
    finished = 0
    for it in rows:
        it.status = "running"
        db.commit()
        params = RedrawParams.from_dict(json.loads(it.params_json) if it.params_json else {})
        # merge defaults
        params.style = params.style or default_params.style
        params.genre = params.genre or default_params.genre

        source = it.source_url
        if source.startswith("/storage/"):
            source = str(
                pathlib.Path(settings.STORAGE_DIR) / source.replace("/storage/", "", 1)
            )

        try:
            record = run_quality_loop(engine, it.id, source, params)
            it.result_url = _publish_local(record.final_output, b.id, f"item_{it.id:04d}.png")
            it.score_7d_json = json.dumps(record.final_scores, ensure_ascii=False)
            it.overall_score = record.overall
            it.passed = record.passed
            it.repair_iters = record.repair_iters
            it.status = "succeeded" if record.passed else "needs_review"
        except Exception as e:  # noqa: BLE001
            it.status = "failed"
            it.feedback = f"{e}"
        finally:
            finished += 1
            b.finished_items = finished
            db.commit()
            db.refresh(it)
    b.status = "succeeded"
    db.commit()
    db.refresh(b)
    return _batch_to_out(b)


@router.post("/{batch_id}/items/{item_id}/redraw", response_model=BatchItemOut)
def redraw_item(
    batch_id: int,
    item_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> BatchItemOut:
    b = db.get(Batch, batch_id)
    if not b or b.user_id != user.id:
        raise HTTPException(status_code=404, detail="批次不存在")
    it = db.get(BatchItem, item_id)
    if not it or it.batch_id != batch_id:
        raise HTTPException(status_code=404, detail="条目不存在")

    from src.transcribe import RedrawEngine, RedrawParams, run_quality_loop

    work_root = pathlib.Path(settings.STORAGE_DIR) / "batch" / str(b.id)
    engine = RedrawEngine(work_root)
    params = RedrawParams.from_dict(json.loads(it.params_json) if it.params_json else {})

    source = it.source_url
    if source.startswith("/storage/"):
        source = str(pathlib.Path(settings.STORAGE_DIR) / source.replace("/storage/", "", 1))

    record = run_quality_loop(engine, it.id, source, params)
    it.result_url = _publish_local(record.final_output, b.id, f"item_{it.id:04d}.png")
    it.score_7d_json = json.dumps(record.final_scores, ensure_ascii=False)
    it.overall_score = record.overall
    it.passed = record.passed
    it.repair_iters = record.repair_iters
    it.status = "succeeded" if record.passed else "needs_review"
    db.commit()
    db.refresh(it)
    return _item_to_out(it)


@router.get("/{batch_id}/export")
def export_batch(
    batch_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Build a zip of all finished items and return a downloadable URL."""
    from src.transcribe import export_batch_zip

    b = db.get(Batch, batch_id)
    if not b or b.user_id != user.id:
        raise HTTPException(status_code=404, detail="批次不存在")
    rows = (
        db.query(BatchItem)
        .filter(BatchItem.batch_id == b.id, BatchItem.result_url.is_not(None))
        .all()
    )
    items_dicts: list[dict] = []
    for it in rows:
        url = it.result_url or ""
        if url.startswith("/storage/"):
            local = str(pathlib.Path(settings.STORAGE_DIR) / url.replace("/storage/", "", 1))
        else:
            local = url
        items_dicts.append(
            {
                "item_id": it.id,
                "source": it.source_url,
                "final_output": local,
                "score_7d": json.loads(it.score_7d_json) if it.score_7d_json else {},
                "overall_score": it.overall_score,
                "passed": it.passed,
            }
        )
    zip_dir = pathlib.Path(settings.STORAGE_DIR) / "batch" / str(b.id) / "export"
    zip_dir.mkdir(parents=True, exist_ok=True)
    zip_path = zip_dir / f"batch_{b.id}.zip"
    export_batch_zip(b.id, items_dicts, zip_path)
    rel = zip_path.relative_to(pathlib.Path(settings.STORAGE_DIR))
    return {"url": f"/storage/{str(rel).replace(os.sep, '/')}", "items": len(items_dicts)}


def _publish_local(src_path: str, batch_id: int, name: str) -> str:
    src = pathlib.Path(src_path)
    dest_dir = pathlib.Path(settings.STORAGE_DIR) / "batch" / str(batch_id) / "results"
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / name
    if src.exists() and src.resolve() != dest.resolve():
        shutil.copy2(src, dest)
    rel = dest.relative_to(pathlib.Path(settings.STORAGE_DIR))
    return f"/storage/{str(rel).replace(os.sep, '/')}"
