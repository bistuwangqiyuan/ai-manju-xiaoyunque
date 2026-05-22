"""Redraw engine — fuses image + text + reference into one output.

Backend priority:
    1. FLUX Kontext (preferred, best edit fidelity)
    2. Seedream 5 i2i
    3. mock (deterministic — pass-through copy with manifest)
"""
from __future__ import annotations

import hashlib
import logging
import os
import pathlib
import shutil
import urllib.request
from dataclasses import dataclass

from .params import RedrawParams

_log = logging.getLogger(__name__)


@dataclass
class RedrawResult:
    item_id: int
    source: str
    output_path: str
    backend: str
    sha256: str
    bytes_in: int
    bytes_out: int


class RedrawEngine:
    """Image-to-image redraw orchestrator."""

    def __init__(self, work_dir: str | pathlib.Path):
        self.work_dir = pathlib.Path(work_dir)
        self.work_dir.mkdir(parents=True, exist_ok=True)

    def redraw(
        self,
        item_id: int,
        source: str | pathlib.Path,
        params: RedrawParams,
    ) -> RedrawResult:
        """Run a single redraw, return result metadata."""
        src = pathlib.Path(source) if not str(source).startswith("http") else None
        bytes_in = src.stat().st_size if src and src.exists() else 0
        out_path = self.work_dir / f"item_{item_id:04d}.png"
        backend = "mock"

        if os.environ.get("FAL_API_KEY") and os.environ.get("FORCE_MOCK_REDRAW") != "1":
            try:
                self._flux_kontext_edit(source, params, out_path)
                backend = "flux_kontext"
            except Exception as e:
                _log.warning("flux kontext failed (%s); falling back to mock", e)

        if backend == "mock":
            # mock: copy or download source as the "result"
            if src and src.exists():
                shutil.copy2(src, out_path)
            else:
                try:
                    self._download(str(source), out_path)
                except Exception:
                    out_path.write_bytes(b"\x89PNG\r\n\x1a\nMOCK")  # dummy
            backend = "mock"

        payload = out_path.read_bytes()
        return RedrawResult(
            item_id=item_id,
            source=str(source),
            output_path=str(out_path),
            backend=backend,
            sha256=hashlib.sha256(payload).hexdigest(),
            bytes_in=bytes_in,
            bytes_out=len(payload),
        )

    # ------------------------------------------------------------------

    def _flux_kontext_edit(
        self,
        source: str | pathlib.Path,
        params: RedrawParams,
        out_path: pathlib.Path,
    ) -> None:
        try:
            from src.shell2_character_assets.edit_flux_kontext import FluxKontextClient
        except ImportError as e:
            raise RuntimeError(f"flux module missing: {e}")

        client = FluxKontextClient()
        url = client.edit(
            base_image_url=str(source),
            instruction=params.refs.text_prompt or _default_instruction(params),
        )
        self._download(url, out_path)

    @staticmethod
    def _download(url: str, dest: pathlib.Path) -> None:
        req = urllib.request.Request(url, headers={"User-Agent": "redraw-batch/1.0"})
        with urllib.request.urlopen(req, timeout=300) as resp:
            dest.write_bytes(resp.read())


def _default_instruction(params: RedrawParams) -> str:
    parts = [
        f"风格: {params.style}",
        f"题材: {params.genre}",
        f"画幅: {params.aspect_ratio}",
    ]
    if params.refs.character_ids:
        parts.append(f"角色锁定: {', '.join(params.refs.character_ids)}")
    if params.refs.forbidden_elements:
        parts.append(f"禁忌: {', '.join(params.refs.forbidden_elements)}")
    if params.structure_lock:
        parts.append("保持原图人体结构、面部五官、视角与比例")
    return "；".join(parts)


__all__ = ["RedrawEngine", "RedrawResult"]
