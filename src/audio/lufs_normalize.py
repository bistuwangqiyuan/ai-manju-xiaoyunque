"""V10 §7.4 — Loudness normalisation (LUFS).

Provides an audio-loudness normaliser that maps an arbitrary input audio
file to a target integrated loudness (e.g. -14 LUFS for streaming
platforms).

Backends (auto-fallback):

    1. ``pyloudnorm`` (preferred) — proper ITU BS.1770 measurement +
       normalisation, then write via soundfile.
    2. ffmpeg ``loudnorm`` filter (single-pass) — close enough for
       short-form drama production.
    3. Pass-through copy (last resort, with a note in the result).

All paths are absolute. Returns a small report dict describing the
backend used, input/target/output LUFS and the output file path.
"""
from __future__ import annotations

import json
import logging
import pathlib
import shutil
import subprocess
from dataclasses import dataclass, field
from typing import Any

_log = logging.getLogger(__name__)


@dataclass
class LufsReport:
    input_path: str
    output_path: str
    target_lufs: float
    measured_input_lufs: float | None = None
    measured_output_lufs: float | None = None
    backend: str = "passthrough"
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "input_path": self.input_path, "output_path": self.output_path,
            "target_lufs": self.target_lufs,
            "measured_input_lufs": self.measured_input_lufs,
            "measured_output_lufs": self.measured_output_lufs,
            "backend": self.backend, "notes": self.notes,
        }


def _try_pyloudnorm(in_path: pathlib.Path, out_path: pathlib.Path,
                    target_lufs: float) -> LufsReport | None:
    try:
        import numpy as np  # type: ignore
        import pyloudnorm as pyln  # type: ignore
        import soundfile as sf  # type: ignore
    except Exception:
        return None
    try:
        data, sr = sf.read(str(in_path))
        meter = pyln.Meter(sr)
        in_lufs = float(meter.integrated_loudness(data))
        if not np.isfinite(in_lufs):
            return None
        norm = pyln.normalize.loudness(data, in_lufs, target_lufs)
        sf.write(str(out_path), norm, sr)
        out_lufs = float(meter.integrated_loudness(norm))
        return LufsReport(
            input_path=str(in_path), output_path=str(out_path),
            target_lufs=target_lufs, measured_input_lufs=in_lufs,
            measured_output_lufs=out_lufs, backend="pyloudnorm",
        )
    except Exception as exc:
        _log.debug("pyloudnorm normalise failed: %s", exc)
        return None


def _ffmpeg_loudnorm(in_path: pathlib.Path, out_path: pathlib.Path,
                     target_lufs: float) -> LufsReport | None:
    if not shutil.which("ffmpeg"):
        return None
    try:
        # single-pass loudnorm filter
        cmd = [
            "ffmpeg", "-y", "-i", str(in_path),
            "-af", f"loudnorm=I={target_lufs}:LRA=11:TP=-1.5:print_format=json",
            "-c:a", "libmp3lame" if out_path.suffix.lower() == ".mp3" else "pcm_s16le",
            str(out_path),
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
        if proc.returncode != 0:
            _log.debug("ffmpeg loudnorm rc=%d stderr=%s", proc.returncode,
                       proc.stderr[-500:])
            return None
        # ffmpeg prints loudnorm JSON to stderr
        out_blob = proc.stderr
        try:
            brace = out_blob.rfind("{")
            measured = json.loads(out_blob[brace:out_blob.rfind("}") + 1])
            in_lufs = float(measured.get("input_i", 0))
            out_lufs = float(measured.get("output_i", target_lufs))
        except Exception:
            in_lufs, out_lufs = None, None
        return LufsReport(
            input_path=str(in_path), output_path=str(out_path),
            target_lufs=target_lufs, measured_input_lufs=in_lufs,
            measured_output_lufs=out_lufs, backend="ffmpeg_loudnorm",
        )
    except Exception as exc:
        _log.debug("ffmpeg loudnorm failed: %s", exc)
        return None


def normalize(
    input_path: str | pathlib.Path,
    output_path: str | pathlib.Path,
    *, target_lufs: float = -14.0,
) -> LufsReport:
    in_p = pathlib.Path(input_path)
    out_p = pathlib.Path(output_path)
    out_p.parent.mkdir(parents=True, exist_ok=True)
    if not in_p.exists():
        raise FileNotFoundError(f"input audio missing: {in_p}")

    rep = _try_pyloudnorm(in_p, out_p, target_lufs)
    if rep is not None:
        return rep
    rep = _ffmpeg_loudnorm(in_p, out_p, target_lufs)
    if rep is not None:
        return rep
    shutil.copy2(str(in_p), str(out_p))
    return LufsReport(
        input_path=str(in_p), output_path=str(out_p),
        target_lufs=target_lufs, backend="passthrough",
        notes=["pyloudnorm + ffmpeg unavailable; copied raw input"],
    )


__all__ = ["LufsReport", "normalize"]
