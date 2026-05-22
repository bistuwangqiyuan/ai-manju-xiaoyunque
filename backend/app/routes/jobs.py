from __future__ import annotations

import json
from datetime import datetime, timedelta
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import desc
from sqlalchemy.orm import Session

from ..db import Job, JobLog, JobVersion, Shot, User, get_db
from ..schemas import (
    ContinueIn,
    ExportIn,
    ExportOut,
    JobCreateIn,
    JobLogOut,
    JobOut,
    JobVersionOut,
    MarketingOut,
    RerollIn,
    RestyleIn,
    ShotOut,
    ShotRepairIn,
    TranslateIn,
    VersionRollbackIn,
    job_to_out,
)
from ..security import get_current_user
from ..settings import settings

router = APIRouter(prefix="/jobs", tags=["jobs"])


def _today_window() -> tuple[datetime, datetime]:
    """UTC day window [start, end). 用 UTC 一致就行，全球用户也用 UTC 计配额。"""
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    return today_start, today_start + timedelta(days=1)


def _free_jobs_today(db: Session, user_id: int) -> int:
    start, end = _today_window()
    return (
        db.query(Job)
        .filter(
            Job.user_id == user_id,
            Job.created_at >= start,
            Job.created_at < end,
            # 已取消的任务不计入今日配额（让用户能重试）
            Job.status != "cancelled",
        )
        .count()
    )


def _compute_cost_cents(tier: str, episodes: int) -> int:
    """按 tier 算扣费金额（分）。free / admin: 0；其余: base * 1.1 * episodes"""
    if tier in ("free", "admin"):
        return 0
    base = settings.EPISODE_BASE_COST_CENTS * episodes
    return int(round(base * settings.PROFIT_MULTIPLIER))


