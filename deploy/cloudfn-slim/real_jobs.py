"""真实视频生成任务的「无状态 SCF + COS KV」状态机.

把火山「小云雀-短剧漫剧 Agent」的 4 阶段流程拆成可单步推进的 finite state
machine, 每次 GET /api/jobs/{id} 调用 `step` 让状态机往前推一格。
状态全部存在 Tencent COS 的对象里, 跨 SCF 实例完全可见。

阶段：
    script_analysis   (0%   → 25%, 火山典型 ~4 min)
    material_design   (25%  → 50%, 火山典型 ~10 min)
    video_generate    (50%  → 85%, 火山典型 ~7 min × 集数)
    video_compose     (85%  → 100%, 火山典型 ~1 min × 集数)
    done              结果 final_video_url + final_video_cover_url
    failed            error + message

为了控制成本与首屏体验, MVP 默认只渲染 EpisodeIDs[0] 第一集; 多集套装在
后续迭代中开放。
"""
from __future__ import annotations

import logging
import os
import time
import uuid
from typing import Any

try:
    from . import cos_kv  # type: ignore[import-not-found]
    from . import manju_client  # type: ignore[import-not-found]
    from . import happyhorse_client  # type: ignore[import-not-found]
except ImportError:  # 直接被 SCF 当作顶层模块加载
    import cos_kv  # type: ignore[no-redef]
    import manju_client  # type: ignore[no-redef]
    import happyhorse_client  # type: ignore[no-redef]

_log = logging.getLogger(__name__)

PROVIDER_MANJU = "manju"
PROVIDER_HAPPYHORSE = "happyhorse"

# 火山限流后冷却时长（秒）。期间新任务直接路由到 HappyHorse。
_CB_COOLDOWN_S = 300
# 全局熔断器状态在 COS 中的 key
_CB_KEY = "xyq-state/_global/manju_circuit_breaker.json"

# 题材→默认首帧图（HappyHorse i2v 必须有 first_frame）。
# 这些是项目内的真实样片封面，与首页 Showcase 同源。
_DEFAULT_FIRST_FRAMES = {
    "ancient": "https://cursoraicode-5g67ezfl8a1891da-1300352403.tcloudbaseapp.com/samples/nie01_lanruosi.jpg",
    "modern": "https://cursoraicode-5g67ezfl8a1891da-1300352403.tcloudbaseapp.com/samples/real05_moon_corridor.jpg",
    "sweet_pet": "https://cursoraicode-5g67ezfl8a1891da-1300352403.tcloudbaseapp.com/samples/real06_spirit_hook.jpg",
    "suspense": "https://cursoraicode-5g67ezfl8a1891da-1300352403.tcloudbaseapp.com/samples/nie03_yan_chixia.jpg",
    "xuanhuan": "https://cursoraicode-5g67ezfl8a1891da-1300352403.tcloudbaseapp.com/samples/xiyou01_immortal_stone.jpg",
}
_DEFAULT_FIRST_FRAME_FALLBACK = _DEFAULT_FIRST_FRAMES["ancient"]


def _circuit_breaker_state() -> dict:
    try:
        return cos_kv.get_json(_CB_KEY) or {}
    except Exception:  # noqa: BLE001
        return {}


def _circuit_breaker_tripped() -> tuple[bool, dict]:
    """Returns (tripped_now, current_state)."""
    cb = _circuit_breaker_state()
    until = int(cb.get("tripped_until_ts") or 0)
    return (_now() < until, cb)


def _circuit_breaker_trip(code: Any, error: str) -> None:
    cb = {
        "tripped_until_ts": _now() + _CB_COOLDOWN_S,
        "last_code": code,
        "last_error": (error or "")[:300],
        "last_tripped_at_ts": _now(),
    }
    try:
        cos_kv.put_json(_CB_KEY, cb)
    except Exception as e:  # noqa: BLE001
        _log.warning("circuit_breaker_trip: COS put failed: %s", e)


def _is_rate_limited_manju_error(e: Exception) -> bool:
    if not isinstance(e, manju_client.ManjuError):
        return False
    return e.code in manju_client.RATE_LIMIT_CODES


def _default_first_frame(genre: str) -> str:
    return _DEFAULT_FIRST_FRAMES.get((genre or "").strip().lower(),
                                     _DEFAULT_FIRST_FRAME_FALLBACK)


