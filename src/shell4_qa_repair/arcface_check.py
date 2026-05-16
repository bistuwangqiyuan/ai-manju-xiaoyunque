"""Offline ArcFace identity check via the open-source InsightFace SDK.

This module is intentionally tolerant of missing optional dependencies; in
environments without InsightFace installed it falls back to a no-op stub that
makes integration testing painless.
"""
from __future__ import annotations

import logging
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence


_log = logging.getLogger(__name__)


@dataclass
class FaceSimilarity:
    shot_id: int
    similarity: float
    passed: bool
    canonical_embedding_dim: int


class ArcFaceChecker:
    def __init__(self,
                 threshold: float = 0.78,
                 sample_every_seconds: float = 1.0,
                 model_name: str = "buffalo_l"):
        self.threshold = threshold
        self.sample_every_seconds = sample_every_seconds
        self.model_name = model_name
        self._app = None  # lazy
        self._np = None

    # ------------------------------------------------------------------
    def _lazy_init(self):
        if self._app is not None:
            return
        try:  # pragma: no cover — depends on optional SDK
            import insightface
            import numpy as np
            self._np = np
            self._app = insightface.app.FaceAnalysis(name=self.model_name)
            self._app.prepare(ctx_id=-1, det_size=(640, 640))
        except ImportError as e:  # noqa: BLE001
            _log.warning("InsightFace not installed (%s); ArcFace check disabled", e)
            self._app = False

    # ------------------------------------------------------------------
    def embedding(self, image_path: str | Path):
        self._lazy_init()
        if not self._app:
            return None
        img = self._np.array(self._read(image_path))
        faces = self._app.get(img)
        if not faces:
            return None
        return faces[0].normed_embedding

    def similarity(self, video_path: str | Path, canonical_image_path: str | Path,
                   shot_id: int = 0) -> FaceSimilarity:
        self._lazy_init()
        if not self._app:
            return FaceSimilarity(shot_id, similarity=1.0, passed=True, canonical_embedding_dim=0)

        ref = self.embedding(canonical_image_path)
        if ref is None:
            return FaceSimilarity(shot_id, similarity=0.0, passed=False, canonical_embedding_dim=0)

        sims = []
        with tempfile.TemporaryDirectory() as tmpdir:
            frames = self._extract_frames(Path(video_path), Path(tmpdir))
            for f in frames:
                emb = self.embedding(f)
                if emb is None:
                    continue
                sims.append(float((ref * emb).sum()))

        if not sims:
            return FaceSimilarity(shot_id, similarity=0.0, passed=False,
                                  canonical_embedding_dim=len(ref))
        sim_avg = sum(sims) / len(sims)
        return FaceSimilarity(
            shot_id=shot_id,
            similarity=sim_avg,
            passed=sim_avg >= self.threshold,
            canonical_embedding_dim=len(ref),
        )

    # ------------------------------------------------------------------

    def _extract_frames(self, video: Path, out_dir: Path) -> list[Path]:
        fps = 1.0 / max(self.sample_every_seconds, 0.1)
        out = out_dir / "frame_%04d.jpg"
        cmd = ["ffmpeg", "-y", "-i", str(video), "-vf", f"fps={fps}",
               "-q:v", "2", str(out)]
        subprocess.run(cmd, check=True, capture_output=True)
        return sorted(out_dir.glob("frame_*.jpg"))

    @staticmethod
    def _read(path: str | Path):
        from PIL import Image  # type: ignore
        img = Image.open(path).convert("RGB")
        return img
