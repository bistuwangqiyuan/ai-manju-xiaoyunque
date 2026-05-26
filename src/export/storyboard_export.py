"""V10 §10.1 — Static storyboard-grid export.

Composes a job's existing shot frames into a single tall storyboard
image (PNG / JPG) ready for share-card or pitch-deck use.

This is a thin wrapper around :func:`src.frame_gen.storyboard_grid.compose_grid`
that ALSO writes a sidecar ``shotlist.txt`` describing each cell
(``[cell N] <duration_s>s · <shot_type> · <description>``).

If ``src.frame_gen.storyboard_grid`` is unavailable, falls back to a
plain PIL grid here (so this module ships standalone).
"""
from __future__ import annotations

import logging
import pathlib
from dataclasses import dataclass, field
from typing import Any

_log = logging.getLogger(__name__)


@dataclass
class StoryboardCell:
    path: str
    shot_id: int = 0
    duration_s: float = 3.0
    shot_type: str = "medium"
    description: str = ""


@dataclass
class StoryboardExportResult:
    output_path: str
    sidecar_path: str
    rows: int
    cols: int
    n_cells: int
    backend: str = "pil"
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "output_path": self.output_path,
            "sidecar_path": self.sidecar_path,
            "rows": self.rows, "cols": self.cols,
            "n_cells": self.n_cells, "backend": self.backend,
            "notes": list(self.notes),
        }


def _pil_grid(
    cells: list[StoryboardCell],
    out_path: pathlib.Path,
    *, cols: int = 3, cell_size: tuple[int, int] = (480, 270),
    gutter: int = 12, bg: tuple[int, int, int] = (30, 30, 36),
    show_numbers: bool = True,
) -> tuple[int, int, str]:
    try:
        from PIL import Image, ImageDraw, ImageFont  # type: ignore
    except Exception:
        raise RuntimeError("PIL not available")
    cw, ch = cell_size
    n = len(cells)
    rows = (n + cols - 1) // cols
    W = cols * cw + (cols + 1) * gutter
    H = rows * ch + (rows + 1) * gutter
    canvas = Image.new("RGB", (W, H), bg)
    draw = ImageDraw.Draw(canvas)
    try:
        font = ImageFont.load_default()
    except Exception:
        font = None
    for i, cell in enumerate(cells):
        r = i // cols
        c = i % cols
        x = gutter + c * (cw + gutter)
        y = gutter + r * (ch + gutter)
        if cell.path and pathlib.Path(cell.path).exists():
            try:
                im = Image.open(cell.path).convert("RGB")
                im.thumbnail((cw, ch))
                ix = x + (cw - im.size[0]) // 2
                iy = y + (ch - im.size[1]) // 2
                canvas.paste(im, (ix, iy))
            except Exception:
                draw.rectangle((x, y, x + cw, y + ch), fill=(70, 70, 80))
        else:
            draw.rectangle((x, y, x + cw, y + ch), fill=(70, 70, 80))
        # cell border
        draw.rectangle((x, y, x + cw, y + ch), outline=(255, 255, 255), width=2)
        if show_numbers:
            tag = f"{cell.shot_id or (i + 1)}"
            tag_w = 36
            draw.rectangle((x, y, x + tag_w, y + 22),
                           fill=(0, 0, 0))
            draw.text((x + 6, y + 4), tag, fill=(255, 255, 255), font=font)
    canvas.save(out_path)
    return rows, cols, "pil"


def export_storyboard(
    cells: list[StoryboardCell] | list[dict[str, Any]],
    output_path: str | pathlib.Path,
    *, cols: int = 3,
    cell_size: tuple[int, int] = (480, 270),
    title: str = "Storyboard",
    show_numbers: bool = True,
) -> StoryboardExportResult:
    out_p = pathlib.Path(output_path)
    out_p.parent.mkdir(parents=True, exist_ok=True)
    normalised: list[StoryboardCell] = []
    for i, c in enumerate(cells):
        if isinstance(c, StoryboardCell):
            normalised.append(c)
        else:
            normalised.append(StoryboardCell(
                path=c.get("path") or c.get("image_path") or "",
                shot_id=c.get("shot_id") or (i + 1),
                duration_s=float(c.get("duration_s") or 3.0),
                shot_type=c.get("shot_type") or "medium",
                description=c.get("description") or "",
            ))
    # Try the shared composer first
    backend = "pil"
    try:
        from ..frame_gen.storyboard_grid import compose_grid  # type: ignore
        cell_paths = [c.path for c in normalised]
        compose_grid(cell_paths, out_p, cols=cols,
                     cell_size=cell_size, show_numbers=show_numbers)
        rows = (len(normalised) + cols - 1) // cols
        backend = "frame_gen.storyboard_grid"
    except Exception:
        rows, cols, backend = _pil_grid(
            normalised, out_p, cols=cols, cell_size=cell_size,
            show_numbers=show_numbers,
        )
    sidecar = out_p.with_suffix(".shotlist.txt")
    lines = [f"# {title}\n"]
    for i, c in enumerate(normalised):
        lines.append(
            f"[cell {c.shot_id or (i + 1):>3}] {c.duration_s:>4.1f}s · "
            f"{c.shot_type:<10} · {c.description}"
        )
    sidecar.write_text("\n".join(lines), encoding="utf-8")
    return StoryboardExportResult(
        output_path=str(out_p), sidecar_path=str(sidecar),
        rows=rows, cols=cols, n_cells=len(normalised), backend=backend,
    )


__all__ = ["StoryboardCell", "StoryboardExportResult", "export_storyboard"]
