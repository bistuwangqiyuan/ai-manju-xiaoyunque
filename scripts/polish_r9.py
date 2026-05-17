"""R9 极致后处理 — 在 R8 母带基础上叠加电影级再加工。

链路（FFmpeg 一遍 filter_complex）:
1. 取 ep0X_zhengzha_wakes.mp4 等当前 R8 母带作为输入
2. 高光晕 halation (split→gaussian blur 大半径→screen blend) 模拟胶片 halation
3. Chromatic aberration (R/G/B 通道微位移) — 现代赛博惊悚电影标配
4. 强化 teal-orange LUT (二次 colorbalance + curves，把 shadow 推更冷青、highlight 推更暖橘)
5. 胶片颗粒 film grain (noise=alls=10:allf=t+u) — 微粒度避免 banding，增加 LAION 评价的"电影感"
6. 锐化二次 (unsharp 5:5:1.0 较 R8 更强)
7. H.264 crf=14 (比 R8 crf=15 更高码率) + faststart 两遍

输出到 data/pilot_short_skylark/r9/<ep_id>.mp4
"""
from __future__ import annotations

import datetime as _dt
import json
import pathlib
import subprocess
import sys

_REPO = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO))


# R8 母带文件
EP_SOURCES = {
    "ep01_zhengzha_wakes": "data/pilot_short_skylark/ep01_zhengzha_wakes.mp4",
    "ep02_zhangjie_revolver": "data/pilot_short_skylark/ep02_zhangjie_revolver.mp4",
    "ep03_train_arrives": "data/pilot_short_skylark/ep03_train_arrives.mp4",
}


def _font_path() -> str:
    """与 cinematic_master 同款字体探测。"""
    for p in ("C:/Windows/Fonts/msyhbd.ttc", "C:/Windows/Fonts/simhei.ttf"):
        if pathlib.Path(p).exists():
            return p
    raise RuntimeError("no Chinese bold font")


def _build_r9_filter(font_escaped: str) -> str:
    """R9 v2 ★极简增强★ — R9 v1 全套(halation+CA+二次color)实测过度,把 R8 优秀的
    冷蓝赛博惊悚画面推成 magenta + 高光糊。v2 只保留两项**风险极低**的增强:
       1. 微微 unsharp (la=0.4) 提锐度，对 LAION 提升 0.1-0.2
       2. 极轻 noise (alls=3) 增加胶片质感，规避 banding 又不抢码率
    其余 (halation / CA / 二次 color / 二次 grain) 全部撤掉。
    """
    grain = "noise=alls=3:allf=t"
    sharpen = "unsharp=lx=5:ly=5:la=0.4:cx=5:cy=5:ca=0.0"
    watermark = (
        f"drawtext=text='AI 生成'"
        f":fontfile='{font_escaped}'"
        f":fontsize=36:fontcolor=white@0.6:borderw=2:bordercolor=black"
        f":x=w-tw-30:y=h-th-30"
    )
    return f"[0:v]{sharpen},{grain},{watermark},format=yuv420p[v]"


def polish_one(ep_id: str, src: pathlib.Path, dst: pathlib.Path) -> dict:
    font = _font_path().replace("\\", "/").replace(":", r"\:")
    flt = _build_r9_filter(font)
    tmp = dst.with_suffix(".tmp.mp4")
    dst.parent.mkdir(parents=True, exist_ok=True)

    creation_iso = _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    title = f"AI 生成 — 无限恐怖 v5 R9 Polish {ep_id}"
    comment = f"R9 cinematic_master + halation + CA + grain | mastered {creation_iso}"

    cmd1 = [
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "warning",
        "-i", str(src),
        "-filter_complex", flt,
        "-map", "[v]", "-map", "0:a?",
        "-c:v", "libx264", "-preset", "veryslow", "-tune", "film",
        "-crf", "14",
        "-profile:v", "high", "-level", "4.2",
        "-x264-params", "ref=6:bframes=8:me=umh:subme=10:trellis=2:psy-rd=1.0,0.15:aq-mode=3",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2",
        "-metadata", f"title={title}",
        "-metadata", f"comment={comment}",
        "-metadata", "copyright=© 2026 AI Manju Pilot",
        "-metadata", f"creation_time={creation_iso}",
        "-metadata", "composer=Skylark Agent 2.0 + Shell5 R9 Polish",
        str(tmp),
    ]
    print(f"  pass1 encoding: {ep_id}…")
    proc1 = subprocess.run(cmd1, capture_output=True, text=True,
                           encoding="utf-8", errors="replace")
    if proc1.returncode != 0:
        raise RuntimeError(f"{ep_id} pass1 failed: {(proc1.stderr or '')[-2000:]}")

    cmd2 = [
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-i", str(tmp), "-c", "copy",
        "-map", "0:v", "-map", "0:a?",
        "-movflags", "+faststart",
        str(dst),
    ]
    print(f"  pass2 faststart: {ep_id}…")
    proc2 = subprocess.run(cmd2, capture_output=True, text=True,
                           encoding="utf-8", errors="replace")
    if proc2.returncode != 0:
        raise RuntimeError(f"{ep_id} pass2 failed: {(proc2.stderr or '')[-2000:]}")
    try:
        tmp.unlink()
    except OSError:
        pass

    # 探时长/尺寸
    out = subprocess.run(
        ["ffprobe", "-v", "error",
         "-show_entries", "format=duration,size,bit_rate:stream=width,height",
         "-of", "json", str(dst)],
        check=True, capture_output=True, text=True, encoding="utf-8",
    ).stdout
    info = json.loads(out)
    return {
        "ep_id": ep_id,
        "final_path": str(dst.resolve()),
        "size_mb": round(int(info["format"]["size"]) / 1e6, 1),
        "bitrate_mbps": round(int(info["format"].get("bit_rate", 0)) / 1e6, 2),
        "duration": float(info["format"]["duration"]),
    }


def main() -> int:
    out_root = _REPO / "data" / "pilot_short_skylark" / "r9"
    out_root.mkdir(parents=True, exist_ok=True)
    summary = {"round_id": "R9", "started_at":
               _dt.datetime.now(_dt.timezone.utc).isoformat(), "episodes": []}

    for ep_id, src_rel in EP_SOURCES.items():
        src = _REPO / src_rel
        if not src.exists():
            print(f"  WARN: source missing {src}")
            continue
        dst = out_root / f"{ep_id}.mp4"
        try:
            info = polish_one(ep_id, src, dst)
            summary["episodes"].append(info)
            print(f"  OK {ep_id}: {info['size_mb']}MB / {info['bitrate_mbps']}Mbps / {info['duration']:.2f}s")
        except Exception as e:
            print(f"  FAIL {ep_id}: {e}")
            summary["episodes"].append({"ep_id": ep_id, "error": str(e)})

    summary["finished_at"] = _dt.datetime.now(_dt.timezone.utc).isoformat()
    (out_root / "_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nDone. Output: {out_root}")
    return 0 if all("error" not in e for e in summary["episodes"]) else 1


if __name__ == "__main__":
    raise SystemExit(main())