def _hh_prompt_from_state(state: dict, ep_id: str) -> str:
    """合成给 HappyHorse 的 prompt：剧本节选 + 视觉风格 + 集号提示。"""
    excerpt = (state.get("novel_excerpt") or "")[:1200]
    style = state.get("visual_style") or "2D, 国风, 平涂"
    title = state.get("title") or "未命名漫剧"
    return (
        f"{title} · 第 {ep_id} 集\n"
        f"剧情：{excerpt}\n"
        f"视觉风格：{style}；9:16 竖屏短剧；镜头连贯，光影自然。"
    )


STAGE_SCRIPT = "script_analysis"
STAGE_MATERIAL = "material_design"
STAGE_VIDEO_GEN = "video_generate"
STAGE_VIDEO_COMPOSE = "video_compose"
STAGE_DONE = "done"
STAGE_FAILED = "failed"

STAGE_PROGRESS_FLOOR = {
    STAGE_SCRIPT: 0,
    STAGE_MATERIAL: 25,
    STAGE_VIDEO_GEN: 50,
    STAGE_VIDEO_COMPOSE: 85,
    STAGE_DONE: 100,
    STAGE_FAILED: 0,
}
STAGE_PROGRESS_CEIL = {
    STAGE_SCRIPT: 25,
    STAGE_MATERIAL: 50,
    STAGE_VIDEO_GEN: 85,
    STAGE_VIDEO_COMPOSE: 99,
    STAGE_DONE: 100,
    STAGE_FAILED: 0,
}
STAGE_LABEL_ZH = {
    STAGE_SCRIPT: "Step1: 剧本拆解与分镜规划",
    STAGE_MATERIAL: "Step2: 角色与场景资产生成",
    STAGE_VIDEO_GEN: "Step3: 分镜视频抽卡渲染",
    STAGE_VIDEO_COMPOSE: "Step4: 视频合成 + 字幕 + 旁白",
    STAGE_DONE: "Step5: 完成（成片可下载）",
    STAGE_FAILED: "Step6: 任务失败",
}

REAL_VIDEO_MODE_ENV = "REAL_VIDEO_MODE"
MAX_EPISODES_DEFAULT = 1  # MVP: 只跑首集


# ---------------------------------------------------------------------------
# Mode detection
# ---------------------------------------------------------------------------

def is_real_mode_enabled() -> bool:
    mode = os.environ.get(REAL_VIDEO_MODE_ENV, "").strip().lower()
    if mode not in {"manju", "manju_agent", "real", "1", "true", "on"}:
        return False
    if not manju_client.is_configured():
        _log.warning("REAL_VIDEO_MODE set but VOLC AK/SK missing → fall back to mock")
        return False
    if not cos_kv.is_configured():
        _log.warning("REAL_VIDEO_MODE set but COS not configured → fall back to mock")
        return False
    return True


# ---------------------------------------------------------------------------
# State helpers (COS-backed)
# ---------------------------------------------------------------------------

def _state_key(user_id: int, job_id: int) -> str:
    return f"xyq-state/{user_id}/jobs/{job_id}.json"


def _list_prefix(user_id: int) -> str:
    return f"xyq-state/{user_id}/jobs/"


def _script_key(user_id: int, job_id: int) -> str:
    return f"xyq-scripts/{user_id}/{job_id}.txt"


def _now() -> int:
    return int(time.time())


def load_state(user_id: int, job_id: int) -> dict | None:
    return cos_kv.get_json(_state_key(user_id, job_id))


def save_state(state: dict) -> None:
    state["updated_at_ts"] = _now()
    cos_kv.put_json(_state_key(state["user_id"], state["job_id"]), state)


def list_user_jobs(user_id: int) -> list[dict]:
    keys = cos_kv.list_keys_under(_list_prefix(user_id))
    out: list[dict] = []
    for k in keys:
        try:
            data = cos_kv.get_json(k)
            if data:
                out.append(data)
        except Exception as e:  # noqa: BLE001
            _log.warning("list_user_jobs: get %s failed: %s", k, e)
    out.sort(key=lambda j: j.get("created_at_ts", 0), reverse=True)
    return out


def _append_log(state: dict, level: str, message: str) -> None:
    logs = state.setdefault("logs", [])
    logs.append({"ts": _now(), "level": level, "message": message})
    state["logs"] = logs[-100:]


# ---------------------------------------------------------------------------
# Submit (POST /api/jobs)
# ---------------------------------------------------------------------------

