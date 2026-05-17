"""R35/R36 — ep02/ep03 v3 prompt Skylark reroll.

读 prompts/episodes/r33_34_v3.json + 真接口生成 + Shell 5 master + 写到
data/pilot_short_skylark/manifest_niexiaoqian_v3.json (单独 manifest 不污染 R30 baseline).

用法:
    python tools/r35_36_v3_reroll.py --ep ep02_nie_appears
    python tools/r35_36_v3_reroll.py --ep ep03_yan_chixia
"""
from __future__ import annotations
import argparse
import json
import os
import pathlib
import shutil
import sys
import datetime as _dt

os.environ.setdefault("PYTHONIOENCODING", "utf-8")
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
except (AttributeError, OSError):
    pass


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ep", required=True,
                       help="ep_id: ep02_nie_appears / ep03_yan_chixia")
    args = parser.parse_args()

    repo = pathlib.Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(repo))

    from pilot.run_three_short_episodes import load_env_file, _make_aigc_meta  # type: ignore
    load_env_file(repo / ".env")

    v3_path = repo / "prompts" / "episodes" / "r33_34_v3.json"
    if not v3_path.exists():
        print(f"[fatal] v3 prompt file missing: {v3_path}")
        return 1
    v3 = json.loads(v3_path.read_text(encoding="utf-8"))
    target = next((r for r in v3 if r.get("ep_id") == args.ep), None)
    if not target:
        print(f"[fatal] no v3 prompt for {args.ep}")
        return 1
    prompt = target["prompt"]
    print(f"[r35/36 v3] target ep: {args.ep}")
    print(f"  prompt len: {len(prompt)}")
    print(f"  rationale: {target.get('rationale', '')[:150]}")
    print(f"  preview: {prompt[:120]!r}...")

    from src.shell3_skylark_engine import (  # type: ignore
        EpisodeRequest, ReferencePack, SkylarkAgentV2WithRefClient,
    )
    from src.shell5_post_production import master, MasterError  # type: ignore
    from src.shell5_post_production.cinematic_master import MasterConfig  # type: ignore

    out_root = repo / "data" / "pilot_short_skylark"
    raw_dir = out_root / "raw_v3"
    out_root.mkdir(parents=True, exist_ok=True)
    raw_dir.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("STORAGE_ROOT", str(out_root))

    run_id = _dt.datetime.now(_dt.timezone.utc).strftime("%Y%m%dT%H%M%S")
    aigc_meta = _make_aigc_meta(args.ep + "_v3", run_id)

    if len(prompt) > 2000:
        print(f"  [trunc] {len(prompt)} → 2000")
        prompt = prompt[:2000]

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

    print(f"\n[skylark] submitting {args.ep} v3 (~15s preset)...")
    t0 = _dt.datetime.now()
    try:
        result = client.render_episode(req, ep_id=args.ep + "_v3")
    except Exception as e:
        print(f"[FAIL] Skylark: {type(e).__name__}: {e}")
        return 1
    wallclock = (_dt.datetime.now() - t0).total_seconds()
    print(f"[skylark] done in {wallclock:.0f}s | task={result.task_id} | dur={result.output_duration_seconds:.2f}s | aigc={result.aigc_meta_tagged}")

    raw_path = raw_dir / f"{args.ep}_v3.raw.mp4"
    final_path = out_root / f"{args.ep}_v3.mp4"
    shutil.copy2(result.archived_video_path, raw_path)

    master_cap = 17.0
    print(f"\n[master] Shell 5 cinematic master ({master_cap}s cap)...")
    cfg = MasterConfig(duration_cap_seconds=master_cap)
    try:
        metrics = master(raw_path, final_path, ep_id=args.ep + "_v3", task_id=result.task_id, config=cfg)
    except Exception as e:
        print(f"[FAIL] master: {type(e).__name__}: {e}")
        return 1
    print(f"[master] {metrics['width']}x{metrics['height']}@{metrics['fps']}fps | "
          f"{metrics['bitrate_mbps']}Mbps | {metrics['size_bytes']/1e6:.1f}MB | dur={metrics['duration']}s")

    # Write separate v3 manifest
    v3_mp = out_root / "manifest_niexiaoqian_v3.json"
    if v3_mp.exists():
        v3_manifest = json.loads(v3_mp.read_text(encoding="utf-8"))
    else:
        v3_manifest = {
            "run_id": run_id,
            "engine": "Skylark Agent 2.0 = Seedance 2.0 fast 720p with reference",
            "skylark_req_key": "pippit_iv2v_v20_cvtob_with_vinput",
            "skylark_ratio": "9:16",
            "skylark_language": "Chinese",
            "skylark_enable_watermark": False,
            "master_profile": "world_class_cinematic_v1",
            "target_resolution": "1080x1920",
            "target_fps": 24,
            "novel_source": "聊斋·聂小倩 蒲松龄 ~1740 公版 (prompt v3)",
            "episodes": [],
        }

    entry = {
        "id": args.ep,
        "ok": True,
        "task_id": result.task_id,
        "final_path": str(final_path.resolve()),
        "raw_path": str(raw_path.resolve()),
        "duration_preset": "～15s",
        "master_cap_seconds": master_cap,
        "aigc_meta_tagged": bool(result.aigc_meta_tagged),
        "prompt_version": "v3",
        "aigc_meta": {
            "content_producer": aigc_meta.content_producer,
            "producer_id": aigc_meta.producer_id,
            "content_propagator": aigc_meta.content_propagator,
            "propagate_id": aigc_meta.propagate_id,
        },
        "reported_output_seconds": result.output_duration_seconds,
        "master_metrics": metrics,
        "round": "R35-R36",
        "generated_at": _dt.datetime.now(_dt.timezone.utc).isoformat(),
    }
    v3_manifest["episodes"] = [e for e in v3_manifest["episodes"] if e["id"] != args.ep]
    v3_manifest["episodes"].append(entry)
    v3_mp.write_text(json.dumps(v3_manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n[DONE] {args.ep} v3 written to {v3_mp.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
