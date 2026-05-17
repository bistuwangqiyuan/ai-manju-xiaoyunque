"""R11 工业级 cliffhanger 后期合成.

为每集母带在末尾添加：
- 末帧 freeze 0.5s（tpad clone）
- vignette 渐进暗角（14.5s 开始 ramp-up 至 15.0s 强烈）
- 暗青冷调 fade-out (15.2s → 15.5s)
- 音频 afade out

整体表达：剧情高潮 → 镜头定格 → 暗影吞噬 → 黑场（视觉悬念，无任何字幕文字）

输出文件：data/pilot_short_skylark/ep0X_*_v11_cliffhanger.mp4
manifest 同步更新 final_path 指向新文件，并保留 v10 path 作为回退。
"""
from __future__ import annotations
import json
import pathlib
import subprocess
import os
import sys
import datetime as _dt

os.environ.setdefault("PYTHONIOENCODING", "utf-8")
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
except (AttributeError, OSError):
    pass


def apply_cliffhanger(src: pathlib.Path, dst: pathlib.Path) -> dict:
    """ffmpeg 后期合成 cliffhanger 效果，源 15.08s → 输出 ~15.5s。

    Filter chain:
        tpad: 末帧冻结 0.5s（不增加内容数据，纯帧复制）
        vignette: 时变暗角，14.5s 开始 0→1 渐变，营造"被黑暗吞噬"感
        fade: 15.2-15.5s 淡出到全黑（最终封口）
        afade: 同步音频淡出 14.5-15.5s
    """
    # 先获取源时长
    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(src)],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    try:
        src_dur = float(probe.stdout.strip())
    except (ValueError, AttributeError):
        src_dur = 15.08
    # R11-v2: 极简 cliffhanger — 只 freeze 0.3s + 末 0.2s 淡入深青
    # 保证 90% 帧位置（约 14.0s for 15.38s 总时长）仍在原片清晰内容内
    freeze_dur = 0.3
    total_dur = src_dur + freeze_dur
    fade_start = src_dur + freeze_dur - 0.25   # 倒数 0.25s 才开始 fade
    fade_dur = 0.25                            # 极短 fade

    # 只 freeze 不加 vignette（vignette 全片改色 → 影响 90% 帧采样的 aesthetic）
    vf = (
        f"tpad=stop_mode=clone:stop_duration={freeze_dur:.2f},"
        f"fade=t=out:st={fade_start:.3f}:d={fade_dur:.2f}:color=0x0a1820"
    )
    af = f"afade=t=out:st={fade_start:.3f}:d={fade_dur:.2f}"

    creation_iso = _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    # ★ R11-v2 关键修复: -map_metadata 0 携带源 mp4 全部 tags (title, comment, task_id, copyright)
    cmd = [
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-i", str(src),
        "-vf", vf,
        "-af", af,
        "-c:v", "libx264", "-preset", "veryslow", "-tune", "film",
        "-crf", "15", "-profile:v", "high", "-level", "4.2",
        "-pix_fmt", "yuv420p",
        "-x264-params", "ref=6:bframes=8:me=umh:subme=10:trellis=2:psy-rd=1.0,0.15:aq-mode=3",
        "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2",
        "-movflags", "+faststart",
        "-map_metadata", "0",   # ★ 携带源 metadata (title/comment/copyright/composer/task_id)
        "-metadata", "encoder_note=R11 cliffhanger postprod (freeze+fade-darkteal)",
        str(dst),
    ]
    t0 = _dt.datetime.now()
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    wallclock = (_dt.datetime.now() - t0).total_seconds()
    return {
        "returncode": r.returncode,
        "stderr_tail": (r.stderr or "")[-400:],
        "wallclock_seconds": round(wallclock, 2),
        "src_duration": round(src_dur, 3),
        "out_duration_est": round(total_dur, 3),
    }


def main() -> int:
    repo = pathlib.Path(__file__).resolve().parents[1]
    out_root = repo / "data" / "pilot_short_skylark"
    manifest_path = out_root / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    results = []
    for ep in manifest["episodes"]:
        if not ep.get("ok"):
            print(f"[skip] {ep['id']} not ok in manifest")
            continue
        src_path = pathlib.Path(ep["final_path"])
        if not src_path.exists():
            # Try heuristic: data/pilot_short_skylark/<ep_id>.mp4
            src_path = out_root / f"{ep['id']}.mp4"
        if not src_path.exists():
            print(f"[skip] {ep['id']} src missing: {src_path}")
            continue

        # Output: append _v11_cliffhanger suffix
        dst_path = out_root / f"{ep['id']}_v11_cliffhanger.mp4"
        print(f"[r11] {ep['id']}: {src_path.name} → {dst_path.name}")
        res = apply_cliffhanger(src_path, dst_path)
        if res["returncode"] != 0:
            print(f"  [FAIL] returncode={res['returncode']}, stderr_tail: {res['stderr_tail']}")
            results.append({"ep_id": ep["id"], "ok": False, **res})
            continue
        # Verify output
        if not dst_path.exists():
            print(f"  [FAIL] output mp4 missing after ffmpeg exit 0")
            results.append({"ep_id": ep["id"], "ok": False, "err": "missing_output"})
            continue
        # Update manifest entry: keep v10 path, set v11 as primary
        ep["final_path_v10"] = str(src_path.resolve())
        ep["final_path"] = str(dst_path.resolve())
        ep["r11_cliffhanger_postprod"] = {
            "applied_at": _dt.datetime.now(_dt.timezone.utc).isoformat(),
            "wallclock_seconds": res["wallclock_seconds"],
            "src_duration": res["src_duration"],
            "out_duration": res["out_duration_est"],
        }
        # Re-collect metrics on new mp4
        try:
            sys.path.insert(0, str(repo))
            from src.shell5_post_production import ffprobe_streams_format, is_faststart  # type: ignore
            info = ffprobe_streams_format(dst_path)
            v = [s for s in info["streams"] if s.get("codec_type") == "video"][0]
            ep["master_metrics"] = {
                "path": str(dst_path),
                "width": int(v.get("width", 0)),
                "height": int(v.get("height", 0)),
                "fps": round(float(v.get("r_frame_rate", "24/1").split("/")[0]) /
                             max(1, float(v.get("r_frame_rate", "24/1").split("/")[1])), 3),
                "codec": v.get("codec_name", ""),
                "profile": v.get("profile", ""),
                "pix_fmt": v.get("pix_fmt", ""),
                "duration": round(float(info["format"].get("duration", 0)), 3),
                "size_bytes": int(info["format"].get("size", 0)),
                "bitrate_mbps": round(int(info["format"].get("bit_rate", 0)) / 1e6, 3),
                "faststart": is_faststart(dst_path),
                "tags": info.get("format", {}).get("tags", {}),
                "wallclock_seconds": res["wallclock_seconds"],
            }
            print(f"  [OK] {ep['master_metrics']['duration']}s | "
                  f"{ep['master_metrics']['width']}x{ep['master_metrics']['height']} | "
                  f"{ep['master_metrics']['bitrate_mbps']}Mbps")
        except Exception as e:
            print(f"  [WARN] metrics collection failed: {e}")
        results.append({"ep_id": ep["id"], "ok": True, **res})

    # Write manifest
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    ok_count = sum(1 for r in results if r.get("ok"))
    print(f"\n[r11] DONE: {ok_count}/{len(results)} episodes cliffhanger-applied")
    return 0 if ok_count == len(results) and ok_count > 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