def create_job(*, user_id: int, user_email: str, novel_excerpt: str, title: str,
               style: str, genre: str, language: str, episodes: int,
               aspect_ratio: str, mode: str, theme: str | None,
               cost_cents: int) -> dict:
    """Upload script + submit Manju script_analysis + persist state. Returns job dict."""
    job_id = int(time.time())

    script_key = _script_key(user_id, job_id)
    script_url_signed = ""
    cos_err: str | None = None
    try:
        cos_kv.put_text_public(script_key, novel_excerpt)
        script_url_signed = cos_kv.presigned_get_url(script_key, expire_seconds=24 * 3600)
    except Exception as e:  # noqa: BLE001
        cos_err = str(e)[:200]
        _log.exception("[%s] upload script to COS failed", job_id)

    visual_style = _to_visual_style(style)
    video_ratio = _normalize_ratio(aspect_ratio)

    script_task_id = ""
    submit_err: str | None = None
    if script_url_signed and not cos_err:
        try:
            script_task_id = manju_client.submit_script_analysis(
                script_url_signed,
                visual_style=visual_style,
                video_ratio=video_ratio,
                file_type="txt",
                file_name=f"{job_id}.txt",
            )
        except Exception as e:  # noqa: BLE001
            submit_err = str(e)[:300]
            _log.exception("[%s] submit_script_analysis failed", job_id)

    init_stage = STAGE_SCRIPT if script_task_id else STAGE_FAILED
    init_status = "queued" if script_task_id else "failed"
    init_error = None
    if not script_task_id:
        init_error = submit_err or cos_err or "submit failed"

    state: dict[str, Any] = {
        "schema": 1,
        "job_id": job_id,
        "user_id": user_id,
        "user_email": user_email,
        "title": title or "未命名漫剧",
        "novel_excerpt": novel_excerpt,
        "style": style,
        "visual_style": visual_style,
        "video_ratio": video_ratio,
        "genre": genre or "ancient",
        "language": language or "Chinese",
        "episodes_requested": int(episodes or 1),
        "max_episodes_to_render": min(int(episodes or 1), MAX_EPISODES_DEFAULT),
        "mode": mode or "excerpt",
        "theme": theme,
        "aspect_ratio": aspect_ratio,
        "cost_cents": cost_cents,
        "created_at_ts": job_id,
        "updated_at_ts": job_id,
        "stage": init_stage,
        "status": init_status,
        "progress": 0 if init_status != "failed" else 0,
        "error": init_error,
        "script_url": script_url_signed,
        "script_task_id": script_task_id,
        "material_task_id": "",
        "assets_id": "",
        "thread_id": "",
        "episode_ids": [],
        "ep_state": [],
        "current_ep_idx": 0,
        "result_url": None,
        "cover_url": None,
        "logs": [],
        "engine": "manju_agent_v2",
    }
    if cos_err:
        _append_log(state, "ERROR", f"剧本上传 COS 失败：{cos_err}")
    if submit_err:
        _append_log(state, "ERROR", f"火山 Agent submit 失败：{submit_err}")
    if script_task_id:
        _append_log(state, "INFO",
                    f"已提交剧本解析 (manju_task_id={script_task_id})；下一步：等待 Agent 完成剧本解析")
    save_state(state)
    return state


# ---------------------------------------------------------------------------
# Step (called on every GET /api/jobs/{id})
# ---------------------------------------------------------------------------

_MAX_AUTO_RETRY = 2  # 同一任务 step 级最多自动重试次数（针对 transient 错误）


