"""100-point scoring rubric for 3-episode pilot (per final-plan.md 验收 KPI).

re-weighted for silent ~15s smoke test (lipsync/voice clone N/A → 分摊到其他维度):

| # | Dimension                                            | Weight | Method                |
|---|------------------------------------------------------|--------|-----------------------|
| 1 | Real Skylark API task_id (numeric Volcengine snowflake)  | 5  | manifest regex         |
| 2 | AIGC aigc_meta_tagged=True from Skylark response         | 8  | manifest               |
| 3 | Visible AIGC watermark "AI 生成" ROI Y p99 ≥ 140         | 7  | sample_roi_stats       |
| 4 | Resolution 1080×1920 portrait 9:16                        | 10 | ffprobe                |
| 5 | Frame rate 24fps ±0.05                                   | 5  | ffprobe                |
| 6 | H.264 High + yuv420p + faststart                         | 8  | ffprobe + box parse    |
| 7 | Bitrate ≥ 8 Mbps (master grade)                          | 5  | ffprobe                |
| 8 | mp4 udta metadata (title+comment+copyright+composer+ts)  | 5  | ffprobe tags           |
| 9 | Episode duration in Skylark preset window                | 5  | ffprobe                |
| 10 | ArcFace cross-episode ID similarity ≥ 0.80 (final KPI)  | 12 | insightface (optional) |
| 11 | VMAF self-roundtrip vs raw 720 ≥ 85                      | 10 | ffmpeg libvmaf         |
| 12 | Laplacian sharpness (Var on mid-frame Y) ≥ 1500          | 5  | PIL                    |
| 13 | Color grade match (teal-orange hue histogram)            | 5  | hue analysis           |
| 14 | Prompt density (≥800 chars + 3+ structured beats)        | 4  | text analysis          |
| 15 | Scene fidelity to source novel chapter (manual gate)     | 6  | external (manual)      |

合计: 100.
"""
from __future__ import annotations

import json
import math
import pathlib
import re
import subprocess
import sys
from dataclasses import dataclass
from typing import Any

_REPO = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO))

from src.shell5_post_production import (  # noqa: E402
    ffprobe_streams_format,
    is_faststart,
    sample_roi_stats,
)


@dataclass
class DimensionScore:
    name: str
    weight: int
    raw_points: float    # 0..weight
    notes: str


TASK_ID_RE = re.compile(r"^[0-9]{12,}$")  # Volcengine snowflake (real Skylark)


