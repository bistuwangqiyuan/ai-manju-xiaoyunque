"""R15 西游记·石猴出世 prompt-only — 启动 R15-R24 10 轮新迭代.

测试用例切换:聊斋·聂小倩 → 西游记·石猴出世(吴承恩 1592 公版IP)。
古风内容,Skylark 历史验证审核宽松。

R15 baseline 期望:88-92(R13 聊斋 baseline 90.2 同 engine 同 prompt-only 路径)。
"""
from __future__ import annotations

import datetime as _dt
import json
import os
import pathlib
import shutil
import sys
import time
import uuid

_REPO = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO))


def force_load_env(path: pathlib.Path) -> None:
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line: continue
        k, _, v = line.partition("=")
        v = v.split("#", 1)[0].strip()
        if k and v:
            os.environ[k.strip()] = v


def main() -> int:
    force_load_env(_REPO / ".env")
    print("=== R15 西游记·石猴出世 prompt-only baseline ===")
    from prompts.episodes import xiyou_stone_monkey as xy
    from src.shell3_skylark_engine import (
        AigcMeta, EpisodeRequest, ReferencePack, SkylarkAgentV2WithRefClient,
    )
    from src.shell5_post_production import master, MasterError
    from src.shell5_post_production.cinematic_master import MasterConfig

    out_root = _REPO / "data" / "pilot_short_skylark"
    raw_dir = out_root / "raw_r15"
    raw_dir.mkdir(parents=True, exist_ok=True)
    run_id = _dt.datetime.now(_dt.timezone.utc).strftime("%Y%m%dT%H%M%S")

    manifest = {
        "run_id": f"R15_{run_id}",
        "round_id": "R15",
        "test_case": "西游记·石猴出世 (吴承恩 1592 公版IP)",
        "started_at": _dt.datetime.now(_dt.timezone.utc).isoformat(),
        "engine": "Skylark Agent 2.0 prompt-only 古风审核宽松",
        "episodes": [],
    }

    for idx, ep in enumerate(xy.EPISODES):
        ep_id = ep["ep_id"]
        print(f"\n=== {ep_id} ===")
        if idx > 0:
            print(f"  proactive QPS sleep 30s...")
            time.sleep(30)
        meta = AigcMeta(
            content_producer="AI_MANJU_PILOT_R15_XIYOU",
            producer_id=f"{ep_id}_R15_{run_id}_{uuid.uuid4().hex[:10]}",
            content_propagator="AI_MANJU_INTERNAL_TEST",
            propagate_id=f"prop_{ep_id}",
        )
        client = SkylarkAgentV2WithRefClient(poll_interval_seconds=12.0,
                                              timeout_seconds=7200.0, aigc_meta=meta)
        req = EpisodeRequest(
            prompt=ep["prompt"][:2000],
            references=ReferencePack(),
            ratio="9:16", duration="～15s", language="Chinese",
            enable_watermark=False,
        )
        entry = {"id": ep_id, "ok": False}
        try:
            result = client.render_episode(req, ep_id=ep_id)
        except Exception as e:
            print(f"  Skylark FAIL: {str(e)[:200]}")
            entry["error"] = f"skylark: {e}"
            manifest["episodes"].append(entry)
            continue
        print(f"  Skylark OK: task_id={result.task_id} dur={result.output_duration_seconds:.2f}s aigc={result.aigc_meta_tagged}")
        raw_path = raw_dir / f"{ep_id}.raw.mp4"
        shutil.copy2(result.archived_video_path, raw_path)
        final_path = out_root / f"{ep_id}_r15.mp4"
        try:
            metrics = master(raw_path, final_path, ep_id=ep_id, task_id=result.task_id,
                             config=MasterConfig(duration_cap_seconds=17.0))
        except MasterError as e:
            entry["error"] = f"master: {e}"
            manifest["episodes"].append(entry)
            continue
        entry.update({
            "ok": True, "task_id": result.task_id,
            "duration_preset_used": "～15s",
            "reported_output_seconds": result.output_duration_seconds,
            "aigc_meta_tagged": bool(result.aigc_meta_tagged),
            "raw_path": str(raw_path.resolve()), "final_path": str(final_path.resolve()),
            "master_metrics": metrics,
        })
        manifest["episodes"].append(entry)
        print(f"  master OK: {metrics['width']}x{metrics['height']} @ {metrics['fps']} fps {metrics['bitrate_mbps']} Mbps")

    manifest["finished_at"] = _dt.datetime.now(_dt.timezone.utc).isoformat()
    mp = out_root / "manifest_r15.json"
    mp.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    ok = sum(1 for e in manifest["episodes"] if e.get("ok"))
    print(f"\nDONE: {ok}/3 successful. Manifest: {mp}")
    return 0 if ok == 3 else 1


if __name__ == "__main__":
    raise SystemExit(main())