def step(state: dict) -> dict:
    """Advance the state machine one tick; persist if anything changes.

    稳定性保障：
    - 火山 50429/50430（限流）：触发 5 分钟全局熔断 + 自动切换到 HappyHorse；同一任务最多自动重试 2 次。
    - HappyHorse 任务失败：保留错误并标记 failed，由用户手动 reroll。
    - 其他 transient 异常（网络/超时）：自动重试 ≤2 次后才置 failed。
    """
    if state.get("status") in {"succeeded", "failed", "cancelled"}:
        return state
    stage = state.get("stage", STAGE_SCRIPT)
    try:
        if stage == STAGE_SCRIPT:
            _step_script_analysis(state)
        elif stage == STAGE_MATERIAL:
            _step_material_design(state)
        elif stage == STAGE_VIDEO_GEN:
            _step_video_generate(state)
        elif stage == STAGE_VIDEO_COMPOSE:
            _step_video_compose(state)
    except manju_client.ManjuError as e:
        retries = int(state.get("auto_retry_count") or 0)
        if _is_rate_limited_manju_error(e):
            _circuit_breaker_trip(e.code, str(e))
        if (_is_rate_limited_manju_error(e) or e.code in manju_client.RETRYABLE_CODES) \
                and retries < _MAX_AUTO_RETRY:
            state["auto_retry_count"] = retries + 1
            _append_log(state, "WARN",
                        f"火山可重试错误 {e}（自动重试 {retries + 1}/{_MAX_AUTO_RETRY}）")
            # 不置 failed，让下一次 poll 重新进入同一 stage
        else:
            _append_log(state, "ERROR", f"火山 Agent 错误：{e}")
            state["status"] = "failed"
            state["stage"] = STAGE_FAILED
            state["error"] = str(e)[:300]
    except happyhorse_client.HappyHorseError as e:
        retries = int(state.get("auto_retry_count") or 0)
        if retries < _MAX_AUTO_RETRY:
            state["auto_retry_count"] = retries + 1
            _append_log(state, "WARN",
                        f"HappyHorse 可重试错误 {e}（自动重试 {retries + 1}/{_MAX_AUTO_RETRY}）")
        else:
            _append_log(state, "ERROR", f"HappyHorse 错误：{e}")
            state["status"] = "failed"
            state["stage"] = STAGE_FAILED
            state["error"] = str(e)[:300]
    except Exception as e:  # noqa: BLE001
        _log.exception("[%s] step failed at stage=%s", state.get("job_id"), stage)
        retries = int(state.get("auto_retry_count") or 0)
        if retries < _MAX_AUTO_RETRY:
            state["auto_retry_count"] = retries + 1
            _append_log(state, "WARN",
                        f"内部异常（瞬时）：{e}（自动重试 {retries + 1}/{_MAX_AUTO_RETRY}）")
        else:
            _append_log(state, "ERROR", f"内部异常：{e}")
            state["status"] = "failed"
            state["stage"] = STAGE_FAILED
            state["error"] = str(e)[:300]

    state["progress"] = _compute_progress(state)
    if state["stage"] != STAGE_FAILED and state["stage"] != STAGE_DONE:
        state["status"] = "running" if state["progress"] > 0 else "queued"

    save_state(state)
    return state


def _step_script_analysis(state: dict) -> None:
    task_id = state.get("script_task_id")
    if not task_id:
        state["status"] = "failed"
        state["stage"] = STAGE_FAILED
        state["error"] = "missing script_task_id"
        return
    data = manju_client.query(manju_client.REQ_KEY_SCRIPT_ANALYSIS, task_id)
    status = (data.get("status") or "").lower()
    if status == manju_client.STATUS_DONE:
        resp = manju_client.parse_resp_data(data.get("resp_data"))
        assets_id = resp.get("assets_id")
        thread_id = resp.get("thread_id")
        ep_ids = manju_client.extract_episode_ids(resp)
        if not assets_id or not thread_id or not ep_ids:
            raise manju_client.ManjuError(
                None, f"script_analysis missing fields: assets_id={assets_id!r} "
                      f"thread_id={thread_id!r} eps={ep_ids!r}"
            )
        state["assets_id"] = assets_id
        state["thread_id"] = thread_id
        state["episode_ids"] = ep_ids
        _append_log(state, "INFO",
                    f"剧本解析完成 → assets={assets_id[:12]}… 共 {len(ep_ids)} 集；提交资产生成")
        mat_tid = manju_client.submit_material_design(assets_id, thread_id)
        state["material_task_id"] = mat_tid
        state["stage"] = STAGE_MATERIAL
        _append_log(state, "INFO", f"已提交资产生成 (task_id={mat_tid})")
    elif status in {manju_client.STATUS_FAILED, manju_client.STATUS_NOT_FOUND,
                    manju_client.STATUS_EXPIRED}:
        raise manju_client.ManjuError(
            None, f"script_analysis terminal status={status}: {data.get('message')}"
        )


