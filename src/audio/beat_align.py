"""V10 §7.2 — Beat-aligned cut planning.

Given a BGM audio file and a list of desired cut points (in seconds), nudge
each cut to the nearest beat so dialogue / transition boundaries land "on
the music".

Backends (auto-fallback):

    1. ``librosa.beat.beat_track`` — proper tempo + beat-time extraction.
    2. Fallback grid: assume constant tempo from the BGM library entry's
       ``bpm`` field (or a 100 BPM default). Beat times are
       ``[60/bpm * i for i in range(N)]``.

For each requested cut we return:
    requested_sec, snapped_sec, beat_index, delta_sec
"""
from __future__ import annotations

import logging
import pathlib
from dataclasses import dataclass, field
from typing import Any

_log = logging.getLogger(__name__)


@dataclass
class BeatGrid:
    bpm: float
    beat_times: list[float] = field(default_factory=list)
    backend: str = "constant"
    audio_duration: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "bpm": round(float(self.bpm), 2),
            "n_beats": len(self.beat_times),
            "audio_duration": round(self.audio_duration, 3),
            "backend": self.backend,
        }


@dataclass
class SnappedCut:
    requested_sec: float
    snapped_sec: float
    beat_index: int
    delta_sec: float

    def to_dict(self) -> dict[str, float | int]:
        return {
            "requested_sec": round(self.requested_sec, 3),
            "snapped_sec": round(self.snapped_sec, 3),
            "beat_index": self.beat_index,
            "delta_sec": round(self.delta_sec, 4),
        }


def _try_librosa_beats(audio_path: pathlib.Path) -> BeatGrid | None:
    try:
        import librosa  # type: ignore
        import numpy as np  # type: ignore
    except Exception:
        return None
    try:
        y, sr = librosa.load(str(audio_path), sr=22050, mono=True)
        tempo, beats = librosa.beat.beat_track(y=y, sr=sr)
        beat_times = librosa.frames_to_time(beats, sr=sr).tolist()
        if not beat_times:
            return None
        return BeatGrid(
            bpm=float(tempo if not hasattr(tempo, "item") else tempo.item()),
            beat_times=[float(t) for t in beat_times],
            backend="librosa",
            audio_duration=float(len(y) / sr),
        )
    except Exception as exc:
        _log.debug("librosa beat-track failed: %s", exc)
        return None


def _constant_grid(bpm: float, audio_duration: float = 600.0) -> BeatGrid:
    if bpm <= 0:
        bpm = 100.0
    interval = 60.0 / bpm
    n_beats = max(2, int(audio_duration / interval) + 1)
    return BeatGrid(
        bpm=float(bpm),
        beat_times=[i * interval for i in range(n_beats)],
        backend="constant",
        audio_duration=float(audio_duration),
    )


def compute_beats(
    audio_path: str | pathlib.Path | None = None,
    *, bpm_hint: float | None = None,
    audio_duration: float = 600.0,
) -> BeatGrid:
    """Get a beat grid for ``audio_path`` (or a hinted constant grid)."""
    if audio_path:
        p = pathlib.Path(audio_path)
        if p.exists():
            grid = _try_librosa_beats(p)
            if grid is not None:
                return grid
    return _constant_grid(bpm_hint or 100.0, audio_duration=audio_duration)


def snap_cuts(beat_grid: BeatGrid, requested_seconds: list[float],
              *, max_drift: float = 0.30) -> list[SnappedCut]:
    """Snap each requested cut time to the nearest beat (within ``max_drift``).

    If no beat lies within ``max_drift``, the cut is kept at its requested
    time (and ``beat_index == -1``).
    """
    if not beat_grid.beat_times:
        return [SnappedCut(t, t, -1, 0.0) for t in requested_seconds]
    out: list[SnappedCut] = []
    for t in requested_seconds:
        # binary-search nearest beat
        bt = beat_grid.beat_times
        lo, hi = 0, len(bt) - 1
        while lo < hi:
            mid = (lo + hi) // 2
            if bt[mid] < t:
                lo = mid + 1
            else:
                hi = mid
        cand: list[tuple[int, float]] = []
        if lo > 0:
            cand.append((lo - 1, bt[lo - 1]))
        cand.append((lo, bt[lo]))
        if lo + 1 < len(bt):
            cand.append((lo + 1, bt[lo + 1]))
        nearest_idx, nearest = min(cand, key=lambda kv: abs(kv[1] - t))
        delta = nearest - t
        if abs(delta) <= max_drift:
            out.append(SnappedCut(t, float(nearest), int(nearest_idx), float(delta)))
        else:
            out.append(SnappedCut(t, float(t), -1, 0.0))
    return out


__all__ = ["BeatGrid", "SnappedCut", "compute_beats", "snap_cuts"]
