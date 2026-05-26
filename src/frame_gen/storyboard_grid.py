"""V10 §5.1 — Storyboard grid composition with numbered cells.

Takes a list of panel images + their grid labels and stitches them into a
single contact sheet using PIL.  Each cell carries a label badge in the
top-left corner so editors can quickly reference panel numbers.

Degrades to "image-list manifest" output when PIL is unavailable so the
orchestrator can still surface the panel data to the user.
"""
from __future__ import annotations

import math
import pathlib
from dataclasses import dataclass


@dataclass
class GridResult:
    output_path: str | None
    manifest_path: str
    cols: int
    rows: int
    cell_size: tuple[int, int]
    n_cells: int


def compose_grid(
    panel_paths: list[str | pathlib.Path],
    *,
    output_path: str | pathlib.Path,
    cell_size: tuple[int, int] = (480, 720),
    label_prefix: str = "P",
    background_rgb: tuple[int, int, int] = (24, 24, 24),
    label_rgb: tuple[int, int, int] = (255, 255, 255),
    cols: int | None = None,
) -> GridResult:
    output_path = pathlib.Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    n = len(panel_paths)
    if n == 0:
        raise ValueError("no panels supplied")

    if cols is None:
        cols = math.ceil(math.sqrt(n))
    rows = math.ceil(n / cols)
    cw, ch = cell_size

    manifest_path = output_path.with_suffix(".manifest.json")
    import json
    manifest = {
        "n_cells": n, "cols": cols, "rows": rows,
        "cell_size": list(cell_size),
        "panels": [
            {"index": i + 1, "label": f"{label_prefix}{i + 1:02d}",
             "path": str(pathlib.Path(p).resolve())}
            for i, p in enumerate(panel_paths)
        ],
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2),
                             encoding="utf-8")

    try:
        from PIL import Image, ImageDraw, ImageFont  # type: ignore
    except Exception:
        return GridResult(
            output_path=None, manifest_path=str(manifest_path),
            cols=cols, rows=rows, cell_size=cell_size, n_cells=n,
        )

    canvas = Image.new("RGB", (cw * cols, ch * rows), background_rgb)
    draw = ImageDraw.Draw(canvas)
    try:
        font = ImageFont.truetype("arial.ttf", size=max(16, cw // 14))
    except Exception:
        font = ImageFont.load_default()
    for i, p in enumerate(panel_paths):
        col = i % cols
        row = i // cols
        x0, y0 = col * cw, row * ch
        path = pathlib.Path(p)
        if path.exists():
            try:
                img = Image.open(path).convert("RGB")
                img = _fit(img, cw, ch)
                ox = x0 + (cw - img.width) // 2
                oy = y0 + (ch - img.height) // 2
                canvas.paste(img, (ox, oy))
            except Exception:
                pass
        # Label badge
        label = f"{label_prefix}{i + 1:02d}"
        pad = 6
        try:
            tw = draw.textlength(label, font=font)
            th = font.size if hasattr(font, "size") else 14
        except Exception:
            tw, th = 40, 14
        badge_box = (x0 + pad, y0 + pad, x0 + pad + int(tw) + 14, y0 + pad + th + 8)
        draw.rectangle(badge_box, fill=(0, 0, 0))
        draw.text((badge_box[0] + 7, badge_box[1] + 4), label, fill=label_rgb, font=font)

    canvas.save(output_path, "JPEG", quality=88)
    return GridResult(
        output_path=str(output_path.resolve()),
        manifest_path=str(manifest_path.resolve()),
        cols=cols, rows=rows, cell_size=cell_size, n_cells=n,
    )


def _fit(img, max_w: int, max_h: int):
    w, h = img.width, img.height
    scale = min(max_w / w, max_h / h)
    new = img.resize((max(1, int(w * scale)), max(1, int(h * scale))))
    return new


__all__ = ["GridResult", "compose_grid"]