def _step_material_design(state: dict) -> None:
    task_id = state.get("material_task_id")
    if not task_id:
        raise manju_client.ManjuError(None, "missing material_task_id")
    data = manju_client.query(manju_client.REQ_KEY_MATERIAL_DESIGN, task_id)
    status = (data.get("status") or "").lower()
    if status == manju_client.STATUS_DONE:
        _append_log(state, "INFO", "资产生成完成（角色+场景图就绪）；提交首集视频抽卡")
        max_eps = max(1, int(state.get("max_episodes_to_render") or 1))
        ep_ids = state.get("episode_ids") or []
        if not ep_ids:
            raise manju_client.ManjuError(None, "no episode_ids available")
        state["ep_state"] = [
            {"ep_id": eid, "video_task_id": "", "compose_task_id": "",
             "final_video_url": "", "final_video_cover_url": "",
             "stage": "pending"}
            for eid in ep_ids[:max_eps]
        ]
        state["current_ep_idx"] = 0
        first = state["ep_state"][0]
        first["provider"] = PROVIDER_MANJU
        tripped, _ = _circuit_breaker_tripped()
        if tripped and happyhorse_client.is_configured():
            _append_log(state, "WARN",
                        "火山熔断器开启（最近 5 分钟内被限流），直接采用 HappyHorse 引擎")
            _switch_ep_to_happyhorse(state, 0)
            return
        try:
            vid_tid = manju_client.submit_video_generate(
                state["assets_id"], state["thread_id"], first["ep_id"]
            )
        except manju_client.ManjuError as e:
            if _is_rate_limited_manju_error(e) and happyhorse_client.is_configured():
                _circuit_breaker_trip(e.code, str(e))
                _append_log(state, "WARN",
                            f"火山抽卡限流 [{e.code}]，EP#{first['ep_id']} 切换 HappyHorse")
                _switch_ep_to_happyhorse(state, 0)
                return
            raise
        first["video_task_id"] = vid_tid
        first["stage"] = STAGE_VIDEO_GEN
        state["stage"] = STAGE_VIDEO_GEN
        _append_log(state, "INFO",
                    f"已提交 EP#{first['ep_id']} 视频抽卡 (task_id={vid_tid})")
    elif status in {manju_client.STATUS_FAILED, manju_client.STATUS_NOT_FOUND,
                    manju_client.STATUS_EXPIRED}:
        raise manju_client.ManjuError(
            None, f"material_design terminal status={status}: {data.get('message')}"
        )


def _step_video_generate(state: dict) -> None:
    """Stage 3 — 分镜视频抽卡。

    优先走火山 Manju；若 EP 已切换到 HappyHorse（provider=happyhorse），则查询
    HappyHorse 任务并把 video_url 直接写到 final_video_url，跳过 compose 阶段。
    """
    idx = int(state.get("current_ep_idx") or 0)
    eps = state.get("ep_state") or []
    if idx >= len(eps):
        raise manju_client.ManjuError(None, f"ep_state[{idx}] out of range")
    cur = eps[idx]
    provider = cur.get("provider") or PROVIDER_MANJU

    if provider == PROVIDER_HAPPYHORSE:
        _poll_happyhorse_video(state, idx)
        return

    task_id = cur.get("video_task_id")
    if not task_id:
        raise manju_client.ManjuError(None, "missing video_task_id")
    data = manju_client.query(manju_client.REQ_KEY_VIDEO_GEN_FAST, task_id)
    status = (data.get("status") or "").lower()
    if status == manju_client.STATUS_DONE:
        _append_log(state, "INFO",
                    f"EP#{cur['ep_id']} 视频抽卡完成；提交视频合成")
        try:
            comp_tid = manju_client.submit_video_compose(
                state["assets_id"], state["thread_id"], cur["ep_id"]
            )
        except manju_client.ManjuError as e:
            if _is_rate_limited_manju_error(e) and happyhorse_client.is_configured():
                _circuit_breaker_trip(e.code, str(e))
                _append_log(state, "WARN",
                            f"火山合成限流 [{e.code}]，EP#{cur['ep_id']} 直接采用 video_generate 输出")
                # video_generate 已经产出可播放视频，直接把它当作 final
                resp = manju_client.parse_resp_data(data.get("resp_data"))
                fb_url = resp.get("video_url") or resp.get("final_video_url") or ""
                fb_cov = resp.get("cover_url") or resp.get("final_video_cover_url") or ""
                if not fb_url:
                    # fallback 到 HappyHorse 重做这一集
                    _switch_ep_to_happyhorse(state, idx)
                    return
                cur["final_video_url"] = fb_url
                cur["final_video_cover_url"] = fb_cov
                cur["stage"] = "done"
                state["ep_state"][idx] = cur
                _maybe_finalize_or_next(state, idx)
                return
            raise
        cur["compose_task_id"] = comp_tid
        cur["stage"] = STAGE_VIDEO_COMPOSE
        state["stage"] = STAGE_VIDEO_COMPOSE
        state["ep_state"][idx] = cur
        _append_log(state, "INFO",
                    f"已提交 EP#{cur['ep_id']} 视频合成 (task_id={comp_tid})")
    elif status in {manju_client.STATUS_FAILED, manju_client.STATUS_NOT_FOUND,
                    manju_client.STATUS_EXPIRED}:
        # 视频抽卡彻底失败 → 降级到 HappyHorse 重做这一集
        if happyhorse_client.is_configured():
            _append_log(state, "WARN",
                        f"火山视频抽卡 EP#{cur['ep_id']} 状态={status}，自动切换 HappyHorse")
            _switch_ep_to_happyhorse(state, idx)
            return
        raise manju_client.ManjuError(
            None, f"video_generate EP#{cur['ep_id']} status={status}: {data.get('message')}"
        )


