"""一轮完整迭代: pilot → VMAF → ArcFace → 评分 → 快照。

用法:
    python scripts/run_round.py R1
    python scripts/run_round.py R2 --skip-pilot   # 仅重测分
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import pathlib
import shutil
import subprocess
import sys

_REPO = pathlib.Path(__file__).resolve().parents[1]


def _run(cmd: list[str], *, label: str) -> bool:
    print(f"\n{'='*70}")
    print(f"  [{label}] {' '.join(cmd)}")
    print('='*70)
    proc = subprocess.run(cmd, cwd=_REPO,
                          capture_output=False, text=True,
                          encoding="utf-8", errors="replace")
    ok = proc.returncode == 0
    print(f"  [{label}] {'OK' if ok else 'FAIL'} (exit {proc.returncode})")
    return ok


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("round_id", help="轮次标识 R1 / R2 / ...")
    ap.add_argument("--skip-pilot", action="store_true",
                    help="跳过 Skylark+master，仅重测/重评分")
    ap.add_argument("--skip-arcface", action="store_true",
                    help="跳过 ArcFace 测量（无 insightface 时）")
    ap.add_argument("--skip-vmaf", action="store_true", help="跳过 VMAF")
    args = ap.parse_args()

    out_root = _REPO / "data" / "pilot_short_skylark"
    out_root.mkdir(parents=True, exist_ok=True)
    log_path = out_root / f"{args.round_id}_run_log.txt"

    started = _dt.datetime.now(_dt.timezone.utc).isoformat()
    print(f"\n=== Round {args.round_id} started at {started} ===")

    # Step 1: pilot (Skylark + cinematic master)
    if not args.skip_pilot:
        ok = _run(
            [sys.executable, "-X", "utf8", "pilot/run_three_short_episodes.py"],
            label="pilot",
        )
        if not ok:
            print(f"WARNING: pilot returned non-zero; continuing with whatever was produced")

    # Step 2: VMAF self-roundtrip
    if not args.skip_vmaf:
        _run([sys.executable, "scripts/measure_vmaf.py"], label="VMAF")

    # Step 3: ArcFace cross-episode
    if not args.skip_arcface:
        _run([sys.executable, "scripts/measure_arcface.py"], label="ArcFace")

    # Step 4: 100-point scoring
    _run([sys.executable, "scripts/score_episodes.py"], label="score")

    # Step 5: 快照
    score_path = out_root / "score_report.json"
    if score_path.exists():
        round_path = out_root / f"{args.round_id}_score.json"
        shutil.copy2(score_path, round_path)
        report = json.loads(score_path.read_text(encoding="utf-8"))
        round_meta = {
            "round_id": args.round_id,
            "started_at": started,
            "finished_at": _dt.datetime.now(_dt.timezone.utc).isoformat(),
            "overall_score": report["summary"]["overall_score_pct"],
            "weakest": report["summary"]["weakest_dimensions"],
        }
        snap_path = out_root / f"{args.round_id}_meta.json"
        snap_path.write_text(json.dumps(round_meta, ensure_ascii=False, indent=2),
                              encoding="utf-8")
        print(f"\n=== Round {args.round_id}: {round_meta['overall_score']}/100 ===")
        print("Weakest:")
        for name, pct in round_meta["weakest"]:
            print(f"  {name}: {pct*100:.0f}%")
        # 复制 final mp4 到本轮快照
        snap_dir = out_root / "snapshots" / args.round_id
        snap_dir.mkdir(parents=True, exist_ok=True)
        for mp4 in out_root.glob("ep0*_micro*.mp4") if False else []:
            shutil.copy2(mp4, snap_dir / mp4.name)
        for ep_id in ("ep01_zhengzha_wakes", "ep02_zhangjie_revolver", "ep03_train_arrives"):
            src = out_root / f"{ep_id}.mp4"
            if src.exists():
                shutil.copy2(src, snap_dir / f"{ep_id}.mp4")
        return 0
    print("ERROR: score_report.json missing — scoring failed")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