def score_episode(ep: dict, prompt_text: str = "") -> list[DimensionScore]:
    """Score a single episode entry against the 15-dimension rubric."""

    scores: list[DimensionScore] = []
    if not ep.get("ok"):
        # 全部失败
        scores.append(DimensionScore("ep_overall_status", 100, 0,
                                     f"episode failed: {ep.get('error','')}"))
        return scores
    final = pathlib.Path(ep["final_path"])
    if not final.exists():
        scores.append(DimensionScore("final_mp4_missing", 100, 0, str(final)))
        return scores
    info = ffprobe_streams_format(final)
    vstreams = [s for s in info["streams"] if s.get("codec_type") == "video"]
    if not vstreams:
        scores.append(DimensionScore("no_video_stream", 100, 0, ""))
        return scores
    v = vstreams[0]
    fmt = info.get("format", {})
    tags = fmt.get("tags") or {}

    # 1. Real Skylark task_id
    tid = str(ep.get("task_id", ""))
    is_real = bool(TASK_ID_RE.match(tid)) and tid not in ("completed", "skipped_existing")
    scores.append(DimensionScore(
        "1_real_skylark_task_id", 5,
        5 if is_real else 0,
        f"task_id={tid!r} real={is_real}",
    ))

    # 2. AIGC aigc_meta_tagged
    aigc_tagged = bool(ep.get("aigc_meta_tagged", False))
    scores.append(DimensionScore(
        "2_aigc_meta_tagged", 8,
        8 if aigc_tagged else 0,
        f"aigc_meta_tagged={aigc_tagged}",
    ))

    # 3. Visible AIGC watermark
    w, h = int(v.get("width", 0)), int(v.get("height", 0))
    p99 = 0.0
    try:
        roi = (max(0, w - 270), max(0, h - 110), max(0, w - 10), max(0, h - 20))
        stats = sample_roi_stats(final, t_sec=7.0, roi=roi)
        p99 = stats["roi_p99"]
    except Exception:
        try:
            # 重试更短帧时刻（短片）
            dur = float(fmt.get("duration", 0) or 0)
            t = max(0.5, dur / 2 - 0.2)
            stats = sample_roi_stats(final, t_sec=t, roi=roi)
            p99 = stats["roi_p99"]
        except Exception as exc:
            stats = None
    pts = 7 if p99 >= 140 else (4 if p99 >= 100 else 0)
    scores.append(DimensionScore(
        "3_watermark_visible_p99", 7, pts,
        f"roi_p99={p99:.0f}",
    ))

    # 4. Resolution 1080x1920 portrait
    target_ok = (w == 1080 and h == 1920)
    portrait = h > w
    pts4 = 10 if target_ok else (5 if portrait and min(w, h) >= 720 else 0)
    scores.append(DimensionScore(
        "4_resolution_1080x1920", 10, pts4,
        f"{w}x{h} portrait={portrait}",
    ))

    # 5. Frame rate 24fps
    rfr = v.get("r_frame_rate", "0/1")
    try:
        num, den = rfr.split("/")
        fps = float(num) / float(den) if float(den) else 0.0
    except Exception:
        fps = 0.0
    pts5 = 5 if 23.95 <= fps <= 24.05 else (2 if 23.0 <= fps <= 25.0 else 0)
    scores.append(DimensionScore("5_framerate_24fps", 5, pts5, f"fps={fps:.3f}"))

    # 6. H.264 High + yuv420p + faststart
    is_h264 = v.get("codec_name") == "h264"
    is_yuv420p = v.get("pix_fmt") == "yuv420p"
    is_high = "High" in (v.get("profile", "") or "")
    is_fs = False
    try:
        is_fs = is_faststart(final)
    except Exception:
        pass
    n_ok = sum([is_h264, is_yuv420p, is_high, is_fs])
    pts6 = round(8 * n_ok / 4, 2)
    scores.append(DimensionScore(
        "6_codec_yuv420p_high_faststart", 8, pts6,
        f"h264={is_h264} yuv420p={is_yuv420p} High={is_high} faststart={is_fs}",
    ))

    # 7. Bitrate ≥ 8 Mbps
    br_mbps = int(fmt.get("bit_rate", 0)) / 1e6
    pts7 = 5 if br_mbps >= 8 else (3 if br_mbps >= 6 else (1 if br_mbps >= 4 else 0))
    scores.append(DimensionScore("7_bitrate_mbps", 5, pts7, f"{br_mbps:.1f} Mbps"))

    # 8. mp4 udta metadata 5 fields
    required = ("title", "comment", "copyright", "composer", "creation_time")
    n_meta = sum(1 for k in required if tags.get(k))
    pts8 = round(5 * n_meta / 5, 2)
    scores.append(DimensionScore(
        "8_udta_metadata", 5, pts8,
        f"{n_meta}/5 fields present",
    ))

    # 9. Duration in preset window
    dur = float(fmt.get("duration", 0) or 0)
    preset = ep.get("duration_preset_used") or ep.get("duration_preset", "")
    windows = {
        "～15s": (11.0, 17.0), "~15s": (11.0, 17.0),
        "～30s": (24.0, 35.5), "~30s": (24.0, 35.5),
        "40～60s": (38.0, 62.0), "40~60s": (38.0, 62.0),
    }
    lo, hi = windows.get(preset, (8.0, 62.0))
    pts9 = 5 if lo <= dur <= hi else (3 if 5 <= dur <= 70 else 0)
    scores.append(DimensionScore(
        "9_duration_preset_window", 5, pts9,
        f"dur={dur:.2f}s preset={preset} window=[{lo}, {hi}]",
    ))

    # 10. ArcFace ID similarity (require Shell 2 refs — placeholder for now)
    arcface = ep.get("arcface_cross_episode_min", None)
    if arcface is None:
        pts10 = 0
        note = "no ArcFace measure (needs Shell 2 refs + cross-ep inference)"
    else:
        pts10 = 12 if arcface >= 0.80 else (8 if arcface >= 0.70 else (4 if arcface >= 0.60 else 0))
        note = f"arcface={arcface:.3f}"
    scores.append(DimensionScore("10_arcface_id_similarity", 12, pts10, note))

    # 11. VMAF self-roundtrip
    vmaf = ep.get("vmaf_self_roundtrip", None)
    if vmaf is None:
        pts11 = 0
        note = "no VMAF measure"
    else:
        pts11 = 10 if vmaf >= 85 else (7 if vmaf >= 75 else (4 if vmaf >= 60 else 1))
        note = f"vmaf={vmaf:.2f}"
    scores.append(DimensionScore("11_vmaf_self_roundtrip", 10, pts11, note))

    # 12. Laplacian sharpness
    sharp = _laplacian_variance(final, t_sec=max(0.5, dur / 2 - 0.2))
    pts12 = 5 if sharp >= 1500 else (3 if sharp >= 1000 else (1 if sharp >= 500 else 0))
    scores.append(DimensionScore(
        "12_laplacian_sharpness", 5, pts12,
        f"var={sharp:.0f}",
    ))

    # 13. Color grade match (cyberpunk teal-orange)
    hue_score = _teal_orange_hue_score(final, t_sec=max(0.5, dur / 2 - 0.2))
    pts13 = round(5 * hue_score, 2)
    scores.append(DimensionScore(
        "13_color_teal_orange", 5, pts13,
        f"teal_orange_score={hue_score:.2f}",
    ))

    # 14. Prompt density (≥800 chars + ≥3 beats `【...】`)
    n_chars = len(prompt_text)
    n_beats = len(re.findall(r"【[^】]+】", prompt_text))
    pts14 = 0
    if n_chars >= 800 and n_beats >= 3:
        pts14 = 4
    elif n_chars >= 500 and n_beats >= 2:
        pts14 = 2
    elif prompt_text:
        pts14 = 1
    scores.append(DimensionScore(
        "14_prompt_density_beats", 4, pts14,
        f"len={n_chars} beats={n_beats}",
    ))

    # 15. Scene fidelity (manual)
    fidelity = ep.get("manual_scene_fidelity", None)
    if fidelity is None:
        pts15 = 4  # 默认中等：未人工标注前给中位分
        note = "manual fidelity not marked; default 4/6"
    else:
        pts15 = round(6 * float(fidelity), 2)
        note = f"manual={fidelity:.2f}"
    scores.append(DimensionScore("15_scene_fidelity_manual", 6, pts15, note))

    return scores