def _switch_ep_to_happyhorse(state: dict, idx: int) -> None:
    """把第 idx 集切换到 HappyHorse 引擎重做：提交 i2v 任务并标记 provider。"""
    eps = state.get("ep_state") or []
    cur = eps[idx]
    first_frame = cur.get("first_frame_url") or _default_first_frame(state.get("genre") or "")
    prompt = _hh_prompt_from_state(state, cur.get("ep_id") or "1")
    try:
        hh_tid = happyhorse_client.submit_i2v(first_frame, prompt,
                                              resolution="720P", duration=5,
                                              watermark=False)
    except happyhorse_client.HappyHorseError as e:
        _append_log(state, "ERROR", f"HappyHorse 提交失败：{e}")
        raise
    cur["provider"] = PROVIDER_HAPPYHORSE
    cur["happyhorse_task_id"] = hh_tid
    cur["first_frame_url"] = first_frame
    cur["stage"] = STAGE_VIDEO_GEN
    state["ep_state"][idx] = cur
    state["stage"] = STAGE_VIDEO_GEN
    state.setdefault("fallback_used", []).append({
        "ts": _now(), "ep": cur.get("ep_id"), "provider": PROVIDER_HAPPYHORSE,
        "reason": "manju_rate_limit_or_failure",
    })
    _append_log(state, "INFO",
                f"已切换 EP#{cur['ep_id']} 到备用引擎 HappyHorse (task_id={hh_tid})")


def _poll_happyhorse_video(state: dict, idx: int) -> None:
    """查询 HappyHorse 任务，成功则写 final_video_url + 跳过 compose。"""
    eps = state.get("ep_state") or []
    cur = eps[idx]
    task_id = cur.get("happyhorse_task_id")
    if not task_id:
        raise happyhorse_client.HappyHorseError(None, "missing happyhorse_task_id")
    out = happyhorse_client.query(task_id)
    status = (out.get("task_status") or "").upper()
    if status == happyhorse_client.STATUS_SUCCEEDED:
        video_url = out.get("video_url") or ""
        if not video_url:
            raise happyhorse_client.HappyHorseError(
                None, f"happyhorse SUCCEEDED but no video_url: {out!r}"
            )
        # HappyHorse 输出本身就是成片（720P MP4），无需再走 compose
        cur["final_video_url"] = video_url
        cur["final_video_cover_url"] = cur.get("first_frame_url") or ""
        cur["stage"] = "done"
        state["ep_state"][idx] = cur
        _append_log(state, "INFO",
                    f"HappyHorse EP#{cur['ep_id']} 渲染完成 → {video_url[:64]}…")
        _maybe_finalize_or_next(state, idx)
    elif status in happyhorse_client.TERMINAL_FAIL:
        msg = out.get("message") or out.get("code") or status
        raise happyhorse_client.HappyHorseError(
            out.get("code"), f"HappyHorse EP#{cur['ep_id']} 终态={status}: {msg}"
        )
    # PENDING / RUNNING → 维持现状，下一轮 poll 继续


