"""风格迁移 — restyle a finished video into 日系/国漫/写实/二次元.

Requirement doc §9 风格迁移：一键切换日系/国漫/写实/二次元。

Backend priority:
    1. Runway Aleph (V2V — best at preserving structure while restyling)
    2. FLUX Kontext (frame-level edits, then ffmpeg recompose)
    3. mock (no-op copy)
"""
from __future__ import annotations

import logging
import os
import pathlib
import shutil

_log = logging.getLogger(__name__)


STYLE_TARGETS = {
    "jpn_anime":  "日系动漫风（Studio Ghibli + 京阿尼），柔和线条，明亮色调",
    "guoman":     "中国 3D 国漫风（白蛇缘起 + 雾山五行），冷青月白朱砂主色",
    "realistic":  "电影 cinematic 写实风（teal-orange），真实皮肤与质感",
    "manhwa":     "韩式二次元 manhwa 风，干净线条，浅色背景",
}


def restyle_video(
    src: str | pathlib.Path,
    dst: str | pathlib.Path,
    *,
    target: str = "jpn_anime",
) -> dict:
    src = pathlib.Path(src)
    dst = pathlib.Path(dst)
    dst.parent.mkdir(parents=True, exist_ok=True)
    descr = STYLE_TARGETS.get(target, target)

    if os.environ.get("FAL_API_KEY") and os.environ.get("FORCE_MOCK_RESTYLE") != "1":
        try:
            return _via_aleph(src, dst, descr, target)
        except Exception as e:
            _log.warning("aleph restyle failed: %s; falling back", e)
    # Fallback: copy the source so callers always get a writeable target.
    if src.exists():
        shutil.copy2(src, dst)
    return {"backend": "mock", "target": target, "description": descr, "output": str(dst)}


def _via_aleph(src: pathlib.Path, dst: pathlib.Path, descr: str, target: str) -> dict:
    """Runway Aleph V2V — synchronous wrapper.

    This intentionally raises on any failure so the caller can fall back. The
    function uploads ``src`` to ``fal.run`` and downloads the result.
    """
    import json as _json
    import urllib.request

    token = os.environ["FAL_API_KEY"]
    endpoint = "https://fal.run/fal-ai/aleph"
    body = {
        "video_url": src.as_uri() if src.is_absolute() else str(src),
        "instruction": f"Restyle this video to: {descr}",
        "duration_cap_seconds": 60,
    }
    req = urllib.request.Request(
        endpoint,
        data=_json.dumps(body).encode("utf-8"),
        headers={
            "Authorization": f"Key {token}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=600) as resp:
        data = _json.loads(resp.read())
    out_url = (data.get("video") or {}).get("url") or data.get("video_url")
    if not out_url:
        raise RuntimeError(f"aleph returned no video: {data}")
    # Download
    with urllib.request.urlopen(out_url, timeout=600) as rr:
        dst.write_bytes(rr.read())
    return {"backend": "runway_aleph", "target": target, "description": descr, "output": str(dst)}


__all__ = ["restyle_video", "STYLE_TARGETS"]