def _laplacian_variance(video_path: pathlib.Path, *, t_sec: float) -> float:
    """ROI-free 帧 Laplacian variance — 锐度统计代理指标。"""

    from PIL import Image, ImageFilter  # type: ignore
    import io

    cmd = [
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-ss", f"{t_sec:.3f}", "-i", str(video_path),
        "-frames:v", "1",
        "-f", "image2pipe", "-pix_fmt", "gray", "-vcodec", "png", "pipe:1",
    ]
    try:
        proc = subprocess.run(cmd, check=True, capture_output=True)
        img = Image.open(io.BytesIO(proc.stdout)).convert("L")
        edges = img.filter(ImageFilter.FIND_EDGES)
        pixels = list(edges.getdata())
        if not pixels:
            return 0.0
        m = sum(pixels) / len(pixels)
        var = sum((p - m) ** 2 for p in pixels) / len(pixels)
        return var
    except Exception:
        return 0.0


def _teal_orange_hue_score(video_path: pathlib.Path, *, t_sec: float) -> float:
    """评 0..1 ：色相直方图中"暖橘 + 冷青"两端占比之和 vs 中段。

    cinematic teal-orange 应让 hue 集中在两端（橙 H≈30 + 青 H≈180-220），
    中段（绿 H≈90 + 品红 H≈300）应该稀少。
    """

    from PIL import Image  # type: ignore
    import io

    cmd = [
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-ss", f"{t_sec:.3f}", "-i", str(video_path),
        "-frames:v", "1",
        "-vf", "scale=270:480",   # 下采样以加速
        "-f", "image2pipe", "-vcodec", "png", "pipe:1",
    ]
    try:
        proc = subprocess.run(cmd, check=True, capture_output=True)
        img = Image.open(io.BytesIO(proc.stdout)).convert("HSV")
        hue_pixels = [p[0] for p in img.getdata()]
        if not hue_pixels:
            return 0.0
        # H 0..255 in PIL HSV. orange ≈ 15-40, teal ≈ 100-150
        orange = sum(1 for h in hue_pixels if 10 <= h <= 45)
        teal = sum(1 for h in hue_pixels if 95 <= h <= 155)
        mid = sum(1 for h in hue_pixels if 55 <= h <= 90 or 165 <= h <= 200)
        total = len(hue_pixels)
        end_ratio = (orange + teal) / total
        mid_ratio = mid / total
        # 端比≥0.30 且中段<0.15 给满分
        if end_ratio >= 0.30 and mid_ratio <= 0.15:
            return 1.0
        if end_ratio >= 0.20 and mid_ratio <= 0.25:
            return 0.7
        if end_ratio >= 0.15:
            return 0.4
        return 0.1
    except Exception:
        return 0.0