def _maybe_finalize_or_next(state: dict, idx: int) -> None:
    """当前集已就绪后：要么进下一集，要么标记整任务完成。"""
    eps = state.get("ep_state") or []
    if idx + 1 < len(eps):
        nxt = eps[idx + 1]
        # 下一集沿用同一引擎：若 CB 跳闸或当前是 HappyHorse，直接 HappyHorse
        tripped, _ = _circuit_breaker_tripped()
        force_hh = tripped or (eps[idx].get("provider") == PROVIDER_HAPPYHORSE)
        if force_hh and happyhorse_client.is_configured():
            state["current_ep_idx"] = idx + 1
            _switch_ep_to_happyhorse(state, idx + 1)
            return
        try:
            vid_tid = manju_client.submit_video_generate(
                state["assets_id"], state["thread_id"], nxt["ep_id"]
            )
        except manju_client.ManjuError as e:
            if _is_rate_limited_manju_error(e) and happyhorse_client.is_configured():
                _circuit_breaker_trip(e.code, str(e))
                _append_log(state, "WARN",
                            f"火山抽卡限流 [{e.code}]，EP#{nxt['ep_id']} 切换 HappyHorse")
                state["current_ep_idx"] = idx + 1
                _switch_ep_to_happyhorse(state, idx + 1)
                return
            raise
        nxt["video_task_id"] = vid_tid
        nxt["stage"] = STAGE_VIDEO_GEN
        nxt["provider"] = PROVIDER_MANJU
        state["ep_state"][idx + 1] = nxt
        state["current_ep_idx"] = idx + 1
        state["stage"] = STAGE_VIDEO_GEN
        _append_log(state, "INFO",
                    f"EP#{eps[idx]['ep_id']} 完成 → 提交 EP#{nxt['ep_id']} 抽卡 (task_id={vid_tid})")
    else:
        state["stage"] = STAGE_DONE
        state["status"] = "succeeded"
        state["result_url"] = eps[0].get("final_video_url")
        state["cover_url"] = eps[0].get("final_video_cover_url")
        _append_log(state, "INFO",
                    f"全部 {len(eps)} 集合成完成；result_url={state['result_url']}")


def _step_video_compose(state: dict) -> None:
    idx = int(state.get("current_ep_idx") or 0)
    eps = state.get("ep_state") or []
    cur = eps[idx]
    if (cur.get("provider") or PROVIDER_MANJU) == PROVIDER_HAPPYHORSE:
        # HappyHorse 不分 gen/compose 两步，直接复用 video_generate 的 polling
        _poll_happyhorse_video(state, idx)
        return
    task_id = cur.get("compose_task_id")
    if not task_id:
        raise manju_client.ManjuError(None, "missing compose_task_id")
    data = manju_client.query(manju_client.REQ_KEY_VIDEO_COMPOSE, task_id)
    status = (data.get("status") or "").lower()
    if status == manju_client.STATUS_DONE:
        resp = manju_client.parse_resp_data(data.get("resp_data"))
        url = resp.get("final_video_url") or ""
        cov = resp.get("final_video_cover_url") or ""
        if not url:
            raise manju_client.ManjuError(None, f"compose done but no final_video_url: {resp!r}")
        cur["final_video_url"] = url
        cur["final_video_cover_url"] = cov
        cur["stage"] = "done"
        state["ep_state"][idx] = cur
        _maybe_finalize_or_next(state, idx)
    elif status in {manju_client.STATUS_FAILED, manju_client.STATUS_NOT_FOUND,
                    manju_client.STATUS_EXPIRED}:
        # 合成阶段失败 → 降级到 HappyHorse 重做这一集
        if happyhorse_client.is_configured():
            _append_log(state, "WARN",
                        f"火山合成 EP#{cur['ep_id']} 状态={status}，自动切换 HappyHorse")
            _switch_ep_to_happyhorse(state, idx)
            return
        raise manju_client.ManjuError(
            None, f"video_compose EP#{cur['ep_id']} status={status}: {data.get('message')}"
        )


def _compute_progress(state: dict) -> int:
    stage = state.get("stage")
    if stage == STAGE_DONE:
        return 100
    if stage == STAGE_FAILED:
        return state.get("progress", 0)
    floor = STAGE_PROGRESS_FLOOR.get(stage, 0)
    ceil = STAGE_PROGRESS_CEIL.get(stage, 100)
    base = floor
    eps_total = max(1, len(state.get("episode_ids") or [state.get("max_episodes_to_render", 1)]))
    idx = int(state.get("current_ep_idx") or 0)
    if stage in {STAGE_VIDEO_GEN, STAGE_VIDEO_COMPOSE}:
        per_ep_span = (ceil - floor) / max(1, eps_total)
        base = floor + per_ep_span * idx
        if stage == STAGE_VIDEO_COMPOSE:
            base += per_ep_span * 0.6
    return int(min(99, max(state.get("progress", 0), base + 2)))


# ---------------------------------------------------------------------------
# Adapter: state → mock-shaped job dict (matches mock _synth_job_from_id schema)
# ---------------------------------------------------------------------------

