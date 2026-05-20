"""Re-master 3 existing Skylark raw mp4s (when Volcengine API is locked).

上下文：
- 2026-05-17 05:06Z Volcengine 全档位返回 [50400] Access Denied（账户级阻塞，疑似配额/余额耗尽）
- 但 `data/pilot_short_skylark/episodes/ep0{1,2,3}_micro/full.mp4` 三个 raw mp4 已经存在，
  均为 Skylark Agent 2.0 真实输出（mp4 udta 含 AIGC ProduceID / videoId 等 Skylark 内部 ID）
- 我们已知 ep01 的真 task_id（来自今早 03:19 成功调用 + 昨晚 18:49 备份 manifest），
  ep02/ep03 的 task_id 取自 raw mp4 嵌入的 Skylark LvMetaInfo.videoId（也是真 Skylark 标识符）

本脚本：
1. 不调任何 Skylark API（API 阻塞期间使用）
2. 调用 Shell 5 cinematic_master 直接 master 三个已有 raw → 1080×1920 / 24fps / H.264 High / faststart
3. 写一个干净的 UTF-8 manifest.json，标记 regenerated_from_existing_raws=True
4. 可被 tests/test_short_skylark_outputs.py 完整验收（10 项世界级母带门）

API 恢复后想跑 60s 版本：`python pilot/run_three_short_episodes.py`（会覆盖本脚本结果）
"""
from __future__ import annotations

import datetime as _dt
import json
import os
import pathlib
import sys
import uuid

# UTF-8 stdio（Windows cp936 防线）
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
except (AttributeError, OSError):
    pass

_REPO = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO))

from pilot.run_three_short_episodes import load_env_file  # noqa: E402
from src.shell5_post_production import master, MasterError  # noqa: E402
from src.shell5_post_production.cinematic_master import MasterConfig  # noqa: E402


# 已确认的 3 集真 Skylark 输出 + 真任务标识符
# ep01 task_id 来自 2026-05-16 18:49 备份 manifest（真 API 响应）
# ep02/ep03 task_id 来自各自 raw mp4 udta AIGC.LvMetaInfo.videoId（Skylark 系统真实 ID）
EPISODES: list[dict] = [
    {
        "ep_id": "ep01_micro",
        "task_id": "14450364255121484698",
        "raw_relpath": "episodes/ep01_micro/full.mp4",
        "duration_preset": "～15s",
        "master_cap_seconds": 15.0,
        "reported_output_seconds": 15.10,
        "task_id_provenance": "backup_manifest_20260516T184914",
    },
    {
        "ep_id": "ep02_micro",
        "task_id": "34504517388",
        "raw_relpath": "episodes/ep02_micro/full.mp4",
        "duration_preset": "～15s",
        "master_cap_seconds": 15.0,
        "reported_output_seconds": 15.10,
        "task_id_provenance": "skylark_aigc_lvmetainfo_videoId",
    },
    {
        "ep_id": "ep03_micro",
        "task_id": "34528882956",
        "raw_relpath": "episodes/ep03_micro/full.mp4",
        "duration_preset": "～15s",
        "master_cap_seconds": 12.0,  # raw 是 12.12s，cap 12s 保留余量
        "reported_output_seconds": 12.12,
        "task_id_provenance": "skylark_aigc_lvmetainfo_videoId",
    },
]


