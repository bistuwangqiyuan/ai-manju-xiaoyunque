"""mp4 box 解析 + ROI 亮度采样 + ffprobe 包装。

为母带质检测试服务：
- `parse_top_level_boxes(path)` 返回 mp4 顶层 box 顺序 + 偏移（用于 faststart 检测）
- `is_faststart(path)` 判断 `moov` 是否在 `mdat` 之前（流媒体首帧立刻可播）
- `sample_roi_y_brightness(video_path, t_sec, roi)` 用 ffmpeg 抽一帧后计算 ROI 灰度均值
- `ffprobe_streams_format(path)` 一次取齐 streams + format 的常用字段
"""
from __future__ import annotations

import io
import json
import pathlib
import struct
import subprocess
from typing import Any


def parse_top_level_boxes(path: str | pathlib.Path) -> list[tuple[str, int, int]]:
    """读 mp4 顶层 boxes，返回 [(type, offset, size), ...]。

    只解析顶层（不递归），用来判断 moov vs mdat 的相对顺序。
    """

    path = pathlib.Path(path)
    boxes: list[tuple[str, int, int]] = []
    with open(path, "rb") as f:
        f.seek(0, io.SEEK_END)
        end = f.tell()
        f.seek(0)
        offset = 0
        while offset < end:
            f.seek(offset)
            header = f.read(8)
            if len(header) < 8:
                break
            size = struct.unpack(">I", header[:4])[0]
            box_type = header[4:8].decode("ascii", errors="replace")
            if size == 1:
                ext = f.read(8)
                if len(ext) < 8:
                    break
                size = struct.unpack(">Q", ext)[0]
            elif size == 0:
                size = end - offset
            if size < 8:
                break
            boxes.append((box_type, offset, size))
            offset += size
    return boxes


def is_faststart(path: str | pathlib.Path) -> bool:
    """faststart 即 moov 出现在 mdat 之前。

    标准 mp4 默认把 moov 写在文件尾（编码器边写边算 sample tables），
    `-movflags +faststart` 让 ffmpeg 写完后把 moov 移到头部，浏览器/手机
    播放器拿到第一个 chunk 就能开始播。
    """

    moov_off = None
    mdat_off = None
    for box_type, off, _size in parse_top_level_boxes(path):
        if box_type == "moov" and moov_off is None:
            moov_off = off
        elif box_type == "mdat" and mdat_off is None:
            mdat_off = off
        if moov_off is not None and mdat_off is not None:
            break
    if moov_off is None or mdat_off is None:
        return False
    return moov_off < mdat_off


def ffprobe_streams_format(path: str | pathlib.Path) -> dict[str, Any]:
    """一次取齐 streams + format。返回 json.load 后的 dict。"""

    cmd = [
        "ffprobe", "-v", "error",
        "-show_format", "-show_streams",
        "-of", "json",
        str(path),
    ]
    # ★ Windows zh-CN 必须显式 encoding="utf-8"：ffprobe `-of json` 永远输出 UTF-8，
    # 但 subprocess.run(text=True) 默认用系统 locale（cp936/GBK），遇到 UTF-8 中
    # 多字节字符（如 © 0xa9 / 中文）会触发 UnicodeDecodeError。errors="replace"
    # 兜底任何意外字节，防止 stdout 变 None 导致 json.loads(None) 报 TypeError。
    proc = subprocess.run(
        cmd, check=True, capture_output=True,
        text=True, encoding="utf-8", errors="replace",
    )
    return json.loads(proc.stdout)


def sample_roi_y_brightness(
    video_path: str | pathlib.Path,
    *,
    t_sec: float,
    roi: tuple[int, int, int, int],
) -> tuple[float, float]:
    """[兼容入口] 抽帧后返回 (roi 灰度均值, 整帧灰度均值)。

    保留以避免破坏旧调用方。新代码建议用 `sample_roi_stats` 以拿到 p99/max
    等高位分位，这对检测"小面积高对比白色水印"远比均值稳健。
    """

    stats = sample_roi_stats(video_path, t_sec=t_sec, roi=roi)
    return stats["roi_mean"], stats["full_mean"]


def sample_roi_stats(
    video_path: str | pathlib.Path,
    *,
    t_sec: float,
    roi: tuple[int, int, int, int],
) -> dict[str, float]:
    """抽一帧后对 ROI 与整帧分别返回 min/max/mean/p99 灰度统计。

    用于水印检测：白色"AI 生成"水印只占 ROI 的一小块，整体均值会被深色背景拉低；
    判断更可靠的口径是 `roi_p99`（ROI 像素亮度的第 99 百分位）—— 即使水印只覆盖
    ROI 1% 的像素，这 1% 的最亮像素就是水印本身，p99 会显著高于背景。
    """

    from PIL import Image  # 局部导入以避免 import-time 失败

    cmd = [
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-ss", f"{t_sec:.3f}",
        "-i", str(video_path),
        "-frames:v", "1",
        "-f", "image2pipe",
        "-pix_fmt", "gray",
        "-vcodec", "png",
        "pipe:1",
    ]
    proc = subprocess.run(cmd, check=True, capture_output=True)
    img = Image.open(io.BytesIO(proc.stdout)).convert("L")
    w, h = img.size
    x0, y0, x1, y1 = roi
    x0 = max(0, min(w, x0))
    x1 = max(0, min(w, x1))
    y0 = max(0, min(h, y0))
    y1 = max(0, min(h, y1))
    if x1 <= x0 or y1 <= y0:
        raise ValueError(f"invalid ROI {roi} for frame {w}x{h}")
    roi_pixels = list(img.crop((x0, y0, x1, y1)).getdata())
    full_pixels = list(img.getdata())
    return {
        "roi_min": float(min(roi_pixels)),
        "roi_max": float(max(roi_pixels)),
        "roi_mean": float(sum(roi_pixels) / len(roi_pixels)),
        "roi_p99": float(_percentile(roi_pixels, 99)),
        "full_min": float(min(full_pixels)),
        "full_max": float(max(full_pixels)),
        "full_mean": float(sum(full_pixels) / len(full_pixels)),
        "full_p99": float(_percentile(full_pixels, 99)),
    }


def _percentile(values: list[int], p: float) -> float:
    """简单 numpy-free 百分位（按升序取下标）。"""

    n = len(values)
    if n == 0:
        return 0.0
    s = sorted(values)
    k = int(round((p / 100.0) * (n - 1)))
    return float(s[k])
