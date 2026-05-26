"""V10 §10.2 — Cover composer (image + title + watermark).

Generates a JPEG / PNG cover from:
    - a base poster image (the existing Seedream cover plate)
    - a title overlay (font, size, colour, stroke configurable)
    - an optional account watermark (lower-right by default)
    - an AIGC compliance label (lower-left, default ON)

Produces a *preview* dataclass (so a UI can show a layout overlay before
fully rendering) plus a final PNG.  All ratios are normalised to the
target output size so the layout works at any resolution.
"""
from __future__ import annotations

import logging
import pathlib
from dataclasses import dataclass, field
from typing import Any

_log = logging.getLogger(__name__)


@dataclass
class CoverLayout:
    title: str = "AI 漫剧"
    subtitle: str = ""
    title_color: str = "#FFFFFF"
    title_size_ratio: float = 0.085         # 8.5% of canvas height
    title_x_ratio: float = 0.06
    title_y_ratio: float = 0.78             # bottom-left area
    subtitle_size_ratio: float = 0.038
    title_stroke_color: str = "#000000"
    title_stroke_width: int = 3
    watermark_text: str = "AI 生成"
    watermark_x_ratio: float = 0.85
    watermark_y_ratio: float = 0.94
    watermark_size_ratio: float = 0.025
    aigc_label: str = "AI 生成 · GenAI"
    aigc_label_x_ratio: float = 0.05
    aigc_label_y_ratio: float = 0.94

    def to_dict(self) -> dict[str, Any]:
        return {
            k: getattr(self, k) for k in [
                "title", "subtitle", "title_color", "title_size_ratio",
                "title_x_ratio", "title_y_ratio", "subtitle_size_ratio",
                "title_stroke_color", "title_stroke_width",
                "watermark_text", "watermark_x_ratio", "watermark_y_ratio",
                "watermark_size_ratio",
                "aigc_label", "aigc_label_x_ratio", "aigc_label_y_ratio",
            ]
        }


@dataclass
class CoverPreview:
    """Numeric layout for a UI preview overlay (CSS-friendly)."""
    canvas_size: tuple[int, int]
    title_position: tuple[int, int]
    title_font_size: int
    watermark_position: tuple[int, int] | None
    watermark_font_size: int | None
    aigc_position: tuple[int, int] | None
    aigc_font_size: int | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "canvas_size": list(self.canvas_size),
            "title": {"x": self.title_position[0], "y": self.title_position[1],
                       "size": self.title_font_size},
            "watermark": (None if not self.watermark_position
                          else {"x": self.watermark_position[0],
                                "y": self.watermark_position[1],
                                "size": self.watermark_font_size}),
            "aigc": (None if not self.aigc_position
                     else {"x": self.aigc_position[0],
                           "y": self.aigc_position[1],
                           "size": self.aigc_font_size}),
        }


@dataclass
class CoverComposeResult:
    output_path: str
    layout: CoverLayout
    preview: CoverPreview
    backend: str = "pil"
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "output_path": self.output_path,
            "layout": self.layout.to_dict(),
            "preview": self.preview.to_dict(),
            "backend": self.backend,
            "notes": list(self.notes),
        }


def _hex_to_rgb(hexstr: str) -> tuple[int, int, int]:
    h = hexstr.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    try:
        return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))
    except Exception:
        return (255, 255, 255)


def preview_layout(canvas_size: tuple[int, int],
                   layout: CoverLayout) -> CoverPreview:
    w, h = canvas_size
    title_size = int(layout.title_size_ratio * h)
    wm_pos = (int(layout.watermark_x_ratio * w),
              int(layout.watermark_y_ratio * h))
    wm_size = int(layout.watermark_size_ratio * h)
    aigc_pos = (int(layout.aigc_label_x_ratio * w),
                int(layout.aigc_label_y_ratio * h))
    aigc_size = int(layout.watermark_size_ratio * h)
    return CoverPreview(
        canvas_size=canvas_size,
        title_position=(int(layout.title_x_ratio * w),
                        int(layout.title_y_ratio * h)),
        title_font_size=title_size,
        watermark_position=wm_pos if layout.watermark_text else None,
        watermark_font_size=wm_size if layout.watermark_text else None,
        aigc_position=aigc_pos if layout.aigc_label else None,
        aigc_font_size=aigc_size if layout.aigc_label else None,
    )


