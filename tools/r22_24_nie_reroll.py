"""R22/R23/R24 — 聊斋·聂小倩单集 Skylark reroll.

读 prompts/episodes/r21_niexiaoqian.json + 真接口生成 + Shell 5 master + 写新 manifest
data/pilot_short_skylark/manifest_niexiaoqian.json（不污染无限恐怖批次）。

用法:
    python tools/r22_24_nie_reroll.py --ep ep01_nie_lanruosi
    python tools/r22_24_nie_reroll.py --ep ep02_nie_appears
    python tools/r22_24_nie_reroll.py --ep ep03_yan_chixia
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
                       help="ep_id: ep01_nie_lanruosi / ep02_nie_appears / ep03_yan_chixia")
    args = parser.parse_args()

    repo = pathlib.Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(repo))

    from pilot.run_three_short_episodes import load_env_file, _make_aigc_meta  # type: ignore
    load_env_file(repo / ".env")

    # Load R21 prompts
    r21_path = repo / "prompts" / "episodes" / "r21_niexiaoqian.json"
    if not r21_path.exists():
        print(f"[fatal] R21 prompt file missing: {r21_path}")
        return 1
    r21 = json.loads(r21_path.read_text(encoding="utf-8"))
    target = next((r for r in r21 if r.get("ep_id") == args.ep and r.get("ok")), None)
    if not target:
        print(f"[fatal] no R21 prompt for {args.ep}")
        return 1
    prompt = target["prompt"]
    print(f"[r22/23/24] target ep: {args.ep}")
    print(f"  prompt len: {len(prompt)}")
    print(f"  preview: {prompt[:120]!r}...")

    from src.shell3_skylark_engine import (  # type: ignore
        EpisodeRequest, ReferencePack, SkylarkAgentV2WithRefClient,
    )
    from src.shell5_post_production import master, MasterError  # type: ignore
    from src.shell5_post_production.cinematic_master import MasterConfig  # type: ignore

    out_root = repo / "data" / "pilot_short_skylark"
    raw_dir = out_root / "raw"
    out_root.mkdir(parents=True, exist_ok=True)
    raw_dir.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("STORAGE_ROOT", str(out_root))

    run_id = _dt.datetime.now(_dt.timezone.utc).strftime("%Y%m%dT%H%M%S")
    aigc_meta = _make_aigc_meta(args.ep, run_id)

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

    print(f"\n[skylark] submitting {args.ep} (R21 prompt, ~15s preset)...")
    t0 = _dt.datetime.now()
    try:
        result = client.render_episode(req, ep_id=args.ep)
    except Exception as e:
        print(f"[FAIL] Skylark: {type(e).__name__}: {e}")
        return 1
    wallclock = (_dt.datetime.now() - t0).total_seconds()
    print(f"[skylark] done in {wallclock:.0f}s | task={result.task_id} | dur={result.output_duration_seconds:.2f}s | aigc={result.aigc_meta_tagged}")

    raw_path = raw_dir / f"{args.ep}.raw.mp4"
    final_path = out_root / f"{args.ep}.mp4"
    shutil.copy2(result.archived_video_path, raw_path)

    master_cap = 17.0
    print(f"\n[master] Shell 5 cinematic master ({master_cap}s cap)...")
    cfg = MasterConfig(duration_cap_seconds=master_cap)
    try:
        metrics = master(raw_path, final_path, ep_id=args.ep, task_id=result.task_id, config=cfg)
    except Exception as e:
        print(f"[FAIL] master: {type(e).__name__}: {e}")
        return 1
    print(f"[master] {metrics['width']}x{metrics['height']}@{metrics['fps']}fps | "
          f"{metrics['bitrate_mbps']}Mbps | {metrics['size_bytes']/1e6:.1f}MB | dur={metrics['duration']}s")

    # Update 聂小倩 manifest (separate from 无限恐怖 batch)
    nie_mp = out_root / "manifest_niexiaoqian.json"
    if nie_mp.exists():
        nie_manifest = json.loads(nie_mp.read_text(encoding="utf-8"))
    else:
        nie_manifest = {
            "run_id": run_id,
            "engine": "Skylark Agent 2.0 = Seedance 2.0 fast 720p with reference",
            "skylark_req_key": "pippit_iv2v_v20_cvtob_with_vinput",
            "skylark_ratio": "9:16",
            "skylark_language": "Chinese",
            "skylark_enable_watermark": False,
            "master_profile": "world_class_cinematic_v1",
            "target_resolution": "1080x1920",
            "target_fps": 24,
            "novel_source": "聊斋·聂小倩 蒲松龄 ~1740 公版",
            "episodes": [],
        }

    # Replace or append entry
    entry = {
        "id": args.ep,
        "ok": True,
        "task_id": result.task_id,
        "final_path": str(final_path.resolve()),
        "raw_path": str(raw_path.resolve()),
        "duration_preset": "～15s",
        "master_cap_seconds": master_cap,
        "aigc_meta_tagged": bool(result.aigc_meta_tagged),
        "aigc_meta": {
            "content_producer": aigc_meta.content_producer,
            "producer_id": aigc_meta.producer_id,
            "content_propagator": aigc_meta.content_propagator,
            "propagate_id": aigc_meta.propagate_id,
        },
        "reported_output_seconds": result.output_duration_seconds,
        "master_metrics": metrics,
        "round": "R22-R24",
        "generated_at": _dt.datetime.now(_dt.timezone.utc).isoformat(),
    }
    nie_manifest["episodes"] = [e for e in nie_manifest["episodes"] if e["id"] != args.ep]
    nie_manifest["episodes"].append(entry)
    nie_mp.write_text(json.dumps(nie_manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n[DONE] {args.ep} written to {nie_mp.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
