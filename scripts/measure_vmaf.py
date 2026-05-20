"""VMAF self-roundtrip measurement.

将 1080p 母带下采样到 720(匹配 raw)，再与 raw 720 做 VMAF 评分。
VMAF (Video Multi-Method Assessment Fusion) 是 Netflix 的感知质量指标，
ffmpeg libvmaf 内置。世界级母带阈值 ≥ 85。

用法:
    python scripts/measure_vmaf.py
读 data/pilot_short_skylark/manifest.json 与对应 raw/，逐集计算 VMAF，
回写到 manifest 的 episodes[i].vmaf_self_roundtrip 字段。
"""
from __future__ import annotations

import json
import pathlib
import re
import subprocess
import sys
import tempfile

_REPO = pathlib.Path(__file__).resolve().parents[1]


def measure_vmaf(master_1080: pathlib.Path, raw_720: pathlib.Path) -> float | None:
    """1080 母带先下采到 720 → 与 raw 720 做 VMAF 比对。"""

    if not master_1080.exists() or not raw_720.exists():
        return None

    with tempfile.TemporaryDirectory() as td:
        downsampled = pathlib.Path(td) / "master_720.mp4"
        # 第一遍：将 master 1080 下采到 720 (与 raw 同尺寸便于 VMAF)
        cmd1 = [
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
            "-i", str(master_1080),
            "-vf", "zscale=w=720:h=1280:filter=spline36",
            "-c:v", "libx264", "-preset", "fast", "-crf", "12",
            "-pix_fmt", "yuv420p",
            "-an",  # 不要音频
            str(downsampled),
        ]
        proc1 = subprocess.run(cmd1, capture_output=True, text=True,
                               encoding="utf-8", errors="replace")
        if proc1.returncode != 0:
            return None

        # 第二遍：VMAF (raw 720 作为 reference，master 720 作为 distorted)
        out_json = pathlib.Path(td) / "vmaf.json"
        cmd2 = [
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "info",
            "-i", str(downsampled),
            "-i", str(raw_720),
            "-lavfi",
            f"[0:v]setpts=PTS-STARTPTS[d];"
            f"[1:v]trim=duration={_duration_seconds(downsampled):.2f},setpts=PTS-STARTPTS[r];"
            f"[d][r]libvmaf=log_path={out_json.as_posix()}:log_fmt=json",
            "-f", "null", "-",
        ]
        proc2 = subprocess.run(cmd2, capture_output=True, text=True,
                               encoding="utf-8", errors="replace")
        # libvmaf 把分数写到 stderr 也可能写到 json
        if out_json.exists():
            try:
                vmaf_data = json.loads(out_json.read_text(encoding="utf-8"))
                pooled = vmaf_data.get("pooled_metrics", {})
                vmaf_score = pooled.get("vmaf", {}).get("mean")
                if vmaf_score is not None:
                    return float(vmaf_score)
            except Exception:
                pass
        # 兜底从 stderr 文本解析 "VMAF score: NN.NN"
        m = re.search(r"VMAF score:\s*([\d.]+)", proc2.stderr or "")
        if m:
            return float(m.group(1))
    return None


def _duration_seconds(path: pathlib.Path) -> float:
    try:
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
            check=True, capture_output=True, text=True,
            encoding="utf-8", errors="replace",
        ).stdout
        return float(out.strip())
    except Exception:
        return 0.0


def main() -> int:
    manifest_path = _REPO / "data" / "pilot_short_skylark" / "manifest.json"
    if not manifest_path.exists():
        print("ERROR: manifest.json missing")
        return 1
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    n_ok = 0
    for ep in manifest.get("episodes", []):
        if not ep.get("ok"):
            continue
        final = pathlib.Path(ep["final_path"])
        raw = pathlib.Path(ep["raw_path"])
        print(f"  measuring VMAF for {ep['id']}…")
        score = measure_vmaf(final, raw)
        if score is not None:
            ep["vmaf_self_roundtrip"] = round(score, 2)
            n_ok += 1
            print(f"    VMAF = {score:.2f}")
        else:
            ep["vmaf_self_roundtrip"] = None
            print(f"    VMAF measurement FAILED for {ep['id']}")

    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2),
                              encoding="utf-8")
    print(f"Updated {n_ok} episodes with VMAF scores")
    return 0 if n_ok > 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
