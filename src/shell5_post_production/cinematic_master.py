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
    """母带配置。默认 ancient_v1（古风冷青+月白+朱砂）匹配 production.yaml 项目标准。

    工厂函数 `cyberpunk_v1_config()` 切换到无限恐怖现代赛博惊悚 Teal-Orange 调色，
    用于 novel-无限恐怖.md 类的现代生化危机/都市黑色科幻题材。
    """

    profile_name: str = "ancient_v1"       # 标识用，落入 manifest 便于回溯
    target_width: int = 1080
    target_height: int = 1920
    target_fps: int = 24
    duration_cap_seconds: float = 60.0     # 截前 60s（Skylark `40~60s` 档口，电影级叙事档）
    crf: int = 15                          # 母带级（参考片 18，发布母带 15）
    preset: str = "veryslow"
    tune: str = "film"
    audio_bitrate: str = "192k"
    watermark_text: str = "AI 生成"
    watermark_fontsize: int = 36
    watermark_opacity: float = 0.60
    watermark_border_px: int = 2
    watermark_margin_px: int = 30
    # 古风冷青 + 月白 + 朱砂 三级调色参数（ancient_v1 默认）
    eq_contrast: float = 1.10
    eq_saturation: float = 1.18
    eq_gamma_r: float = 0.95
    eq_gamma_g: float = 1.00
    eq_gamma_b: float = 1.05
    cb_rs: float = -0.05   # 红 shadow（朱砂痣别被洗掉）
    cb_gs: float = 0.02
    cb_bs: float = 0.08    # 蓝 shadow（月夜冷青）
    cb_bm: float = 0.03
    # RGB 曲线：red & blue（curves filter）默认古风冷调
    curves_red: str = "0/0 0.5/0.42 1/1"
    curves_blue: str = "0/0.05 0.5/0.58 1/1"
    # 降噪 + 锐化
    hqdn3d: str = "4:3:6:4.5"
    unsharp: str = "5:5:0.8:5:5:0.0"


