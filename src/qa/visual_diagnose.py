"""V10 §6.2 — Visual diagnosis (heatmap + VLM bbox).

Produces a per-image diagnosis bundle:
    - heatmap PNG that highlights *visual entropy* hotspots
      (using a Laplacian variance map; serves as a cheap saliency proxy)
    - bounding boxes around suspect regions
    - optional VLM follow-up via ``post_vlm_review.review_image`` returning
      sharper categorical labels

Heavy deps (opencv-python) are optional — without them we still emit a
manifest with PIL-based luminance edges.
"""
from __future__ import annotations

import json
import math
import pathlib
from dataclasses import dataclass, field


@dataclass
class DiagnosisRegion:
    label: str
    bbox_xyxy: tuple[int, int, int, int]
    score: float
    note: str = ""


@dataclass
class DiagnosisReport:
    image_path: str
    heatmap_path: str | None
    bbox_overlay_path: str | None
    regions: list[DiagnosisRegion] = field(default_factory=list)
    backend: str = "opencv"
    severity: float = 0.0

    def to_dict(self) -> dict:
        return {
            "image_path": self.image_path,
            "heatmap_path": self.heatmap_path,
            "bbox_overlay_path": self.bbox_overlay_path,
            "backend": self.backend,
            "severity": round(self.severity, 3),
            "regions": [
                {"label": r.label, "bbox_xyxy": list(r.bbox_xyxy),
                 "score": round(r.score, 3), "note": r.note}
                for r in self.regions
            ],
        }


def _try_cv2():
    try:
        import cv2  # type: ignore
        import numpy as np  # type: ignore
        return cv2, np
    except Exception:
        return None, None


def diagnose(image_path: str | pathlib.Path,
             *, output_dir: str | pathlib.Path | None = None,
             top_k: int = 4) -> DiagnosisReport:
    image_path = pathlib.Path(image_path)
    output_dir = pathlib.Path(output_dir) if output_dir else image_path.parent
    output_dir.mkdir(parents=True, exist_ok=True)
    cv2, np = _try_cv2()
    if cv2 is None:
        return _pil_diagnose(image_path, output_dir, top_k)

    img = cv2.imread(str(image_path))
    if img is None:
        return DiagnosisReport(image_path=str(image_path), heatmap_path=None,
                               bbox_overlay_path=None, backend="opencv:failed")
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    lap = cv2.Laplacian(gray, cv2.CV_64F)
    abs_lap = np.absolute(lap)
    # downsample variance map → 16x16 cells, then threshold the top cells
    h, w = abs_lap.shape
    cell_h, cell_w = max(1, h // 16), max(1, w // 16)
    grid = []
    for gy in range(16):
        for gx in range(16):
            y0, x0 = gy * cell_h, gx * cell_w
            y1, x1 = min(h, y0 + cell_h), min(w, x0 + cell_w)
            sub = abs_lap[y0:y1, x0:x1]
            score = float(sub.var() + sub.mean() * 0.5)
            grid.append((score, (x0, y0, x1, y1)))
    grid.sort(key=lambda x: -x[0])
    top = grid[:top_k]
    # severity = normalised mean of top cells
    severity = float(min(10.0, math.log1p(top[0][0]) * 1.4)) if top else 0.0

    # heatmap
    norm = cv2.normalize(abs_lap, None, 0, 255, cv2.NORM_MINMAX).astype("uint8")
    heat = cv2.applyColorMap(norm, cv2.COLORMAP_JET)
    overlay = cv2.addWeighted(img, 0.55, heat, 0.45, 0)
    heat_path = output_dir / f"{image_path.stem}.heatmap.png"
    bbox_path = output_dir / f"{image_path.stem}.bbox.png"
    cv2.imwrite(str(heat_path), overlay)

    bbox_img = img.copy()
    regions: list[DiagnosisRegion] = []
    for i, (score, (x0, y0, x1, y1)) in enumerate(top):
        cv2.rectangle(bbox_img, (x0, y0), (x1, y1), (0, 0, 255), 2)
        regions.append(DiagnosisRegion(
            label=f"hotspot_{i + 1}",
            bbox_xyxy=(int(x0), int(y0), int(x1), int(y1)),
            score=score, note="laplacian-variance",
        ))
    cv2.imwrite(str(bbox_path), bbox_img)

    return DiagnosisReport(
        image_path=str(image_path),
        heatmap_path=str(heat_path),
        bbox_overlay_path=str(bbox_path),
        regions=regions, backend="opencv", severity=severity,
    )


def _pil_diagnose(image_path: pathlib.Path, output_dir: pathlib.Path,
                  top_k: int) -> DiagnosisReport:
    try:
        from PIL import Image, ImageFilter, ImageDraw  # type: ignore
    except Exception:
        return DiagnosisReport(image_path=str(image_path), heatmap_path=None,
                               bbox_overlay_path=None, backend="none")
    img = Image.open(image_path).convert("RGB")
    grey = img.convert("L")
    edges = grey.filter(ImageFilter.FIND_EDGES)
    w, h = img.size
    cell_w, cell_h = max(1, w // 16), max(1, h // 16)
    grid = []
    pixels = edges.load()
    for gy in range(16):
        for gx in range(16):
            x0, y0 = gx * cell_w, gy * cell_h
            x1, y1 = min(w, x0 + cell_w), min(h, y0 + cell_h)
            total = 0
            cnt = 0
            for y in range(y0, y1):
                for x in range(x0, x1):
                    total += pixels[x, y]
                    cnt += 1
            grid.append((total / max(cnt, 1), (x0, y0, x1, y1)))
    grid.sort(key=lambda x: -x[0])
    top = grid[:top_k]
    severity = min(10.0, top[0][0] / 25.0) if top else 0.0
    bbox_path = output_dir / f"{image_path.stem}.bbox.png"
    overlay = img.copy()
    draw = ImageDraw.Draw(overlay)
    regions = []
    for i, (score, (x0, y0, x1, y1)) in enumerate(top):
        draw.rectangle((x0, y0, x1, y1), outline=(255, 30, 30), width=3)
        regions.append(DiagnosisRegion(
            label=f"hotspot_{i + 1}",
            bbox_xyxy=(x0, y0, x1, y1),
            score=score, note="pil-edges",
        ))
    overlay.save(bbox_path)
    return DiagnosisReport(
        image_path=str(image_path),
        heatmap_path=None,
        bbox_overlay_path=str(bbox_path),
        regions=regions, backend="pil", severity=severity,
    )


def save_report(report: DiagnosisReport, path: str | pathlib.Path) -> pathlib.Path:
    path = pathlib.Path(path)
    path.write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2),
                    encoding="utf-8")
    return path


__all__ = ["DiagnosisRegion", "DiagnosisReport", "diagnose", "save_report"]
