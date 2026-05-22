"""Platform-specific export adapters.

Requirement doc §8 运营商用:
    流量适配：适配抖音、快手、视频号、小红书、B 站、YouTube Shorts 等格式

Each adapter takes one master mp4 and produces a re-encoded copy with the
platform's preferred aspect ratio, bitrate ceiling, and (optionally) an
account watermark + AIGC label. Caption + hashtag suggestions are bundled.
"""
from __future__ import annotations

import logging
import pathlib
import shutil
import subprocess
from dataclasses import dataclass
from typing import Any

_log = logging.getLogger(__name__)


@dataclass
class PlatformSpec:
    id: str
    name_zh: str
    aspect: str
    width: int
    height: int
    fps: int
    video_bitrate: str
    audio_bitrate: str
    max_duration_s: int | None = None
    container: str = "mp4"
    caption_template: str = "{title} — AI 漫剧 · {genre}"
    hashtag_seed: tuple[str, ...] = ("AI漫剧", "短剧推荐")


PLATFORM_SPECS: dict[str, PlatformSpec] = {
    "douyin": PlatformSpec(
        id="douyin",
        name_zh="抖音",
        aspect="9:16",
        width=1080,
        height=1920,
        fps=30,
        video_bitrate="6M",
        audio_bitrate="192k",
        max_duration_s=600,
        caption_template="{title}｜AI 漫剧 · {genre}（戳头像看更多）",
        hashtag_seed=("AI漫剧", "短剧推荐", "古风漫剧"),
    ),
    "kuaishou": PlatformSpec(
        id="kuaishou",
        name_zh="快手",
        aspect="9:16",
        width=1080,
        height=1920,
        fps=30,
        video_bitrate="6M",
        audio_bitrate="192k",
        max_duration_s=900,
        caption_template="🎬 {title}｜AI 漫剧 · {genre}",
        hashtag_seed=("AI漫剧", "古风", "国漫"),
    ),
    "wechat_video": PlatformSpec(
        id="wechat_video",
        name_zh="视频号",
        aspect="9:16",
        width=1080,
        height=1920,
        fps=24,
        video_bitrate="5M",
        audio_bitrate="160k",
        max_duration_s=60 * 30,
        caption_template="《{title}》AI 漫剧 第 {episode} 集",
        hashtag_seed=("AI漫剧", "国漫"),
    ),
    "xiaohongshu": PlatformSpec(
        id="xiaohongshu",
        name_zh="小红书",
        aspect="3:4",
        width=1080,
        height=1440,
        fps=30,
        video_bitrate="5M",
        audio_bitrate="160k",
        max_duration_s=300,
        caption_template="《{title}》｜被宠到上头的 AI 漫剧 · {genre}",
        hashtag_seed=("AI漫剧", "漫剧推荐", "甜宠"),
    ),
    "bilibili": PlatformSpec(
        id="bilibili",
        name_zh="B站",
        aspect="16:9",
        width=1920,
        height=1080,
        fps=30,
        video_bitrate="8M",
        audio_bitrate="192k",
        max_duration_s=60 * 60,
        caption_template="【AI 国漫】《{title}》第 {episode} 集 · {genre}",
        hashtag_seed=("AI国漫", "国漫", "漫剧"),
    ),
    "youtube_shorts": PlatformSpec(
        id="youtube_shorts",
        name_zh="YouTube Shorts",
        aspect="9:16",
        width=1080,
        height=1920,
        fps=30,
        video_bitrate="8M",
        audio_bitrate="192k",
        max_duration_s=60,
        caption_template="AI animated drama · {title} (Episode {episode})",
        hashtag_seed=("AIanime", "shortdrama", "AIstory"),
    ),
}


