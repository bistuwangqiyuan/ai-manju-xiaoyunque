"""3 集 ~15s 真实 Skylark Agent 2.0 跑通 + 世界电影级精修.

流程：
    1) 读 repo-root .env（VOLC_AK/VOLC_SK/VOLC_REGION etc.）
    2) 实例化 AigcMeta（GB/T 45438-2025 隐式标识）
    3) 用官方最小档 `duration="~15s"` 提交三集（ep01_micro/ep02_micro/ep03_micro），
       9:16 竖屏古风 3D 国漫，prompt 已硬注三大原创锁定符号（朱砂痣/黑藤/苍白手）
    4) Skylark raw → 写到 data/pilot_short_skylark/raw/<ep_id>.raw.mp4
    5) 调用 Shell 5 cinematic master:
       - trim 15s + hqdn3d 降噪 + 三级调色（冷青/月白/朱砂）
       - zscale spline36 1080×1920 上采 + unsharp 锐化
       - fps=24 标准化 + drawtext "AI 生成" 合规水印
       - libx264 crf=15 preset=veryslow tune=film yuv420p + faststart
       - mp4 metadata: title/comment/copyright/creation_time/composer
    6) 写完整 manifest.json: 真 task_id + aigc_meta_tagged + master metrics

用法：
    python pilot/run_three_short_episodes.py

依赖：
    - .env 含 VOLC_AK + VOLC_SK + VOLC_REGION
    - ffmpeg ≥ 8.x 含 zscale/libfreetype/libass
    - Windows 中文 Bold 字体（msyhbd.ttc / simhei.ttf）
"""
from __future__ import annotations

import datetime as _dt
import json
import logging
import os
import pathlib
import shutil
import sys
import uuid

_REPO = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO))


def load_env_file(path: pathlib.Path) -> None:
    """从 KEY=VALUE .env 注入 os.environ；尾部 # 注释剥掉。"""

    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, _, val = line.partition("=")
        key = key.strip()
        val = val.strip()
        if "#" in val:
            val = val.split("#", 1)[0].strip()
        if key and val and key not in os.environ:
            os.environ[key] = val


# 三集 micro 钩子 prompt — 古风 3D 国漫，三大原创锁定符号硬注入
EPISODE_PROMPTS: list[tuple[str, str]] = [
    (
        "ep01_micro",
        """古风3D国漫竖屏9:16，Unreal5路径追踪+cel-shading描边，冷青+月白+朱砂配色。
兰若寺荒废山门月夜，蝙蝠掠过破匾。书生宁采臣浅灰青长袍背書箧推门入院。
聂小倩白衣襦裙浅粉缎带，眉间一点朱砂痣清晰可见，杏眼浅蓝灰微光，白玉镯半透。
镜头：广角→推近→特写朱砂痣；铜镜前回眸，镜面只做空灵倒影不写血腥。
音效留白：夜风、竹影；禁忌：画面不出现任何字幕文字。""",
    ),
    (
        "ep02_micro",
        """古风3D国漫竖屏9:16，白蛇缘起质感60%+狐妖月红仙气30%+雾山撞色10%（战斗段禁用）。
兰若东侧回廊深夜烛火摇曳，宁采臣端坐案前。三更叩门，白衣聂小倩立于门外，
眉间朱砂痣与左肩袖口一缕淡淡鬼气（虚化烟雾，不写血腥）。黄金落在阶下化作柔和光尘散去（不写白骨特写）。
镜头正反打+浅景深；禁忌：无性暗示构图，无字幕文字。""",
    ),
    (
        "ep03_micro",
        """古风3D国漫竖屏9:16，雨后天青光与烛火暖橘对比。
客栈榻上友人昏迷写意镜头（不要血腥创口特写）。燕赤霞深墨色道袍暗红披风，
腰间褐色革囊与短剑鞘可见，右眉骨浅疤。夜空一道青蓝剑光掠过，
白练状阴影远去方向引向远处院落剪影（不写恐怖特写）。
镜头：中景→剪影→眼角特写；禁忌：无字幕文字。""",
    ),
]