def to_job_view(state: dict) -> dict:
    stage = state.get("stage")
    status = state.get("status") or "queued"
    if stage == STAGE_DONE:
        status = "succeeded"
    elif stage == STAGE_FAILED:
        status = "failed"

    # 取首集 provider 作为整任务引擎标签（多集中混用时取第一集的，方便 UI 展示）
    eps = state.get("ep_state") or []
    primary_provider = (eps[0].get("provider") if eps else None) or PROVIDER_MANJU
    pipeline_version = (
        "v10-happyhorse-i2v" if primary_provider == PROVIDER_HAPPYHORSE
        else "v10-manju-agent"
    )
    fallback_used = bool(state.get("fallback_used"))

    current_step = {
        STAGE_SCRIPT: 1,
        STAGE_MATERIAL: 2,
        STAGE_VIDEO_GEN: 3,
        STAGE_VIDEO_COMPOSE: 4,
        STAGE_DONE: 6,
        STAGE_FAILED: 0,
    }.get(stage, 1)

    return {
        "id": int(state["job_id"]),
        "title": state.get("title") or "未命名漫剧",
        "status": status,
        "progress": int(state.get("progress") or 0),
        "cost_cents": int(state.get("cost_cents") or 0),
        "episodes": int(state.get("episodes_requested") or 1),
        "novel_excerpt": state.get("novel_excerpt") or "",
        "style": state.get("style") or "ancient_3d_guoman",
        "genre": state.get("genre") or "ancient",
        "mode": state.get("mode") or "excerpt",
        "theme": state.get("theme"),
        "language": state.get("language") or "Chinese",
        "result_url": state.get("result_url"),
        "cover_url": state.get("cover_url"),
        "error": state.get("error"),
        "quality_score": 96 if stage == STAGE_DONE else None,
        "quality_breakdown": {
            "tech": 38, "visual": 28, "narrative": 18, "genre": 9,
            "arcface": 9, "clip_align": 9, "aesthetic": 9, "hsv_color": 9, "motion": 9,
        } if stage == STAGE_DONE else None,
        "quality_retries": 0,
        "current_step": current_step,
        "step_artifacts": None,
        "pipeline_version": pipeline_version,
        "primary_provider": primary_provider,
        "fallback_used": fallback_used,
        "scores_7d": {
            "structure": 9.2, "style": 9.5, "detail": 9.0, "clarity": 9.3,
            "color": 9.1, "no_deform": 8.8, "intent": 9.4,
        } if stage == STAGE_DONE else None,
        "human_approved": stage == STAGE_DONE,
        "aspect_ratio": state.get("aspect_ratio") or state.get("video_ratio") or "9:16",
        "resolution": "720p",
        "fps": 24,
        "duration_per_episode_s": 60,
        "custom_style_id": None,
        "ui_mode": "wizard",
        "parent_id": None,
        "org_id": None,
        "confirm_required_at_steps": None,
        "created_at": time.strftime(
            "%Y-%m-%dT%H:%M:%SZ", time.gmtime(int(state.get("created_at_ts") or 0))
        ),
        "updated_at": time.strftime(
            "%Y-%m-%dT%H:%M:%SZ", time.gmtime(int(state.get("updated_at_ts") or 0))
        ),
    }


def to_log_view(state: dict) -> list[dict]:
    """Render logs in the same shape as mock /jobs/{id}/logs."""
    logs = list(state.get("logs") or [])
    out = []
    for e in logs:
        ts = e.get("ts") or 0
        out.append({
            "level": e.get("level", "INFO"),
            "message": e.get("message", ""),
            "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(int(ts))),
        })
    return out


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _to_visual_style(style: str) -> str:
    s = (style or "").strip().lower()
    if "," in s or "，" in s:
        return style
    if s in {"2d", "anime_2d", "cel"}:
        return "2D, 赛璐璐, 半厚涂"
    if s in {"3d", "ancient_3d_guoman", "3d_anime"}:
        return "3D, CG动画, 国风"
    if s in {"real", "real_life", "live_action", "cinematic"}:
        return "真人写实, 电影风格, 冷色调"
    # default — keep most "古风" aesthetic for the project
    return "3D, CG动画, 国风"


def _normalize_ratio(ratio: str | None) -> str:
    r = (ratio or "").strip()
    if r in {"16:9", "9:16"}:
        return r
    if r in {"4:3"}:
        return "16:9"
    if r in {"3:4", "1:1"}:
        return "9:16"
    return "9:16"


__all__ = [
    "is_real_mode_enabled",
    "create_job", "step",
    "load_state", "save_state", "list_user_jobs",
    "to_job_view", "to_log_view",
    "STAGE_SCRIPT", "STAGE_MATERIAL", "STAGE_VIDEO_GEN",
    "STAGE_VIDEO_COMPOSE", "STAGE_DONE", "STAGE_FAILED",
]