def _load_prompt_map() -> dict[str, str]:
    """读 prompts/episodes/infinite_horror_ch1.py 取每集 prompt 文本"""
    try:
        from prompts.episodes import infinite_horror_ch1
        return {ep["ep_id"]: ep["prompt"] for ep in infinite_horror_ch1.EPISODES}
    except Exception:
        return {}


def main() -> int:
    out_root = _REPO / "data" / "pilot_short_skylark"
    manifest_path = out_root / "manifest.json"
    if not manifest_path.exists():
        print(f"ERROR: missing {manifest_path}; run pilot first")
        return 1
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    prompt_map = _load_prompt_map()

    report: dict[str, Any] = {
        "run_id": manifest.get("run_id"),
        "engine": manifest.get("engine"),
        "color_profile": manifest.get("color_profile", "unknown"),
        "episodes": [],
        "summary": {},
    }

    total_weighted = 0.0
    n_episodes = 0
    per_dim: dict[str, list[float]] = {}

    for ep in manifest.get("episodes", []):
        prompt = prompt_map.get(ep.get("id", ""), "")
        scores = score_episode(ep, prompt_text=prompt)
        ep_total = sum(s.raw_points for s in scores)
        ep_max = sum(s.weight for s in scores)
        ep_pct = (ep_total / ep_max * 100.0) if ep_max else 0.0
        ep_report = {
            "id": ep.get("id"),
            "score_pct": round(ep_pct, 2),
            "score_raw": round(ep_total, 2),
            "score_max": ep_max,
            "dimensions": [
                {"name": s.name, "weight": s.weight, "points": round(s.raw_points, 2), "notes": s.notes}
                for s in scores
            ],
        }
        report["episodes"].append(ep_report)
        total_weighted += ep_pct
        n_episodes += 1
        for s in scores:
            per_dim.setdefault(s.name, []).append(s.raw_points / s.weight if s.weight else 0.0)

    overall = total_weighted / n_episodes if n_episodes else 0.0
    report["summary"] = {
        "overall_score_pct": round(overall, 2),
        "n_episodes": n_episodes,
        "weakest_dimensions": _weakest_dims(per_dim, k=3),
    }

    out_path = out_root / "score_report.json"
    out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Score report written to: {out_path}")
    print(f"\n=== OVERALL: {overall:.2f}/100 ({n_episodes} episodes) ===")
    print("\nWeakest dimensions (need improvement):")
    for name, pct in report["summary"]["weakest_dimensions"]:
        print(f"  {name}: {pct*100:.0f}% avg")
    print("\nPer-episode:")
    for ep_r in report["episodes"]:
        print(f"  {ep_r['id']}: {ep_r['score_pct']}/100 ({ep_r['score_raw']}/{ep_r['score_max']} pts)")
    return 0


def _weakest_dims(per_dim: dict[str, list[float]], k: int = 3) -> list[tuple[str, float]]:
    avg = [(name, sum(pcts) / len(pcts)) for name, pcts in per_dim.items() if pcts]
    avg.sort(key=lambda x: x[1])
    return avg[:k]


if __name__ == "__main__":
    raise SystemExit(main())