def cyberpunk_v1_config(**overrides) -> "MasterConfig":
    """无限恐怖现代赛博惊悚 Teal-Orange 调色 profile.

    电影级 cinematic teal-orange 配方（Blade Runner 2049 / Mr. Robot 风格）：
    - shadow 偏深青蓝（teal）→ 高对比阴影
    - highlight 偏暖橘红（orange）→ 角色皮肤/灯光暖光
    - mid-tone 维持平衡但稍提对比
    - 曲线：红高光提升 / 蓝阴影提升 → 经典 teal-orange 撞色
    - 降噪略减弱（写实/胶片颗粒不必抹平）
    - 锐化略增强（突出金属/疤痕/枪械细节）
    """

    base = dict(
        profile_name="cyberpunk_v1",
        eq_contrast=1.18,           # 明暗对比拉强
        eq_saturation=1.12,         # 饱和度稍降，写实电影感
        eq_gamma_r=1.02,            # 红 gamma 略亮（暖肤色）
        eq_gamma_g=0.97,            # 绿 gamma 略压（避免泛绿）
        eq_gamma_b=0.95,            # 蓝 gamma 压低（深蓝阴影）
        cb_rs=-0.10,                # shadow 红 -0.10（深青）
        cb_gs=0.04,                 # shadow 绿 +0.04（teal）
        cb_bs=0.10,                 # shadow 蓝 +0.10（teal）
        cb_bm=0.00,                 # mid 蓝 中性
        # 曲线：红高光 +0.08 / 蓝阴影 +0.10（经典 cinematic teal-orange）
        curves_red="0/0 0.25/0.22 0.6/0.68 1/1",
        curves_blue="0/0.10 0.4/0.50 0.75/0.72 1/1",
        hqdn3d="3:2:4:3",            # 弱化降噪保留胶片颗粒
        unsharp="5:5:1.0:5:5:0.0",   # 锐化提升（金属/疤痕/枪械细节）
    )
    base.update(overrides)
    return MasterConfig(**base)


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

    # ★ 两遍 ffmpeg：先编码 → 再 remux faststart。一次性走 `-movflags +faststart`
    # 在 filter_complex + audio 映射 + `-t` 截断的组合下，ffmpeg 8.x 会写入两个 moov atom
    # （第一个老的 + 第二个 faststart 重排后的），让播放器选错索引→ NAL 解码失败。
    # 拆成两步可彻底避开这个 bug：
    #   pass1: 全套滤镜 + 编码 → tmp.mp4 (moov 在文件尾，标准 mp4 结构)
    #   pass2: -c copy +faststart → final.mp4 (单一 moov 移到文件头)
    tmp_path = dst_path.with_suffix(".tmp.mp4")
    pass1_cmd = _build_ffmpeg_cmd_pass1(
        raw_path, tmp_path, filter_complex, cfg,
        ep_id=ep_id, task_id=task_id, creation_iso=creation_iso,
    )
    pass2_cmd = _build_ffmpeg_cmd_pass2_faststart(tmp_path, dst_path)
    _log.info("[%s] master pass1 (encode): %s", ep_id, " ".join(pass1_cmd))

    t0 = _dt.datetime.now()
    proc1 = subprocess.run(pass1_cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if proc1.returncode != 0:
        tail = (proc1.stderr or "")[-3000:]
        raise MasterError(
            f"[{ep_id}] ffmpeg master pass1 exit={proc1.returncode}; stderr tail:\n{tail}"
        )

    _log.info("[%s] master pass2 (faststart remux): %s", ep_id, " ".join(pass2_cmd))
    proc2 = subprocess.run(pass2_cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    wallclock = (_dt.datetime.now() - t0).total_seconds()
    if proc2.returncode != 0:
        tail = (proc2.stderr or "")[-3000:]
        raise MasterError(
            f"[{ep_id}] ffmpeg master pass2 (faststart) exit={proc2.returncode}; stderr tail:\n{tail}"
        )

    # 清理临时文件
    try:
        tmp_path.unlink()
    except OSError:
        pass

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
        # 3c. 显式 RGB 曲线（可配置）：ancient_v1 默认古风冷调；cyberpunk_v1 切换 teal-orange
        f"curves=red='{cfg.curves_red}':blue='{cfg.curves_blue}'",
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


def _build_ffmpeg_cmd_pass1(
    raw_path: pathlib.Path,
    tmp_path: pathlib.Path,
    filter_complex: str,
    cfg: MasterConfig,
    *,
    ep_id: str,
    task_id: str,
    creation_iso: str,
) -> list[str]:
    """Pass 1: 编码 + 全部滤镜，输出到 tmp.mp4（moov 在文件尾，标准 mp4）。

    注意：故意 **不带** `-movflags +faststart` —— 它和 filter_complex+audio+`-t`
    的组合会在 ffmpeg 8.x 上写出重复 moov atom（已实证），导致解码失败。
    """

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
        "-map", "0:a?",
        "-t", f"{cfg.duration_cap_seconds:.2f}",
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
        "-metadata", f"title={title}",
        "-metadata", f"comment={comment}",
        "-metadata", "copyright=© 2026 AI Manju Pilot",
        "-metadata", f"creation_time={creation_iso}",
        "-metadata", "composer=Skylark Agent 2.0 + Shell5 Cinematic Master",
        str(tmp_path),
    ]


def _build_ffmpeg_cmd_pass2_faststart(
    tmp_path: pathlib.Path,
    dst_path: pathlib.Path,
) -> list[str]:
    """Pass 2: 仅 remux (`-c copy`) + faststart，把唯一的 moov atom 移到文件头。

    `-c copy` 不重新编码，几秒内完成。重排后的 mp4 流媒体首帧立刻可播。
    """

    return [
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "info",
        "-i", str(tmp_path),
        "-c", "copy",
        "-map", "0:v",
        "-map", "0:a?",
        "-movflags", "+faststart",
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