def _pil_compose(base_image: pathlib.Path | None,
                 layout: CoverLayout,
                 output_path: pathlib.Path,
                 *, canvas_size: tuple[int, int]) -> CoverComposeResult:
    from PIL import Image, ImageDraw, ImageFont  # type: ignore
    W, H = canvas_size
    canvas = Image.new("RGB", (W, H), (12, 12, 18))
    if base_image and base_image.exists():
        try:
            bg = Image.open(base_image).convert("RGB")
            ratio = max(W / bg.size[0], H / bg.size[1])
            new_size = (max(1, int(bg.size[0] * ratio)),
                        max(1, int(bg.size[1] * ratio)))
            bg = bg.resize(new_size)
            ox = (bg.size[0] - W) // 2
            oy = (bg.size[1] - H) // 2
            canvas.paste(bg.crop((ox, oy, ox + W, oy + H)), (0, 0))
        except Exception:
            pass

    draw = ImageDraw.Draw(canvas)
    title_size = int(layout.title_size_ratio * H)
    sub_size = int(layout.subtitle_size_ratio * H)

    def _font(sz: int) -> Any:
        for fp in (
            "C:/Windows/Fonts/msyhbd.ttc",
            "C:/Windows/Fonts/simhei.ttf",
            "/usr/share/fonts/opentype/source-han-sans/SourceHanSansSC-Bold.otf",
            "/System/Library/Fonts/PingFang.ttc",
        ):
            if pathlib.Path(fp).exists():
                try:
                    return ImageFont.truetype(fp, sz)
                except Exception:
                    continue
        try:
            return ImageFont.load_default()
        except Exception:
            return None

    title_font = _font(title_size)
    sub_font = _font(sub_size)
    wm_font = _font(int(layout.watermark_size_ratio * H))

    title_color = _hex_to_rgb(layout.title_color)
    stroke_color = _hex_to_rgb(layout.title_stroke_color)
    tx = int(layout.title_x_ratio * W)
    ty = int(layout.title_y_ratio * H)
    if layout.title and title_font:
        draw.text((tx, ty), layout.title, fill=title_color, font=title_font,
                  stroke_width=layout.title_stroke_width,
                  stroke_fill=stroke_color)
    if layout.subtitle and sub_font:
        draw.text((tx, ty + title_size + 10), layout.subtitle,
                  fill=(220, 220, 220), font=sub_font,
                  stroke_width=1, stroke_fill=(0, 0, 0))
    if layout.watermark_text and wm_font:
        wx = int(layout.watermark_x_ratio * W)
        wy = int(layout.watermark_y_ratio * H)
        draw.text((wx, wy), layout.watermark_text,
                  fill=(255, 255, 255), font=wm_font,
                  stroke_width=1, stroke_fill=(0, 0, 0))
    if layout.aigc_label and wm_font:
        ax = int(layout.aigc_label_x_ratio * W)
        ay = int(layout.aigc_label_y_ratio * H)
        draw.text((ax, ay), layout.aigc_label,
                  fill=(255, 255, 255), font=wm_font,
                  stroke_width=1, stroke_fill=(0, 0, 0))
    canvas.save(output_path)
    return CoverComposeResult(
        output_path=str(output_path), layout=layout,
        preview=preview_layout(canvas_size, layout), backend="pil",
    )


def compose_cover(
    base_image: str | pathlib.Path | None,
    output_path: str | pathlib.Path,
    *, layout: CoverLayout | None = None,
    canvas_size: tuple[int, int] = (1080, 1920),
) -> CoverComposeResult:
    layout = layout or CoverLayout()
    out_p = pathlib.Path(output_path)
    out_p.parent.mkdir(parents=True, exist_ok=True)
    base = pathlib.Path(base_image) if base_image else None
    try:
        return _pil_compose(base, layout, out_p, canvas_size=canvas_size)
    except Exception as exc:
        _log.warning("PIL cover compose failed: %s", exc)
        return CoverComposeResult(
            output_path=str(out_p), layout=layout,
            preview=preview_layout(canvas_size, layout),
            backend="none", notes=[str(exc)],
        )


__all__ = [
    "CoverLayout", "CoverPreview", "CoverComposeResult",
    "preview_layout", "compose_cover",
]
