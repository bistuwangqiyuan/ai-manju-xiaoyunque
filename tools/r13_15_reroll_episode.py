"""R13/R14/R15 单集 Skylark reroll — 用 R12 prompt 真接口重生 + master.

用法:
    python tools/r13_15_reroll_episode.py --ep ep03_train_arrives
    python tools/r13_15_reroll_episode.py --ep ep02_zhangjie_revolver
    python tools/r13_15_reroll_episode.py --ep ep01_zhengzha_wakes

每次只 reroll 一集（节省 Skylark API 调用 + 防止 QPS 50430）。
生成的 raw 替换 raw/<ep_id>.raw.mp4，新 master 覆盖 <ep_id>.mp4，manifest 同步更新。
"""
from __future__ import annotations
import argparse
import json
import os
import pathlib
import shutil
import sys
import uuid
import datetime as _dt

os.environ.setdefault("PYTHONIOENCODING", "utf-8")
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
except (AttributeError, OSError):
    pass


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ep", required=True, help="Episode id (ep01_zhengzha_wakes / ep02_zhangjie_revolver / ep03_train_arrives)")
    args = parser.parse_args()

    repo = pathlib.Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(repo))

    from pilot.run_three_short_episodes import load_env_file, _make_aigc_meta  # type: ignore
    load_env_file(repo / ".env")

    # Load R12 prompt
    r12_path = repo / "prompts" / "episodes" / "r12_v2.json"
    if not r12_path.exists():
        print(f"[fatal] R12 prompt file missing: {r12_path}")
        return 1
    r12 = json.loads(r12_path.read_text(encoding="utf-8"))
    target = next((r for r in r12 if r.get("ep_id") == args.ep and r.get("ok")), None)
    if not target:
        print(f"[fatal] no R12 prompt for {args.ep}")
        return 1
    prompt = target["prompt"]
    print(f"[r13/14/15] target ep: {args.ep}")
    print(f"  R12 prompt len: {len(prompt)}")
    print(f"  preview: {prompt[:120]!r}...")

    from src.shell3_skylark_engine import (  # type: ignore
        EpisodeRequest,
        ReferencePack,
        SkylarkAgentV2WithRefClient,
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
        print(f"  [trunc] prompt {len(prompt)} > 2000, truncating to 2000")
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

    print(f"\n[skylark] submitting {args.ep} (R12 prompt, ~15s preset)...")
    t0 = _dt.datetime.now()
    try:
        result = client.render_episode(req, ep_id=args.ep)
    except Exception as e:
        print(f"[FAIL] Skylark error: {type(e).__name__}: {e}")
        return 1
    wallclock = (_dt.datetime.now() - t0).total_seconds()
    print(f"[skylark] done in {wallclock:.0f}s | task_id={result.task_id} | dur={result.output_duration_seconds:.2f}s | aigc_tagged={result.aigc_meta_tagged}")

    # Archive raw + master
    raw_path = raw_dir / f"{args.ep}.raw.mp4"
    final_path = out_root / f"{args.ep}.mp4"
    shutil.copy2(result.archived_video_path, raw_path)
    print(f"[raw] {raw_path}")

    print(f"\n[master] applying Shell 5 cinematic master...")
    master_cap = 17.0
    cfg = MasterConfig(duration_cap_seconds=master_cap)
    try:
        metrics = master(raw_path, final_path, ep_id=args.ep, task_id=result.task_id, config=cfg)
    except MasterError as e:
        print(f"[FAIL] master error: {e}")
        return 1
    except Exception as e:
        print(f"[FAIL] master unexpected: {type(e).__name__}: {e}")
        return 1
    print(f"[master] done | {metrics['width']}x{metrics['height']}@{metrics['fps']}fps | {metrics['bitrate_mbps']}Mbps | {metrics['size_bytes']/1e6:.1f}MB | dur={metrics['duration']}s")

    # Patch manifest
    mp = out_root / "manifest.json"
    manifest = json.loads(mp.read_text(encoding="utf-8"))
    for ep in manifest["episodes"]:
        if ep["id"] == args.ep:
            ep["ok"] = True
            ep["task_id"] = result.task_id
            ep["final_path"] = str(final_path.resolve())
            ep["raw_path"] = str(raw_path.resolve())
            ep["duration_preset"] = "～15s"
            ep["master_cap_seconds"] = master_cap
            ep["aigc_meta_tagged"] = bool(result.aigc_meta_tagged)
            ep["reported_output_seconds"] = result.output_duration_seconds
            ep["master_metrics"] = metrics
            ep["reroll_round"] = "R13/14/15"
            ep["reroll_at"] = _dt.datetime.now(_dt.timezone.utc).isoformat()
            print(f"  [manifest] patched entry for {args.ep}")
            break
    mp.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n[DONE] {args.ep} rerolled successfully")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
