"""Account + AIGC explicit watermark (requirement doc §8 / §合规)."""
from __future__ import annotations

import logging
import pathlib
import shutil
import subprocess

_log = logging.getLogger(__name__)


def apply_watermark(
    src: str | pathlib.Path,
    dst: str | pathlib.Path,
    *,
    account_handle: str | None = None,
    aigc_label: str = "AI 生成",
    position: str = "bottom_right",
) -> str:
    """Overlay text watermark (account + AIGC) on a single video.

    Falls back to copy if ffmpeg/font is unavailable so the pipeline never
    breaks on a tooling problem.
    """
    src = pathlib.Path(src)
    dst = pathlib.Path(dst)
    dst.parent.mkdir(parents=True, exist_ok=True)

    if not src.exists():
        raise FileNotFoundError(src)

    if shutil.which("ffmpeg") is None:
        shutil.copy2(src, dst)
        return str(dst)

    font = _detect_font()
    if font is None:
        shutil.copy2(src, dst)
        return str(dst)

    pos_map = {
        "bottom_right": "x=w-tw-30:y=h-th-30",
        "bottom_left":  "x=30:y=h-th-30",
        "top_right":    "x=w-tw-30:y=30",
        "top_left":     "x=30:y=30",
    }
    coords = pos_map.get(position, pos_map["bottom_right"])

    text = aigc_label
    if account_handle:
        text = f"@{account_handle.lstrip('@')} · {aigc_label}"
    text = text.replace(":", r"\:")
    font_escaped = font.replace("\\", "/").replace(":", r"\:")
    vf = (
        f"drawtext=text='{text}'"
        f":fontfile='{font_escaped}'"
        ":fontsize=30"
        ":fontcolor=white@0.65"
        ":borderw=2:bordercolor=black"
        f":{coords}"
    )
    cmd = [
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-i", str(src),
        "-vf", vf,
        "-c:v", "libx264", "-preset", "fast", "-crf", "20",
        "-pix_fmt", "yuv420p",
        "-c:a", "copy",
        "-movflags", "+faststart",
        str(dst),
    ]
    try:
        subprocess.run(cmd, check=True, capture_output=True)
    except Exception as e:
        _log.warning("watermark ffmpeg failed: %s", e)
        shutil.copy2(src, dst)
    return str(dst)


def _detect_font() -> str | None:
    for p in (
        "C:/Windows/Fonts/msyhbd.ttc",
        "C:/Windows/Fonts/simhei.ttf",
        "/usr/share/fonts/opentype/source-han-sans/SourceHanSansSC-Bold.otf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/System/Library/Fonts/PingFang.ttc",
    ):
        if pathlib.Path(p).exists():
            return p
    return None


__all__ = ["apply_watermark"]