def export_for_platforms(
    src: str | pathlib.Path,
    out_root: str | pathlib.Path,
    *,
    platforms: list[str],
    add_watermark: bool = True,
    account_handle: str | None = None,
    title: str = "AI 漫剧",
    episode: int | str = 1,
    genre: str = "ancient",
) -> dict[str, dict[str, Any]]:
    """Transcode ``src`` once per platform into ``out_root/<platform>.mp4``.

    Returns a mapping ``{platform_id: {path, width, height, duration_s, caption, hashtags}}``.
    Best-effort: if ffmpeg is missing we copy the source as-is so the SaaS UX
    never blocks on a tooling problem.
    """
    src = pathlib.Path(src)
    out_root = pathlib.Path(out_root)
    out_root.mkdir(parents=True, exist_ok=True)
    out: dict[str, dict[str, Any]] = {}

    have_ffmpeg = shutil.which("ffmpeg") is not None

    for pid in platforms:
        spec = PLATFORM_SPECS.get(pid)
        if spec is None:
            continue
        target = out_root / f"{spec.id}.mp4"
        info: dict[str, Any] = {"path": str(target)}
        if have_ffmpeg and src.exists():
            try:
                _transcode(
                    src,
                    target,
                    spec=spec,
                    add_watermark=add_watermark,
                    account_handle=account_handle,
                )
                info["width"] = spec.width
                info["height"] = spec.height
            except Exception as e:
                _log.warning("transcode %s failed: %s", spec.id, e)
                shutil.copy2(src, target)
        else:
            if src.exists() and src.resolve() != target.resolve():
                shutil.copy2(src, target)
            info["width"] = spec.width
            info["height"] = spec.height

        caption = spec.caption_template.format(title=title, episode=episode, genre=genre)
        hashtags = [f"#{tag}" for tag in spec.hashtag_seed]
        info.update(
            {
                "caption": caption,
                "hashtags": hashtags,
                "duration_s": None,  # ffprobe optional
                "aspect": spec.aspect,
            }
        )
        out[spec.id] = info
    return out


# ---------------------------------------------------------------------------


def _transcode(
    src: pathlib.Path,
    dst: pathlib.Path,
    *,
    spec: PlatformSpec,
    add_watermark: bool,
    account_handle: str | None,
) -> None:
    filter_chain = [
        f"scale={spec.width}:{spec.height}:force_original_aspect_ratio=decrease",
        f"pad={spec.width}:{spec.height}:(ow-iw)/2:(oh-ih)/2:color=black",
        f"fps={spec.fps}",
    ]
    if add_watermark:
        font = _detect_font()
        if font:
            wm = "AI 生成"
            if account_handle:
                wm += f" · @{account_handle}"
            wm = wm.replace(":", r"\:")
            font_escaped = font.replace("\\", "/").replace(":", r"\:")
            filter_chain.append(
                (
                    f"drawtext=text='{wm}'"
                    f":fontfile='{font_escaped}'"
                    ":fontsize=28"
                    ":fontcolor=white@0.6"
                    ":borderw=2:bordercolor=black"
                    ":x=w-tw-30:y=h-th-30"
                )
            )

    vf = ",".join(filter_chain)
    cmd = [
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-i", str(src),
        "-vf", vf,
        "-c:v", "libx264", "-preset", "fast", "-crf", "20",
        "-b:v", spec.video_bitrate,
        "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", spec.audio_bitrate,
        "-movflags", "+faststart",
    ]
    if spec.max_duration_s:
        cmd.extend(["-t", str(spec.max_duration_s)])
    cmd.append(str(dst))
    subprocess.run(cmd, check=True, capture_output=True)


def _detect_font() -> str | None:
    candidates = [
        "C:/Windows/Fonts/msyhbd.ttc",
        "C:/Windows/Fonts/simhei.ttf",
        "/usr/share/fonts/opentype/source-han-sans/SourceHanSansSC-Bold.otf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/System/Library/Fonts/PingFang.ttc",
    ]
    for p in candidates:
        if pathlib.Path(p).exists():
            return p
    return None


__all__ = ["export_for_platforms", "PlatformSpec", "PLATFORM_SPECS"]
