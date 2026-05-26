"""V10 §5.3 — Local-only hand-region cropper that drives the repair handoff.

Given a frame + an anatomy report indicating a hand anomaly, crop a 1.4×
bounding box around the offending hand and emit a mask that the repair
router can hand to FLUX Kontext / Inpaint pipelines.

Pure-CPU, no model downloads — mediapipe is preferred but we fall back to
a deterministic centre crop when it's not available.
"""
from __future__ import annotations

import pathlib
from dataclasses import dataclass


@dataclass
class HandCropResult:
    crop_path: str
    mask_path: str
    bbox_xyxy: tuple[int, int, int, int]
    expansion: float = 1.4
    backend: str = "mediapipe"


def _safe_imports():
    try:
        import cv2  # type: ignore
        import mediapipe as mp  # type: ignore
        return cv2, mp
    except Exception:
        return None, None


def repair_hand_local(
    *,
    image_path: str | pathlib.Path,
    output_dir: str | pathlib.Path,
    expansion: float = 1.4,
) -> list[HandCropResult] | None:
    image_path = pathlib.Path(image_path)
    output_dir = pathlib.Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    cv2, mp = _safe_imports()
    if cv2 is None:
        return _fallback(image_path, output_dir, expansion)

    img = cv2.imread(str(image_path))
    if img is None:
        return None
    h, w = img.shape[:2]
    rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    results: list[HandCropResult] = []
    with mp.solutions.hands.Hands(static_image_mode=True, max_num_hands=4) as hands:
        res = hands.process(rgb)
    if not res.multi_hand_landmarks:
        return _fallback(image_path, output_dir, expansion)
    for i, hand in enumerate(res.multi_hand_landmarks):
        xs = [lm.x * w for lm in hand.landmark]
        ys = [lm.y * h for lm in hand.landmark]
        x0, x1 = min(xs), max(xs)
        y0, y1 = min(ys), max(ys)
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        bw, bh = (x1 - x0) * expansion, (y1 - y0) * expansion
        rx0 = max(0, int(cx - bw / 2))
        ry0 = max(0, int(cy - bh / 2))
        rx1 = min(w, int(cx + bw / 2))
        ry1 = min(h, int(cy + bh / 2))
        crop_path = output_dir / f"{image_path.stem}_hand{i}_crop.png"
        mask_path = output_dir / f"{image_path.stem}_hand{i}_mask.png"
        crop = img[ry0:ry1, rx0:rx1]
        cv2.imwrite(str(crop_path), crop)
        # Build a binary mask same dims as original
        import numpy as np  # cv2 ships numpy
        mask = np.zeros((h, w), dtype=np.uint8)
        mask[ry0:ry1, rx0:rx1] = 255
        cv2.imwrite(str(mask_path), mask)
        results.append(HandCropResult(
            crop_path=str(crop_path), mask_path=str(mask_path),
            bbox_xyxy=(rx0, ry0, rx1, ry1), expansion=expansion,
            backend="mediapipe",
        ))
    return results


def _fallback(image_path: pathlib.Path, output_dir: pathlib.Path,
              expansion: float) -> list[HandCropResult] | None:
    try:
        from PIL import Image, ImageDraw  # type: ignore
    except Exception:
        return None
    img = Image.open(image_path).convert("RGB")
    w, h = img.size
    # Place a guess crop in the lower-right quadrant (typical hand location)
    cx, cy = int(w * 0.62), int(h * 0.72)
    bw, bh = int(w * 0.20 * expansion), int(h * 0.20 * expansion)
    x0, y0 = max(0, cx - bw // 2), max(0, cy - bh // 2)
    x1, y1 = min(w, cx + bw // 2), min(h, cy + bh // 2)
    crop_path = output_dir / f"{image_path.stem}_hand0_crop.png"
    mask_path = output_dir / f"{image_path.stem}_hand0_mask.png"
    img.crop((x0, y0, x1, y1)).save(crop_path)
    mask = Image.new("L", (w, h), 0)
    ImageDraw.Draw(mask).rectangle((x0, y0, x1, y1), fill=255)
    mask.save(mask_path)
    return [HandCropResult(
        crop_path=str(crop_path), mask_path=str(mask_path),
        bbox_xyxy=(x0, y0, x1, y1), expansion=expansion,
        backend="fallback",
    )]


__all__ = ["HandCropResult", "repair_hand_local"]