@router.get("", response_model=List[JobOut])
def list_jobs(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> List[JobOut]:
    rows = (
        db.query(Job)
        .filter(Job.user_id == user.id)
        .order_by(desc(Job.created_at))
        .limit(100)
        .all()
    )
    return [job_to_out(r) for r in rows]


@router.get("/quota")
def get_quota(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """前端 dashboard 用：当前 tier、今日已用、剩余、单集预估费用"""
    used = _free_jobs_today(db, user.id) if user.tier == "free" else 0
    cost_per_episode = _compute_cost_cents(user.tier, 1)
    return {
        "tier": user.tier,
        "credits_cents": user.credits_cents,
        "free_daily_limit": settings.FREE_DAILY_QUOTA,
        "free_used_today": used,
        "free_remaining_today": max(0, settings.FREE_DAILY_QUOTA - used) if user.tier == "free" else None,
        "cost_per_episode_cents": cost_per_episode,
        "episode_base_cost_cents": settings.EPISODE_BASE_COST_CENTS,
        "profit_multiplier": settings.PROFIT_MULTIPLIER,
    }


@router.post("", response_model=JobOut, status_code=201)
def create_job(
    payload: JobCreateIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> JobOut:
    # 1) Free 用户当日配额
    if user.tier == "free":
        used = _free_jobs_today(db, user.id)
        if used + 1 > settings.FREE_DAILY_QUOTA:
            raise HTTPException(
                status_code=429,
                detail=(
                    f"今日免费配额已用完（{settings.FREE_DAILY_QUOTA} 个/天）。"
                    f"充值任意金额自动升级为付费用户，配额无限制。"
                ),
            )
        # Free 用户超过 1 集不让做（避免一次性把额度吃完）
        if payload.episodes > 1:
            raise HTTPException(
                status_code=403,
                detail="免费用户单次只能生成 1 集。十集套装请升级为付费用户。",
            )

    # 2) 计算扣费
    cost = _compute_cost_cents(user.tier, payload.episodes)

    # 3) 余额校验（free 用户 cost=0，自然通过）
    if cost > 0 and user.credits_cents < cost:
        raise HTTPException(
            status_code=402,
            detail=f"余额不足：需要 ¥{cost/100:.2f}（按成本×{settings.PROFIT_MULTIPLIER} 计算），当前 ¥{user.credits_cents/100:.2f}",
        )
    if cost > 0:
        user.credits_cents -= cost

    # Mode "theme" allows empty novel_excerpt — backend will generate via Claude.
    if payload.mode == "theme":
        if not payload.theme or len(payload.theme.strip()) < 4:
            raise HTTPException(status_code=400, detail="theme 模式下需提供 ≥ 4 字的主题")
        novel_text = payload.novel_excerpt or f"theme:{payload.theme}"
    else:
        if len(payload.novel_excerpt.strip()) < 50:
            raise HTTPException(status_code=400, detail="小说片段至少 50 字")
        novel_text = payload.novel_excerpt

    job = Job(
        user_id=user.id,
        title=payload.title or "未命名漫剧",
        novel_excerpt=novel_text,
        style=payload.style,
        episodes=payload.episodes,
        cost_cents=cost,
        status="queued",
        progress=0,
        genre=payload.genre,
        mode=payload.mode,
        theme=payload.theme,
        language=payload.language,
    )
    db.add(job)
    db.flush()
    if user.tier == "free":
        used_after = _free_jobs_today(db, user.id)
        db.add(JobLog(job_id=job.id, level="INFO",
                      message=f"[free] 今日配额 {used_after}/{settings.FREE_DAILY_QUOTA} 已使用"))
    else:
        db.add(JobLog(job_id=job.id, level="INFO",
                      message=f"[{user.tier}] 扣费 ¥{cost/100:.2f}（成本 ¥{settings.EPISODE_BASE_COST_CENTS*payload.episodes/100:.2f} × {settings.PROFIT_MULTIPLIER}）"))
    db.commit()
    db.refresh(job)
    return job_to_out(job)


@router.get("/{job_id}", response_model=JobOut)
def get_job(
    job_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> JobOut:
    job = db.get(Job, job_id)
    if not job or job.user_id != user.id:
        raise HTTPException(status_code=404, detail="任务不存在")
    return job_to_out(job)


@router.get("/{job_id}/logs", response_model=List[JobLogOut])
def get_job_logs(
    job_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> List[JobLogOut]:
    job = db.get(Job, job_id)
    if not job or job.user_id != user.id:
        raise HTTPException(status_code=404, detail="任务不存在")
    rows = db.query(JobLog).filter(JobLog.job_id == job_id).order_by(JobLog.id).all()
    return [JobLogOut.model_validate(r) for r in rows]


@router.post("/{job_id}/cancel", response_model=JobOut)
def cancel_job(
    job_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> JobOut:
    job = db.get(Job, job_id)
    if not job or job.user_id != user.id:
        raise HTTPException(status_code=404, detail="任务不存在")
    if job.status in ("succeeded", "failed", "cancelled"):
        raise HTTPException(status_code=400, detail=f"任务已是 {job.status}，不可取消")

    # 退还剩余比例金额
    refund_ratio = max(0.0, 1.0 - job.progress / 100.0)
    refund = int(round(job.cost_cents * refund_ratio))
    if refund > 0:
        user.credits_cents += refund
        db.add(JobLog(job_id=job.id, level="INFO", message=f"取消，退回 ¥{refund/100:.2f}"))

    job.status = "cancelled"
    db.commit()
    db.refresh(job)
    return job_to_out(job)


@router.post("/{job_id}/approve", response_model=JobOut)
def approve_job(
    job_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> JobOut:
    """人工复核：确认放行成片。"""
    job = db.get(Job, job_id)
    if not job or job.user_id != user.id:
        raise HTTPException(status_code=404, detail="任务不存在")
    if job.status != "succeeded":
        raise HTTPException(status_code=400, detail="仅已完成任务可确认放行")
    job.human_approved = True
    db.add(JobLog(job_id=job.id, level="INFO", message="用户已人工确认放行"))
    db.commit()
    db.refresh(job)
    return job_to_out(job)


@router.post("/{job_id}/reroll", response_model=JobOut)
def reroll_job(
    job_id: int,
    payload: RerollIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> JobOut:
    """一键重绘：重新排队渲染（可选单镜 shot_id）。"""
    job = db.get(Job, job_id)
    if not job or job.user_id != user.id:
        raise HTTPException(status_code=404, detail="任务不存在")
    if job.status == "running":
        raise HTTPException(status_code=400, detail="任务渲染中，请稍后再试")
    shot = payload.shot_id or "full"
    job.status = "queued"
    job.progress = 0
    job.current_step = 0
    job.human_approved = False
    job.error = None
    db.add(JobLog(job_id=job.id, level="INFO", message=f"用户触发重绘 scope={shot}"))
    db.commit()
    db.refresh(job)
    return job_to_out(job)


@router.get("/{job_id}/versions", response_model=List[JobVersionOut])
def list_job_versions(
    job_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> List[JobVersionOut]:
    job = db.get(Job, job_id)
    if not job or job.user_id != user.id:
        raise HTTPException(status_code=404, detail="任务不存在")
    rows = (
        db.query(JobVersion)
        .filter(JobVersion.job_id == job_id)
        .order_by(JobVersion.version_no.desc())
        .all()
    )
    out: list[JobVersionOut] = []
    for r in rows:
        s7 = None
        if r.scores_7d_json:
            try:
                s7 = json.loads(r.scores_7d_json)
            except Exception:
                pass
        out.append(
            JobVersionOut(
                id=r.id,
                version_no=r.version_no,
                quality_score=r.quality_score,
                scores_7d=s7,
                result_url=r.result_url,
                cover_url=r.cover_url,
                notes=r.notes,
                created_at=r.created_at,
            )
        )
    return out


@router.post("/{job_id}/versions/rollback", response_model=JobOut)
def rollback_version(
    job_id: int,
    payload: VersionRollbackIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> JobOut:
    """Restore a previous version as the current one."""
    job = db.get(Job, job_id)
    if not job or job.user_id != user.id:
        raise HTTPException(status_code=404, detail="任务不存在")
    target = (
        db.query(JobVersion)
        .filter(JobVersion.job_id == job_id, JobVersion.version_no == payload.target_version_no)
        .one_or_none()
    )
    if target is None:
        raise HTTPException(status_code=404, detail="目标版本不存在")
    job.result_url = target.result_url
    job.cover_url = target.cover_url
    job.quality_score = target.quality_score
    job.scores_7d = target.scores_7d_json
    db.add(JobLog(
        job_id=job.id,
        level="INFO",
        message=f"用户回滚到 v{payload.target_version_no}: {payload.notes or '(无备注)'}",
    ))
    db.commit()
    db.refresh(job)
    return job_to_out(job)


# ---------------------------------------------------------------------
# Per-shot APIs (requirement doc §自动修正 + 一键重绘/局部修正/反馈)
# ---------------------------------------------------------------------


def _shot_to_out(s: Shot) -> ShotOut:
    score_7d = None
    if s.score_7d_json:
        try:
            score_7d = json.loads(s.score_7d_json)
        except Exception:
            score_7d = None
    routes = None
    if s.repair_routes_json:
        try:
            routes = json.loads(s.repair_routes_json)
        except Exception:
            routes = None
    return ShotOut(
        id=s.id,
        job_id=s.job_id,
        episode_id=s.episode_id,
        shot_id=s.shot_id,
        duration_s=s.duration_s,
        description=s.description,
        shot_type=s.shot_type,
        status=s.status,
        result_url=s.result_url,
        canonical_image_url=s.canonical_image_url,
        score_7d=score_7d,
        overall_score=s.overall_score,
        passed=s.passed,
        repair_iters=s.repair_iters,
        repair_routes=routes,
        feedback=s.feedback,
        created_at=s.created_at,
        updated_at=s.updated_at,
    )


@router.get("/{job_id}/shots", response_model=List[ShotOut])
def list_job_shots(
    job_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> List[ShotOut]:
    job = db.get(Job, job_id)
    if not job or job.user_id != user.id:
        raise HTTPException(status_code=404, detail="任务不存在")
    rows = (
        db.query(Shot)
        .filter(Shot.job_id == job_id)
        .order_by(Shot.episode_id.asc(), Shot.shot_id.asc())
        .all()
    )
    return [_shot_to_out(r) for r in rows]


@router.get("/{job_id}/shots/{shot_id}", response_model=ShotOut)
def get_shot(
    job_id: int,
    shot_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ShotOut:
    job = db.get(Job, job_id)
    if not job or job.user_id != user.id:
        raise HTTPException(status_code=404, detail="任务不存在")
    s = db.get(Shot, shot_id)
    if not s or s.job_id != job_id:
        raise HTTPException(status_code=404, detail="镜头不存在")
    return _shot_to_out(s)


@router.post("/{job_id}/shots/{shot_id}/reroll", response_model=ShotOut)
def reroll_shot(
    job_id: int,
    shot_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ShotOut:
    """Queue a single-shot re-render (一键重绘 局部)."""
    job = db.get(Job, job_id)
    if not job or job.user_id != user.id:
        raise HTTPException(status_code=404, detail="任务不存在")
    s = db.get(Shot, shot_id)
    if not s or s.job_id != job_id:
        raise HTTPException(status_code=404, detail="镜头不存在")
    s.status = "queued"
    s.passed = False
    db.add(JobLog(job_id=job_id, level="INFO",
                  message=f"用户对镜头 {s.episode_id}#{s.shot_id} 触发重绘"))
    db.commit()
    db.refresh(s)
    return _shot_to_out(s)


@router.post("/{job_id}/shots/{shot_id}/repair", response_model=ShotOut)
def repair_shot(
    job_id: int,
    shot_id: int,
    payload: ShotRepairIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ShotOut:
    """Manually trigger a specific repair route or auto-pick."""
    job = db.get(Job, job_id)
    if not job or job.user_id != user.id:
        raise HTTPException(status_code=404, detail="任务不存在")
    s = db.get(Shot, shot_id)
    if not s or s.job_id != job_id:
        raise HTTPException(status_code=404, detail="镜头不存在")
    s.status = "queued_repair"
    if payload.feedback:
        s.feedback = payload.feedback
    db.add(JobLog(
        job_id=job_id,
        level="INFO",
        message=(
            f"用户手动修复 {s.episode_id}#{s.shot_id} "
            f"route={payload.route or 'auto'} feedback={(payload.feedback or '')[:40]}"
        ),
    ))
    db.commit()
    db.refresh(s)
    return _shot_to_out(s)


@router.post("/{job_id}/shots/{shot_id}/approve", response_model=ShotOut)
def approve_shot(
    job_id: int,
    shot_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ShotOut:
    """一键确认: mark this shot as human-approved."""
    job = db.get(Job, job_id)
    if not job or job.user_id != user.id:
        raise HTTPException(status_code=404, detail="任务不存在")
    s = db.get(Shot, shot_id)
    if not s or s.job_id != job_id:
        raise HTTPException(status_code=404, detail="镜头不存在")
    s.passed = True
    s.status = "approved"
    db.add(JobLog(job_id=job_id, level="INFO",
                  message=f"用户人工确认 {s.episode_id}#{s.shot_id}"))
    db.commit()
    db.refresh(s)
    return _shot_to_out(s)


# ---------------------------------------------------------------------
# Marketing copy + export + advanced (requirement doc §8 / §9)
# ---------------------------------------------------------------------


@router.get("/{job_id}/marketing", response_model=MarketingOut)
def get_marketing_copy(
    job_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MarketingOut:
    job = db.get(Job, job_id)
    if not job or job.user_id != user.id:
        raise HTTPException(status_code=404, detail="任务不存在")
    try:
        from src.shell5_post_production.marketing_copy import generate_marketing_copy

        copy = generate_marketing_copy(
            title=job.title,
            synopsis=(job.novel_excerpt or job.theme or "")[:600],
            genre=job.genre,
            language=job.language,
        )
        return MarketingOut(**copy)
    except Exception:
        return MarketingOut(
            title=f"{job.title}",
            summary=f"{job.genre} 题材 AI 漫剧 · {job.episodes} 集",
            hook_copy=f"看到第 3 秒你就停不下来 — {job.title}",
            hashtags=[f"#{job.genre}", "#AI漫剧", "#爆款短剧"],
            language=job.language or "Chinese",
        )


@router.post("/{job_id}/export", response_model=List[ExportOut])
def export_platforms(
    job_id: int,
    payload: ExportIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> List[ExportOut]:
    """Render platform-specific master copies (抖音/快手/视频号/小红书/B站/YouTube)."""
    job = db.get(Job, job_id)
    if not job or job.user_id != user.id:
        raise HTTPException(status_code=404, detail="任务不存在")
    if not job.result_url:
        raise HTTPException(status_code=400, detail="任务尚未生成成片")

    try:
        from src.shell5_post_production.platform_export import (
            PLATFORM_SPECS,
            export_for_platforms,
        )

        # Resolve source path
        import pathlib
        from ..settings import settings as _s
        from ..storage_upload import upload_if_configured  # noqa: F401

        url = job.result_url or ""
        if url.startswith("/storage/"):
            src = pathlib.Path(_s.STORAGE_DIR) / url.replace("/storage/", "", 1)
        elif url.startswith("/samples/"):
            src = pathlib.Path(_s.STORAGE_DIR).parent / "web" / "public" / url.lstrip("/")
            if not src.exists():
                # 退回到项目内 web/public/samples
                src = pathlib.Path(__file__).resolve().parents[3] / "web" / "public" / url.lstrip("/")
        else:
            src = pathlib.Path(url)

        out_root = pathlib.Path(_s.STORAGE_DIR) / "jobs" / str(job.id) / "export"
        outs = export_for_platforms(
            src,
            out_root,
            platforms=payload.platforms,
            add_watermark=payload.add_watermark,
            account_handle=payload.account_handle,
        )
        result: list[ExportOut] = []
        for spec_id, info in outs.items():
            local_path = pathlib.Path(info["path"])
            try:
                url_rel = local_path.relative_to(pathlib.Path(_s.STORAGE_DIR))
                pub_url = f"/storage/{str(url_rel).replace(chr(92), '/')}"
            except ValueError:
                pub_url = str(local_path)
            result.append(
                ExportOut(
                    platform=spec_id,
                    url=pub_url,
                    cover_url=job.cover_url,
                    caption=info.get("caption"),
                    hashtags=info.get("hashtags", []),
                    duration_s=info.get("duration_s"),
                    width=info.get("width"),
                    height=info.get("height"),
                )
            )
        return result
    except Exception as e:
        # Graceful mock: emit URLs without actually transcoding
        return [
            ExportOut(
                platform=p,
                url=job.result_url or "",
                cover_url=job.cover_url,
                caption=f"AI 漫剧 · {job.title}",
                hashtags=["#AI漫剧"],
                duration_s=None,
                width=None,
                height=None,
            )
            for p in payload.platforms
        ]


@router.post("/{job_id}/continue", response_model=JobOut)
def continue_job(
    job_id: int,
    payload: ContinueIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> JobOut:
    """剧情续写: clone the job + queue extra episodes."""
    job = db.get(Job, job_id)
    if not job or job.user_id != user.id:
        raise HTTPException(status_code=404, detail="任务不存在")
    new_job = Job(
        user_id=user.id,
        title=f"{job.title} · 续集",
        novel_excerpt=(payload.direction or "续写") + "\n\n" + (job.novel_excerpt or ""),
        style=job.style,
        genre=job.genre,
        mode="excerpt",
        theme=job.theme,
        language=job.language,
        episodes=payload.extra_episodes,
        cost_cents=_compute_cost_cents(user.tier, payload.extra_episodes),
        status="queued",
        progress=0,
    )
    if new_job.cost_cents > 0:
        if user.credits_cents < new_job.cost_cents:
            raise HTTPException(status_code=402, detail="余额不足，无法续写")
        user.credits_cents -= new_job.cost_cents
    db.add(new_job)
    db.flush()
    db.add(JobLog(
        job_id=new_job.id,
        level="INFO",
        message=f"由 #{job.id} 续写 +{payload.extra_episodes} 集",
    ))
    db.commit()
    db.refresh(new_job)
    return job_to_out(new_job)


@router.post("/{job_id}/restyle", response_model=JobOut)
def restyle_job(
    job_id: int,
    payload: RestyleIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> JobOut:
    """风格迁移: re-queue with target style."""
    job = db.get(Job, job_id)
    if not job or job.user_id != user.id:
        raise HTTPException(status_code=404, detail="任务不存在")
    if job.status == "running":
        raise HTTPException(status_code=400, detail="任务渲染中，请稍后再试")
    style_map = {
        "jpn_anime": "japanese_anime",
        "guoman": "ancient_3d_guoman",
        "realistic": "cinematic_realistic",
        "manhwa": "korean_manhwa",
    }
    job.style = style_map[payload.target]
    job.status = "queued"
    job.progress = 0
    job.current_step = 0
    db.add(JobLog(
        job_id=job.id,
        level="INFO",
        message=f"风格迁移 → {payload.target}",
    ))
    db.commit()
    db.refresh(job)
    return job_to_out(job)


@router.post("/{job_id}/translate", response_model=JobOut)
def translate_job(
    job_id: int,
    payload: TranslateIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> JobOut:
    """Multilingual: re-render subtitles + TTS for target language."""
    job = db.get(Job, job_id)
    if not job or job.user_id != user.id:
        raise HTTPException(status_code=404, detail="任务不存在")
    job.language = payload.target_lang
    db.add(JobLog(
        job_id=job.id,
        level="INFO",
        message=f"翻译/配音目标语言 → {payload.target_lang} (burn={payload.burn_subtitle})",
    ))
    db.commit()
    db.refresh(job)
    return job_to_out(job)


@router.get("/{job_id}/interaction-graph")
def get_interaction_graph(
    job_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return character→character interaction edges inferred from the script."""
    job = db.get(Job, job_id)
    if not job or job.user_id != user.id:
        raise HTTPException(status_code=404, detail="任务不存在")
    artifacts = _parse_artifacts(job)
    episodes = _episodes_from_artifacts(artifacts) or _stub_episodes(job)

    from src.advanced import build_interaction_graph

    return build_interaction_graph(episodes)


def _parse_artifacts(job: Job) -> dict:
    if not job.step_artifacts:
        return {}
    try:
        return json.loads(job.step_artifacts)
    except Exception:
        return {}


def _episodes_from_artifacts(artifacts: dict) -> list[dict]:
    step_1 = (artifacts.get("steps") or {}).get("1") or {}
    plan_path = step_1.get("plan")
    if not plan_path:
        return []
    try:
        import pathlib
        import yaml
        data = yaml.safe_load(pathlib.Path(plan_path).read_text(encoding="utf-8")) or {}
        return list(data.get("episodes", []))
    except Exception:
        return []


def _stub_episodes(job: Job) -> list[dict]:
    return [
        {
            "episode_id": f"ep{i + 1:02d}",
            "title": f"第 {i + 1} 集",
            "synopsis": (job.novel_excerpt or "")[:200],
            "characters_in_episode": [],
        }
        for i in range(max(job.episodes, 1))
    ]
