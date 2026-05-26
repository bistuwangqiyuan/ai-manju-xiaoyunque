"""V10 §8.3.1 — Novel → comic PDF generator.

Given a parsed novel (chapters + character library + optional pre-rendered
panel images), produce a multi-page comic PDF using reportlab.

Layout heuristics (per page):
    cover    — title + author + cover image (full-bleed)
    chapter  — chapter title page
    page     — 1-3 panels stacked vertically with caption blocks for prose
              and speech-bubble boxes for dialogue.

Backends:
    1. ``reportlab``  — proper vector PDF.
    2. ``Pillow``      — PNG fallback (one panel per file under output_dir).

The fallback exists so this module is always callable in test envs that
don't ship reportlab.
"""
from __future__ import annotations

import logging
import pathlib
import re
from dataclasses import dataclass, field
from typing import Any

_log = logging.getLogger(__name__)


@dataclass
class ComicPanel:
    caption: str = ""
    dialogue: list[tuple[str, str]] = field(default_factory=list)   # (speaker, line)
    image_path: str | None = None
    chapter_index: int = 0
    panel_index: int = 0


@dataclass
class ComicSpec:
    title: str
    author: str = ""
    cover_path: str | None = None
    panels: list[ComicPanel] = field(default_factory=list)
    page_size: tuple[float, float] = (1080.0, 1920.0)  # 9:16 default
    panels_per_page: int = 2


@dataclass
class ComicResult:
    output_path: str
    backend: str
    n_pages: int = 0
    n_panels: int = 0
    extra_paths: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "output_path": self.output_path, "backend": self.backend,
            "n_pages": self.n_pages, "n_panels": self.n_panels,
            "extra_paths": list(self.extra_paths),
        }


# ---------- spec builder from raw chapters ----------

_DIALOG_RE = re.compile(r'"([^"]+)"|"([^"]+)"|「([^」]+)」')


def build_spec_from_novel(
    *,
    title: str,
    author: str = "",
    chapters: list[dict | str],
    panel_images_by_chapter: dict[int, list[str]] | None = None,
    cover_path: str | None = None,
    max_panels_per_chapter: int = 6,
) -> ComicSpec:
    """Build a :class:`ComicSpec` from a list of chapters.

    ``chapters`` entries may be plain strings (whole-chapter text) or dicts
    with optional ``title`` / ``content`` keys.
    """
    panels: list[ComicPanel] = []
    img_map = panel_images_by_chapter or {}
    for ch_idx, raw in enumerate(chapters):
        if isinstance(raw, dict):
            content = raw.get("content") or raw.get("text") or ""
        else:
            content = str(raw)
        if not content.strip():
            continue
        paragraphs = [p.strip() for p in content.split("\n") if p.strip()]
        para_per_panel = max(1, len(paragraphs) // max_panels_per_chapter)
        for p_idx in range(0, len(paragraphs), para_per_panel):
            chunk = " ".join(paragraphs[p_idx:p_idx + para_per_panel])
            if not chunk:
                continue
            dialogue: list[tuple[str, str]] = []
            for m in _DIALOG_RE.finditer(chunk):
                line = next((g for g in m.groups() if g), "")
                if line:
                    dialogue.append(("", line.strip()))
            caption = _DIALOG_RE.sub("", chunk).strip()
            caption = re.sub(r"\s{2,}", " ", caption)[:200]
            img_pool = img_map.get(ch_idx, [])
            img = img_pool[p_idx // para_per_panel] if (
                img_pool and p_idx // para_per_panel < len(img_pool)
            ) else None
            panels.append(ComicPanel(
                caption=caption, dialogue=dialogue,
                image_path=img, chapter_index=ch_idx,
                panel_index=p_idx // para_per_panel,
            ))
            if len([p for p in panels
                    if p.chapter_index == ch_idx]) >= max_panels_per_chapter:
                break
    return ComicSpec(
        title=title, author=author, cover_path=cover_path, panels=panels,
    )


# ---------- reportlab PDF backend ----------

def _try_reportlab_render(spec: ComicSpec,
                          output_path: pathlib.Path) -> ComicResult | None:
    try:
        from reportlab.lib.pagesizes import portrait  # type: ignore
        from reportlab.pdfgen import canvas  # type: ignore
        from reportlab.lib.utils import ImageReader  # type: ignore
        from reportlab.pdfbase import pdfmetrics  # type: ignore
        from reportlab.pdfbase.cidfonts import UnicodeCIDFont  # type: ignore
    except Exception:
        return None
    try:
        try:
            pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))
            font_name = "STSong-Light"
        except Exception:
            font_name = "Helvetica"

        w, h = spec.page_size
        c = canvas.Canvas(str(output_path), pagesize=portrait((w, h)))
        n_pages = 0

        if spec.cover_path and pathlib.Path(spec.cover_path).exists():
            try:
                c.drawImage(ImageReader(spec.cover_path), 0, 0, width=w, height=h,
                            preserveAspectRatio=True, anchor="c", mask="auto")
            except Exception:
                pass
            c.setFont(font_name, 64)
            c.drawCentredString(w / 2, h - 240, spec.title)
            if spec.author:
                c.setFont(font_name, 32)
                c.drawCentredString(w / 2, h - 320, spec.author)
            c.showPage()
            n_pages += 1

        per_page = spec.panels_per_page
        panel_h = h / per_page
        margin = 40

        current_ch = -1
        for i, panel in enumerate(spec.panels):
            if panel.chapter_index != current_ch:
                current_ch = panel.chapter_index
                c.setFont(font_name, 48)
                c.drawCentredString(w / 2, h - 160,
                                    f"第 {panel.chapter_index + 1} 章")
                c.showPage()
                n_pages += 1

            pos_idx = i % per_page
            if pos_idx == 0 and i > 0:
                c.showPage()
                n_pages += 1
            top = h - pos_idx * panel_h
            bottom = top - panel_h
            c.rect(margin, bottom + margin, w - 2 * margin,
                   panel_h - 2 * margin)

            if panel.image_path and pathlib.Path(panel.image_path).exists():
                try:
                    c.drawImage(
                        ImageReader(panel.image_path),
                        margin + 10, bottom + margin + 120,
                        width=w - 2 * margin - 20,
                        height=panel_h - 2 * margin - 220,
                        preserveAspectRatio=True, anchor="c", mask="auto",
                    )
                except Exception:
                    pass

            c.setFont(font_name, 22)
            y = bottom + margin + 90
            caption_lines = _wrap_chinese(panel.caption, max_chars=30)
            for line in caption_lines[:3]:
                c.drawString(margin + 20, y, line)
                y -= 28
            for spk, line in panel.dialogue[:2]:
                bubble = f"「{line}」"
                c.drawString(margin + 20, y, bubble)
                y -= 28
        if spec.panels:
            c.showPage()
            n_pages += 1
        c.save()
        return ComicResult(
            output_path=str(output_path), backend="reportlab",
            n_pages=n_pages, n_panels=len(spec.panels),
        )
    except Exception as exc:
        _log.warning("reportlab render failed: %s", exc)
        return None


