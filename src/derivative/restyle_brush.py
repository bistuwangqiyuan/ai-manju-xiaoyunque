"""V10 §8.2 — Partial-restyle "brush mask".

The user uploads (or draws) a binary/grayscale mask over a finished
frame; this module reconstructs that mask into a clean RGBA alpha plate,
optionally feathers the edges, and ships a (image, mask) pair to the
inpaint backend (default FLUX Kontext) along with a restyle prompt.

Designed to share the contract with ``src.qa.repair_router`` so the
same downstream worker can execute both "auto repair" and "user
restyle brush" tasks.
"""
from __future__ import annotations

import logging
import pathlib
from dataclasses import dataclass, field
from typing import Any

_log = logging.getLogger(__name__)


@dataclass
class BrushTask:
    image_path: str
    mask_path: str
    prompt: str
    backend: str = "flux_kontext_inpaint"
    feather_px: int = 8
    strength: float = 0.7
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "image_path": self.image_path, "mask_path": self.mask_path,
            "prompt": self.prompt, "backend": self.backend,
            "feather_px": self.feather_px, "strength": self.strength,
            "notes": self.notes,
        }


def _try_pil():
    try:
        from PIL import Image, ImageFilter  # type: ignore
        return Image, ImageFilter
    except Exception:
        return None, None


def normalize_mask(
    raw_mask_path: str | pathlib.Path,
    out_path: str | pathlib.Path,
    *, feather_px: int = 8,
    threshold: int = 128,
) -> pathlib.Path:
    """Convert an arbitrary user mask into a single-channel feathered alpha PNG.

    Falls back to a binary copy if PIL is unavailable.
    """
    Image, ImageFilter = _try_pil()
    out = pathlib.Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    if Image is None:
        import shutil
        shutil.copy2(raw_mask_path, out)
        return out

    img = Image.open(raw_mask_path).convert("L")
    # binarise
    bin_img = img.point(lambda v: 255 if v >= threshold else 0)
    if feather_px > 0:
        bin_img = bin_img.filter(ImageFilter.GaussianBlur(radius=feather_px))
    bin_img.save(out)
    return out


def make_brush_task(
    *,
    image_path: str | pathlib.Path,
    raw_mask_path: str | pathlib.Path,
    prompt: str,
    work_dir: str | pathlib.Path,
    backend: str = "flux_kontext_inpaint",
    feather_px: int = 8,
    strength: float = 0.7,
) -> BrushTask:
    img_p = pathlib.Path(image_path)
    work = pathlib.Path(work_dir)
    work.mkdir(parents=True, exist_ok=True)
    mask_out = normalize_mask(raw_mask_path, work / f"{img_p.stem}_mask.png",
                              feather_px=feather_px)
    return BrushTask(
        image_path=str(img_p), mask_path=str(mask_out), prompt=prompt,
        backend=backend, feather_px=feather_px, strength=strength,
        notes="user-supplied brush",
    )


__all__ = ["BrushTask", "normalize_mask", "make_brush_task"]
