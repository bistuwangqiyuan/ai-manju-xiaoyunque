"""电影级母带管线 — 单次 ffmpeg filter_complex，720→1080 上采 + 色彩分级 + 合规水印。

设计原则:
- **一次解码、一次编码**：所有滤镜串入同一个 filter_complex 链，避免多次重编损失。
- **参考级缩放**：zscale=spline36 是 zimg 的最佳 CPU 缩放器（与 madVR/foobar2000 同核），
  优于 ffmpeg scale=lanczos。如系统支持 libplacebo + Vulkan，调用方可显式开启。
- **古风冷青调色**：三级（eq → colorbalance → curves=cool）匹配《白蛇缘起》60% +
  《狐妖月红仙气》30% + 《雾山五行》10% 的项目色彩配方 (config/production.yaml:17)。
- **AIGC 合规水印**：drawtext 自渲染白色 60% + 黑描边 2px 右下角"AI 生成"，
  匹配 compliance/aigc_label_checklist.md:14-24 的国标要求。
- **fps=24 标准化**：从 Skylark 默认 30fps 抽帧到项目标准 24fps；用 `fps` 滤镜直接抽，
  不用 minterpolate（运动补偿插帧反而引入伪影）。
- **libx264 母带级编码**：crf=15 preset=veryslow tune=film + 高级 x264-params 调优
  （高 ref、psy-rd、aq-mode=3）+ +faststart，输出可对外发布的高端母带 mp4。
"""
from __future__ import annotations

import datetime as _dt
import json
import logging
import pathlib
import shutil
import subprocess
from dataclasses import dataclass
from typing import Any

from .quality_metrics import ffprobe_streams_format, is_faststart

_log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 字体探测：用于 drawtext AIGC 水印
# ---------------------------------------------------------------------------

# Windows 常驻中文 Bold 字体候选；按合规清单优先级排序。
_FONT_CANDIDATES = (
    "C:/Windows/Fonts/SourceHanSansSC-Bold.otf",   # 思源黑体 CN Bold（首选；可能未装）
    "C:/Windows/Fonts/msyhbd.ttc",                 # 微软雅黑 Bold（必装）
    "C:/Windows/Fonts/simhei.ttf",                 # 黑体（必装，更老）
)


def select_chinese_bold_font() -> str:
    """探测系统上可用的中文 Bold 字体，返回绝对路径（POSIX 风格）。

    探测顺序：思源黑体 → 微软雅黑 Bold → SimHei。三者都查不到则抛错——
    drawtext 没有中文字体会出方框，必须 fail-fast 而非 ship 一个坏母带。
    """

    for path in _FONT_CANDIDATES:
        if pathlib.Path(path).exists():
            return path
    raise MasterError(
        f"no Chinese bold font found; tried {_FONT_CANDIDATES}. "
        "drawtext will render 豆腐块, refusing to ship a broken master."
    )


# ---------------------------------------------------------------------------
# 错误模型
# ---------------------------------------------------------------------------

class MasterError(RuntimeError):
    """母带管线失败（ffmpeg 退出非 0、字体探测失败、输出校验失败等）。"""


# ---------------------------------------------------------------------------
# 主入口
# ---------------------------------------------------------------------------

@dataclass
class MasterConfig:
    """母带配置。默认值匹配 production.yaml 的项目标准。"""

    target_width: int = 1080
    target_height: int = 1920
    target_fps: int = 24
    duration_cap_seconds: float = 15.0     # 截前 15s（Skylark `~15s` 档口）
    crf: int = 15                          # 母带级（参考片 18，发布母带 15）
    preset: str = "veryslow"
    tune: str = "film"
    audio_bitrate: str = "192k"
    watermark_text: str = "AI 生成"
    watermark_fontsize: int = 36
    watermark_opacity: float = 0.60
    watermark_border_px: int = 2
    watermark_margin_px: int = 30
    # 古风冷青 + 月白 + 朱砂 三级调色参数
    eq_contrast: float = 1.10
    eq_saturation: float = 1.18
    eq_gamma_r: float = 0.95
    eq_gamma_g: float = 1.00
    eq_gamma_b: float = 1.05
    cb_rs: float = -0.05   # 红 shadow（朱砂痣别被洗掉）
    cb_gs: float = 0.02
    cb_bs: float = 0.08    # 蓝 shadow（月夜冷青）
    cb_bm: float = 0.03
    # 降噪 + 锐化
    hqdn3d: str = "4:3:6:4.5"
    unsharp: str = "5:5:0.8:5:5:0.0"


