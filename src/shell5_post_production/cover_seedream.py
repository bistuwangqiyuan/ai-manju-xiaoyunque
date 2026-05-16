"""Episode cover poster — Seedream 4.0 (Chinese) + Pillow text layer."""
from __future__ import annotations

import io
import logging
import pathlib

import urllib.request

from ..shell2_character_assets.gen_seedream import SeedreamClient, SeedreamRequest


_log = logging.getLogger(__name__)


def build_cover(
    title_zh: str,
    subtitle_zh: str,
    episode_no: int,
    output_path: str | pathlib.Path,
    *,
    seedream: SeedreamClient | None = None,
    base_image_url: str | None = None,
) -> str:
    """Generate a Seedream 4.0 base poster then burn title text via Pillow."""

    if base_image_url is None:
        if seedream is None:
            seedream = SeedreamClient(req_key="jimeng_t2i_v40")
        prompt = (
            f"漫剧《聊斋·聂小倩》第{episode_no}集《{title_zh}》竖屏 9:16 海报；"
            "古风3D国漫风，60% 白蛇缘起 + 30% 狐妖月红 + 10% 雾山五行；"
            "中央留出竖向标题区，下方留出副标题带；色调冷青+暖橘对比"
        )
        urls = seedream.generate(SeedreamRequest(
            prompt=prompt, num_images=1, aspect_ratio="9:16", deep_thinking=True,
        ))
        if not urls:
            raise RuntimeError("Seedream returned no images for cover")
        base_image_url = urls[0]

    base_bytes = _fetch(base_image_url)
    final = _render_text_layer(base_bytes, title_zh, subtitle_zh, episode_no)
    out = pathlib.Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(final)
    return str(out)


# ---------------------------------------------------------------------------

def _fetch(url: str) -> bytes:
    with urllib.request.urlopen(url, timeout=60) as resp:
        return resp.read()


def _render_text_layer(image_bytes: bytes, title: str, subtitle: str, episode_no: int) -> bytes:
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError as e:  # pragma: no cover
        raise RuntimeError("Install pillow: pip install pillow") from e

    img = Image.open(io.BytesIO(image_bytes)).convert("RGBA")
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    title_font = _try_font(["思源宋体 CN Bold", "Source Han Serif CN Bold", "simsun.ttc"], 120)
    subtitle_font = _try_font(["思源黑体 CN", "Source Han Sans CN", "msyh.ttc"], 56)
    label_font = _try_font(["思源黑体 CN Bold", "Source Han Sans CN Bold", "msyh.ttc"], 48)

    w, h = img.size
    cx = w // 2

    # Episode badge top-right
    badge = f"第 {episode_no:02d} 集"
    draw.text((w - 60, 80), badge, fill=(255, 220, 130, 255),
              font=label_font, anchor="rt", stroke_width=3, stroke_fill=(0, 0, 0, 220))

    # Title center
    draw.text((cx, h * 0.62), title, fill=(255, 255, 255, 255),
              font=title_font, anchor="mm", stroke_width=4, stroke_fill=(0, 0, 0, 230))

    # Subtitle below
    draw.text((cx, h * 0.72), subtitle, fill=(232, 217, 176, 255),
              font=subtitle_font, anchor="mm", stroke_width=2, stroke_fill=(0, 0, 0, 200))

    # AI-generated label bottom-left (合规)
    draw.text((40, h - 80), "AI 生成", fill=(220, 220, 220, 200),
              font=label_font, anchor="lb", stroke_width=2, stroke_fill=(0, 0, 0, 200))

    out = Image.alpha_composite(img, overlay).convert("RGB")
    buf = io.BytesIO()
    out.save(buf, format="JPEG", quality=94)
    return buf.getvalue()


def _try_font(candidates, size):
    from PIL import ImageFont
    for name in candidates:
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()