def _make_aigc_meta(ep_id: str, run_id: str):
    """造一个本集唯一的 AigcMeta（满足 ≤256 chars 长度限制）。

    `producer_id` 含 ep_id + UTC 时间戳 + uuid 短前缀，保证全局唯一。
    """

    from src.shell3_skylark_engine import AigcMeta
    return AigcMeta(
        content_producer="AI_MANJU_PILOT_NIE_XIAOQIAN_V5",
        producer_id=f"{ep_id}_{run_id}_{uuid.uuid4().hex[:12]}",
        content_propagator="AI_MANJU_INTERNAL_TEST",
        propagate_id=f"prop_{ep_id}_{run_id}",
    )


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    log = logging.getLogger("three_short_skylark")
    load_env_file(_REPO / ".env")

    out_root = _REPO / "data" / "pilot_short_skylark"
    raw_dir = out_root / "raw"
    out_root.mkdir(parents=True, exist_ok=True)
    raw_dir.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("STORAGE_ROOT", str(out_root))

    from src.shell3_skylark_engine import (
        EpisodeRequest,
        ReferencePack,
        SkylarkAgentV2WithRefClient,
    )
    from src.shell5_post_production import master, MasterError

    run_id = _dt.datetime.now(_dt.timezone.utc).strftime("%Y%m%dT%H%M%S")

    manifest: dict = {
        "run_id": run_id,
        "started_at": _dt.datetime.now(_dt.timezone.utc).isoformat(),
        "skylark_req_key": "pippit_iv2v_v20_cvtob_with_vinput",
        "skylark_duration_preset": "～15s",
        "skylark_ratio": "9:16",
        "skylark_language": "Chinese",
        "enable_watermark": False,
        "master_profile": "world_class_cinematic_v1",
        "target_resolution": "1080x1920",
        "target_fps": 24,
        "episodes": [],
    }

    for ep_id, prompt in EPISODE_PROMPTS:
        log.info("=" * 70)
        log.info("Episode %s: prepare", ep_id)

        if len(prompt) > 2000:
            log.warning("%s prompt %d > 2000, truncating", ep_id, len(prompt))
            prompt = prompt[:2000]

        aigc_meta = _make_aigc_meta(ep_id, run_id)
        client = SkylarkAgentV2WithRefClient(
            poll_interval_seconds=12.0,
            timeout_seconds=7200.0,
            aigc_meta=aigc_meta,
        )

        req = EpisodeRequest(
            prompt=prompt,
            references=ReferencePack(),
            ratio="9:16",
            duration="～15s",
            language="Chinese",
            enable_watermark=False,
        )

        raw_path = raw_dir / f"{ep_id}.raw.mp4"
        final_path = out_root / f"{ep_id}.mp4"

        entry: dict = {
            "id": ep_id,
            "ok": False,
            "aigc_meta": {
                "content_producer": aigc_meta.content_producer,
                "producer_id": aigc_meta.producer_id,
                "content_propagator": aigc_meta.content_propagator,
                "propagate_id": aigc_meta.propagate_id,
            },
        }

        # ---------- Step A: Skylark submit + poll + archive raw ----------
        log.info("[%s] submitting Skylark 2.0 (~15s preset, 9:16, AigcMeta wired)...", ep_id)
        try:
            result = client.render_episode(req, ep_id=ep_id)
        except Exception as exc:  # noqa: BLE001
            log.exception("[%s] Skylark render_episode FAILED: %s", ep_id, exc)
            entry["error"] = f"skylark_failed: {exc}"
            manifest["episodes"].append(entry)
            _write_manifest(out_root, manifest)
            continue

        log.info(
            "[%s] Skylark done task_id=%s reported_duration=%.2fs aigc_meta_tagged=%s",
            ep_id, result.task_id, result.output_duration_seconds, result.aigc_meta_tagged,
        )
        shutil.copy2(result.archived_video_path, raw_path)
        entry["task_id"] = result.task_id
        entry["raw_path"] = str(raw_path.resolve())
        entry["reported_output_seconds"] = result.output_duration_seconds
        entry["aigc_meta_tagged"] = bool(result.aigc_meta_tagged)
        entry["video_url_archived_from"] = result.video_url[:120] + "..." if result.video_url else ""

        # ---------- Step B: cinematic master (1080p + 24fps + AIGC 水印 + faststart) ----------
        log.info("[%s] cinematic master starting…", ep_id)
        try:
            metrics = master(raw_path, final_path, ep_id=ep_id, task_id=result.task_id)
        except MasterError as exc:
            log.exception("[%s] master FAILED: %s", ep_id, exc)
            entry["error"] = f"master_failed: {exc}"
            manifest["episodes"].append(entry)
            _write_manifest(out_root, manifest)
            continue

        entry["ok"] = True
        entry["final_path"] = str(final_path.resolve())
        entry["master_metrics"] = metrics
        manifest["episodes"].append(entry)
        _write_manifest(out_root, manifest)

    manifest["finished_at"] = _dt.datetime.now(_dt.timezone.utc).isoformat()
    _write_manifest(out_root, manifest)

    ok = sum(1 for e in manifest["episodes"] if e.get("ok"))
    log.info("=" * 70)
    log.info("DONE: %d/%d episodes succeeded (manifest: %s/manifest.json)", ok, len(EPISODE_PROMPTS), out_root)
    return 0 if ok == len(EPISODE_PROMPTS) else 1


def _write_manifest(out_root: pathlib.Path, manifest: dict) -> None:
    (out_root / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


if __name__ == "__main__":
    raise SystemExit(main())