def master(
    raw_path: str | pathlib.Path,
    dst_path: str | pathlib.Path,
    *,
    ep_id: str,
    task_id: str,
    config: MasterConfig | None = None,
) -> dict[str, Any]:
    """跑完整母带管线：raw mp4 → 1080×1920 24fps h264 crf=15 yuv420p faststart。

    返回 metrics dict（width / height / fps / codec / pix_fmt / bitrate / duration /
    size / faststart / wallclock_seconds），便于上游写入 manifest 持久化。
    """

    cfg = config or MasterConfig()
    raw_path = pathlib.Path(raw_path)
    dst_path = pathlib.Path(dst_path)
    if not raw_path.exists():
        raise MasterError(f"raw video missing: {raw_path}")
    if shutil.which("ffmpeg") is None:
        raise MasterError("ffmpeg not found on PATH; install ffmpeg ≥ 8.x")
    if shutil.which("ffprobe") is None:
        raise MasterError("ffprobe not found on PATH; install ffmpeg ≥ 8.x")

    dst_path.parent.mkdir(parents=True, exist_ok=True)
    font_path = select_chinese_bold_font()
    filter_complex = _build_filter_complex(cfg, font_path)
    creation_iso = _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    cmd = _build_ffmpeg_cmd(
        raw_path, dst_path, filter_complex, cfg,
        ep_id=ep_id, task_id=task_id, creation_iso=creation_iso,
    )
    _log.info("[%s] master ffmpeg cmd: %s", ep_id, " ".join(cmd))

    t0 = _dt.datetime.now()
    proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    wallclock = (_dt.datetime.now() - t0).total_seconds()
    if proc.returncode != 0:
        tail = (proc.stderr or "")[-3000:]
        raise MasterError(
            f"[{ep_id}] ffmpeg master exit={proc.returncode}; stderr tail:\n{tail}"
        )

    metrics = _collect_metrics(dst_path)
    metrics["wallclock_seconds"] = round(wallclock, 2)
    _log.info(
        "[%s] master done: %dx%d @ %s fps, %s codec, %.1f Mbps, %.2fs duration, %.1fs wallclock",
        ep_id, metrics["width"], metrics["height"], metrics["fps"],
        metrics["codec"], metrics["bitrate_mbps"], metrics["duration"], wallclock,
    )
    return metrics


# ---------------------------------------------------------------------------
# 内部 — filter_complex 构造
# ---------------------------------------------------------------------------

def _build_filter_complex(cfg: MasterConfig, font_path: str) -> str:
    """组装 9 步滤镜链。所有用到字符串拼接的特殊字符（如 `:` 和 `\\`）已显式转义。"""

    # ffmpeg filter_complex 用 `:` 作参数分隔，font 路径里的 `:` 必须 `\:` 转义。
    font_escaped = font_path.replace("\\", "/").replace(":", r"\:")

    parts = [
        # 1. 截前 15s（Skylark `~15s` 档口；有时返回 23.15s，安全裁掉）
        f"trim=start=0:end={cfg.duration_cap_seconds:.2f}",
        "setpts=PTS-STARTPTS",
        # 2. 三维空时降噪（hqdn3d 经典参数，温和保细节）
        f"hqdn3d={cfg.hqdn3d}",
        # 3a. brightness/contrast/saturation/gamma：朱砂红保留 + 蓝端微提
        (
            f"eq=contrast={cfg.eq_contrast}:saturation={cfg.eq_saturation}"
            f":gamma_r={cfg.eq_gamma_r}:gamma_g={cfg.eq_gamma_g}:gamma_b={cfg.eq_gamma_b}"
        ),
        # 3b. color balance：shadow 偏冷青、midtone 微蓝
        (
            f"colorbalance=rs={cfg.cb_rs}:gs={cfg.cb_gs}:bs={cfg.cb_bs}"
            f":rm=0:gm=0:bm={cfg.cb_bm}"
        ),
        # 3c. 显式 RGB 曲线：红 shadow 略压 + 蓝 shadow/midtone 略提（古风冷调）
        # ffmpeg curves 内置预设无 'cool'，手工写曲线 = 经典 cinematic teal/blue 谷
        "curves=red='0/0 0.5/0.42 1/1':blue='0/0.05 0.5/0.58 1/1'",
        # 4. zscale 1080×1920，spline36 + bt709 限范
        (
            f"zscale=w={cfg.target_width}:h={cfg.target_height}"
            ":filter=spline36:m=bt709:t=bt709:p=bt709:r=tv"
        ),
        # 5. unsharp 微锐
        f"unsharp={cfg.unsharp}",
        # 6. fps=24 抽帧标准化
        f"fps=fps={cfg.target_fps}",
        # 7. 合规 AIGC 水印：右下角 30px 边距
        (
            f"drawtext=text='{cfg.watermark_text}'"
            f":fontfile='{font_escaped}'"
            f":fontsize={cfg.watermark_fontsize}"
            f":fontcolor=white@{cfg.watermark_opacity}"
            f":borderw={cfg.watermark_border_px}:bordercolor=black"
            f":x=w-tw-{cfg.watermark_margin_px}:y=h-th-{cfg.watermark_margin_px}"
        ),
        # 8. 强制 yuv420p 输出（H.264 main/high profile 通用，所有播放器兼容）
        "format=yuv420p",
    ]
    return ",".join(parts)