def _wrap_chinese(text: str, max_chars: int = 30) -> list[str]:
    if not text:
        return []
    out: list[str] = []
    line = ""
    for ch in text:
        line += ch
        if len(line) >= max_chars or ch in "。！？":
            out.append(line)
            line = ""
    if line:
        out.append(line)
    return out


# ---------- PIL fallback (one PNG per panel) ----------

def _pil_fallback_render(spec: ComicSpec,
                         output_path: pathlib.Path) -> ComicResult | None:
    try:
        from PIL import Image, ImageDraw, ImageFont  # type: ignore
    except Exception:
        return None
    output_path = output_path.with_suffix("")
    output_path.mkdir(parents=True, exist_ok=True)
    extra: list[str] = []
    try:
        font = ImageFont.load_default()
    except Exception:
        font = None
    for i, panel in enumerate(spec.panels):
        img = Image.new("RGB", (int(spec.page_size[0]), int(spec.page_size[1] // 2)),
                        (245, 240, 230))
        draw = ImageDraw.Draw(img)
        y = 60
        caption_lines = _wrap_chinese(panel.caption, max_chars=24)
        for line in caption_lines[:6]:
            draw.text((40, y), line, fill=(20, 20, 20), font=font)
            y += 28
        for spk, line in panel.dialogue[:3]:
            draw.text((60, y), f"「{line}」", fill=(40, 40, 80), font=font)
            y += 32
        if panel.image_path and pathlib.Path(panel.image_path).exists():
            try:
                ref = Image.open(panel.image_path).convert("RGB")
                ref.thumbnail((int(spec.page_size[0]) - 200, 700))
                img.paste(ref, (100, y + 20))
            except Exception:
                pass
        out_png = output_path / f"panel_{i:03d}.png"
        img.save(out_png)
        extra.append(str(out_png))
    return ComicResult(
        output_path=str(output_path) + "/", backend="pil",
        n_pages=len(extra), n_panels=len(spec.panels),
        extra_paths=extra,
    )


# ---------- public API ----------

def render_comic(spec: ComicSpec,
                 output_path: str | pathlib.Path) -> ComicResult:
    out = pathlib.Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    res = _try_reportlab_render(spec, out)
    if res is not None:
        return res
    res = _pil_fallback_render(spec, out)
    if res is not None:
        return res
    out.write_text(_render_as_text(spec), encoding="utf-8")
    return ComicResult(
        output_path=str(out), backend="text",
        n_pages=1, n_panels=len(spec.panels),
    )


def _render_as_text(spec: ComicSpec) -> str:
    lines = [f"# {spec.title}"]
    if spec.author:
        lines.append(f"作者：{spec.author}")
    lines.append("")
    current_ch = -1
    for p in spec.panels:
        if p.chapter_index != current_ch:
            current_ch = p.chapter_index
            lines.append(f"\n## 第 {current_ch + 1} 章\n")
        lines.append(f"[panel {p.panel_index}] {p.caption}")
        for _spk, dl in p.dialogue:
            lines.append(f"    「{dl}」")
    return "\n".join(lines)


def novel_to_comic(
    *, title: str, author: str = "", chapters: list[dict | str],
    output_path: str | pathlib.Path,
    panel_images_by_chapter: dict[int, list[str]] | None = None,
    cover_path: str | None = None,
    panels_per_page: int = 2,
) -> ComicResult:
    """End-to-end convenience wrapper."""
    spec = build_spec_from_novel(
        title=title, author=author, chapters=chapters,
        panel_images_by_chapter=panel_images_by_chapter,
        cover_path=cover_path,
    )
    spec.panels_per_page = panels_per_page
    return render_comic(spec, output_path)


__all__ = [
    "ComicPanel", "ComicSpec", "ComicResult",
    "build_spec_from_novel", "render_comic", "novel_to_comic",
]