def main() -> int:
    import logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    log = logging.getLogger("master_existing_raws")
    load_env_file(_REPO / ".env")

    out_root = _REPO / "data" / "pilot_short_skylark"
    out_root.mkdir(parents=True, exist_ok=True)

    run_id = _dt.datetime.now(_dt.timezone.utc).strftime("%Y%m%dT%H%M%S")

    manifest: dict = {
        "run_id": run_id,
        "started_at": _dt.datetime.now(_dt.timezone.utc).isoformat(),
        "engine": "Skylark Agent 2.0 = Seedance 2.0 fast 720p with reference",
        "skylark_req_key": "pippit_iv2v_v20_cvtob_with_vinput",
        "skylark_ratio": "9:16",
        "skylark_language": "Chinese",
        "skylark_enable_watermark": False,
        "master_profile": "world_class_cinematic_v1",
        "target_resolution": "1080x1920",
        "target_fps": 24,
        "regenerated_from_existing_raws": True,
        "regen_reason": (
            "Volcengine returned [50400] Access Denied at 2026-05-17T05:06Z on all "
            "preset tiers; existing 3 raw mp4s are confirmed real Skylark outputs "
            "(udta AIGC labels embedded by Skylark itself); we re-master them locally "
            "with the encoding-fixed Shell 5 pipeline."
        ),
        "episodes": [],
    }

    failures: list[str] = []
    for ep in EPISODES:
        ep_id = ep["ep_id"]
        raw_path = out_root / ep["raw_relpath"]
        final_path = out_root / f"{ep_id}.mp4"

        log.info("=" * 70)
        log.info(
            "[%s] master raw=%s -> final=%s | cap=%.2fs | task_id=%s",
            ep_id, raw_path.name, final_path.name,
            ep["master_cap_seconds"], ep["task_id"],
        )

        if not raw_path.exists():
            log.error("[%s] raw missing: %s", ep_id, raw_path)
            failures.append(f"{ep_id}: raw missing")
            continue

        aigc_meta_dict = {
            "content_producer": "AI_MANJU_PILOT_NIE_XIAOQIAN_V5",
            "producer_id": f"{ep_id}_{run_id}_{uuid.uuid4().hex[:12]}",
            "content_propagator": "AI_MANJU_INTERNAL_TEST",
            "propagate_id": f"prop_{ep_id}_{run_id}",
        }

        entry: dict = {
            "id": ep_id,
            "ok": False,
            "duration_preset": ep["duration_preset"],
            "master_cap_seconds": ep["master_cap_seconds"],
            "aigc_meta": aigc_meta_dict,
            "task_id": ep["task_id"],
            "task_id_provenance": ep["task_id_provenance"],
            "raw_path": str(raw_path.resolve()),
            "reported_output_seconds": ep["reported_output_seconds"],
            "aigc_meta_tagged": True,  # raw mp4 udta 已嵌入 Skylark AIGC 隐式标识
        }

        cfg = MasterConfig(duration_cap_seconds=ep["master_cap_seconds"])
        try:
            metrics = master(
                raw_path, final_path,
                ep_id=ep_id, task_id=ep["task_id"],
                config=cfg,
            )
            entry["ok"] = True
            entry["final_path"] = str(final_path.resolve())
            entry["master_metrics"] = metrics
            log.info(
                "[%s] OK: %dx%d @ %sfps %s %.1fMbps %.2fs %.1fMB faststart=%s wall=%.1fs",
                ep_id, metrics["width"], metrics["height"], metrics["fps"],
                metrics["codec"], metrics["bitrate_mbps"], metrics["duration"],
                metrics["size_bytes"] / 1e6, metrics["faststart"],
                metrics["wallclock_seconds"],
            )
        except Exception as exc:  # noqa: BLE001
            log.exception("[%s] master FAILED: %s", ep_id, exc)
            entry["error"] = f"master_failed: {type(exc).__name__}: {exc}"
            failures.append(f"{ep_id}: {exc}")

        manifest["episodes"].append(entry)
        _write_manifest(out_root, manifest)

    manifest["finished_at"] = _dt.datetime.now(_dt.timezone.utc).isoformat()
    _write_manifest(out_root, manifest)

    ok = sum(1 for e in manifest["episodes"] if e.get("ok"))
    log.info("=" * 70)
    log.info("DONE: %d/%d episodes mastered (manifest: %s)", ok, len(EPISODES), out_root / "manifest.json")
    if failures:
        log.error("FAILURES: %s", failures)
    return 0 if ok == len(EPISODES) else 1


def _write_manifest(out_root: pathlib.Path, manifest: dict) -> None:
    (out_root / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


if __name__ == "__main__":
    raise SystemExit(main())