def _build_ffmpeg_cmd(
    raw_path: pathlib.Path,
    dst_path: pathlib.Path,
    filter_complex: str,
    cfg: MasterConfig,
    *,
    ep_id: str,
    task_id: str,
    creation_iso: str,
) -> list[str]:
    """组装 ffmpeg 命令行参数列表（subprocess.run 直传，避免 shell 转义陷阱）。"""

    x264_params = (
        "ref=6:bframes=8:me=umh:subme=10:trellis=2:psy-rd=1.0,0.15:aq-mode=3"
    )
    title = f"AI 生成 — 聊斋·聂小倩 v5 Pilot {ep_id}"
    comment = (
        f"Skylark Agent 2.0 task_id={task_id} | "
        f"AIGC GB/T 45438-2025 | mastered {creation_iso}"
    )
    return [
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "info",
        "-i", str(raw_path),
        "-filter_complex", f"[0:v]{filter_complex}[v]",
        "-map", "[v]",
        "-map", "0:a?",   # 可选 audio passthrough（Skylark 输出含静音 AAC）
        "-t", f"{cfg.duration_cap_seconds:.2f}",   # ★ 全局硬截：video filter trim + audio 同步截
        "-c:v", "libx264",
        "-preset", cfg.preset,
        "-tune", cfg.tune,
        "-crf", str(cfg.crf),
        "-profile:v", "high",
        "-level", "4.2",
        "-x264-params", x264_params,
        "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        "-b:a", cfg.audio_bitrate,
        "-ar", "48000",
        "-ac", "2",
        "-movflags", "+faststart",
        "-metadata", f"title={title}",
        "-metadata", f"comment={comment}",
        "-metadata", "copyright=© 2026 AI Manju Pilot",
        "-metadata", f"creation_time={creation_iso}",
        "-metadata", f"composer=Skylark Agent 2.0 + Shell5 Cinematic Master",
        str(dst_path),
    ]


def _collect_metrics(dst_path: pathlib.Path) -> dict[str, Any]:
    """读 ffprobe + box parse，生成 manifest 友好的 metrics dict。"""

    info = ffprobe_streams_format(dst_path)
    fmt = info.get("format", {})
    vstreams = [s for s in info.get("streams", []) if s.get("codec_type") == "video"]
    if not vstreams:
        raise MasterError(f"master output {dst_path} has no video stream")
    v = vstreams[0]
    fps = _parse_rational(v.get("r_frame_rate") or v.get("avg_frame_rate") or "0/1")
    size = int(fmt.get("size", 0) or 0)
    duration = float(fmt.get("duration", 0) or 0)
    bit_rate = int(fmt.get("bit_rate", 0) or 0)
    return {
        "path": str(dst_path),
        "width": int(v.get("width", 0) or 0),
        "height": int(v.get("height", 0) or 0),
        "fps": round(fps, 3),
        "codec": v.get("codec_name", ""),
        "profile": v.get("profile", ""),
        "pix_fmt": v.get("pix_fmt", ""),
        "duration": round(duration, 3),
        "size_bytes": size,
        "bitrate_mbps": round(bit_rate / 1_000_000, 3),
        "faststart": is_faststart(dst_path),
        "tags": (fmt.get("tags") or {}),
    }


def _parse_rational(s: str) -> float:
    try:
        num, den = s.split("/")
        return float(num) / float(den) if float(den) else 0.0
    except Exception:  # noqa: BLE001
        return 0.0
