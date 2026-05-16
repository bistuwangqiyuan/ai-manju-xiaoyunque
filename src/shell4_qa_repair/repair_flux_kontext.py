"""FLUX Kontext shot-level wardrobe repair (frame-by-frame in-paint)."""
from __future__ import annotations

import json
import os
import pathlib
import subprocess
import tempfile
from typing import Iterable

from ..shell2_character_assets.edit_flux_kontext import (
    FluxKontextClient, FluxKontextEditRequest,
)
from .repair_router import RepairContext


class FluxKontextShotRepair:
    """Frame-extract → per-frame edit → re-encode to mp4."""

    def __init__(self, client: FluxKontextClient | None = None, fps: int = 24):
        self.client = client or FluxKontextClient()
        self.fps = fps

    def __call__(self, context: RepairContext) -> str:
        sidecar = json.loads(context.shot_prompt) if context.shot_prompt.startswith("{") else {}
        edit_prompt = sidecar.get("edit_prompt",
                                  "修复服装漂移，强化锁定符号：眉间朱砂痣 / 左肩黑藤")
        with tempfile.TemporaryDirectory() as tmp:
            tmp_dir = pathlib.Path(tmp)
            frame_dir = tmp_dir / "frames"
            frame_dir.mkdir()
            self._extract(context.shot_url, frame_dir)
            edited = self._edit_frames(frame_dir, edit_prompt)
            return self._reassemble(edited, tmp_dir / "patched.mp4")

    # ------------------------------------------------------------------

    def _extract(self, video: str, out_dir: pathlib.Path):
        cmd = ["ffmpeg", "-y", "-i", video, "-vf", f"fps={self.fps}",
               str(out_dir / "f_%05d.png")]
        subprocess.run(cmd, check=True, capture_output=True)

    def _edit_frames(self, frame_dir: pathlib.Path, prompt: str) -> Iterable[pathlib.Path]:
        out_dir = frame_dir.parent / "edited"
        out_dir.mkdir(exist_ok=True)
        for frame in sorted(frame_dir.glob("f_*.png")):
            edited_url = self.client.edit(FluxKontextEditRequest(
                source_image_url=frame.as_uri(),
                edit_prompt=prompt, strength=0.4,
            ))
            target = out_dir / frame.name
            self._download(edited_url, target)
            yield target

    @staticmethod
    def _download(url: str, target: pathlib.Path):
        import urllib.request
        with urllib.request.urlopen(url, timeout=60) as resp:
            target.write_bytes(resp.read())

    def _reassemble(self, frames: Iterable[pathlib.Path], output: pathlib.Path) -> str:
        first = next(iter(frames))
        frame_dir = first.parent
        cmd = ["ffmpeg", "-y", "-framerate", str(self.fps),
               "-i", str(frame_dir / "f_%05d.png"),
               "-c:v", "libx264", "-pix_fmt", "yuv420p",
               str(output)]
        subprocess.run(cmd, check=True, capture_output=True)
        return str(output)
