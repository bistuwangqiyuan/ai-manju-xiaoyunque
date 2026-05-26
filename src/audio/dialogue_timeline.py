"""V10 §7.1 — Dialogue timeline alignment.

Given a list of dialogue lines + (optional) per-line audio files, produce a
timeline of ``(start_seconds, end_seconds, line_index, text)`` tuples that
the subtitle renderer & video compositor can use.

Strategies (auto-fallback in order):

    1. ``whisperX`` forced alignment against the rendered TTS audio
       (gives ~50 ms word-level accuracy when audio is clean).
    2. ffprobe duration of each per-line audio file + sequential offsets.
    3. Pure character-rate estimator (3.5 chars/sec Chinese, 14 chars/sec EN).

Output is deterministic; with the same input you always get the same
timeline. This is the only file the subtitle layer needs to consume.
"""
from __future__ import annotations

import json
import logging
import pathlib
import re
import shutil
import subprocess
from dataclasses import dataclass, field
from typing import Any

_log = logging.getLogger(__name__)

# Approximate speaking rates — Chinese measured at our 6 voice roles avg.
_CHARS_PER_SEC = {"zh": 3.6, "en": 14.0, "ja": 6.2, "ko": 5.8, "th": 7.4}
_DEFAULT_RATE = 4.0
_GAP_BETWEEN_LINES_SEC = 0.25      # natural pause between consecutive lines
_MIN_LINE_SEC = 0.5
_MAX_LINE_SEC = 12.0


@dataclass
class DialogueLine:
    index: int
    text: str
    speaker_role: str | None = None
    emotion: str | None = None
    language: str = "zh"
    audio_path: str | None = None     # rendered TTS file (mp3/wav)


@dataclass
class TimedLine:
    index: int
    start: float
    end: float
    text: str
    speaker_role: str | None = None
    language: str = "zh"

    @property
    def duration(self) -> float:
        return self.end - self.start

    def to_dict(self) -> dict[str, Any]:
        return {
            "index": self.index, "start": round(self.start, 3),
            "end": round(self.end, 3), "duration": round(self.duration, 3),
            "text": self.text, "speaker_role": self.speaker_role,
            "language": self.language,
        }


@dataclass
class Timeline:
    lines: list[TimedLine] = field(default_factory=list)
    total_duration: float = 0.0
    backend: str = "estimate"
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "lines": [l.to_dict() for l in self.lines],
            "total_duration": round(self.total_duration, 3),
            "backend": self.backend, "notes": self.notes,
        }


# ---------- character-rate estimator (always available) ----------

def _detect_lang(text: str) -> str:
    if re.search(r"[\u4e00-\u9fff]", text):
        return "zh"
    if re.search(r"[\u3040-\u30ff]", text):
        return "ja"
    if re.search(r"[\uac00-\ud7af]", text):
        return "ko"
    if re.search(r"[\u0e00-\u0e7f]", text):
        return "th"
    return "en"


def _estimate_line_duration(text: str, language: str | None = None,
                            speed: float = 1.0) -> float:
    text = text.strip()
    if not text:
        return _MIN_LINE_SEC
    lang = (language or _detect_lang(text)).lower()
    rate = _CHARS_PER_SEC.get(lang, _DEFAULT_RATE)
    # punctuation pads — commas 0.10s, period 0.25s, exclam/question 0.30s
    punct_pad = (text.count("，") + text.count(",")) * 0.10
    punct_pad += (text.count("。") + text.count(".")) * 0.25
    punct_pad += (text.count("！") + text.count("!")) * 0.30
    punct_pad += (text.count("？") + text.count("?")) * 0.30
    n_chars = sum(1 for ch in text if not ch.isspace())
    seconds = (n_chars / rate) / max(speed, 0.1) + punct_pad
    return float(max(_MIN_LINE_SEC, min(_MAX_LINE_SEC, seconds)))


# ---------- ffprobe duration extraction ----------

def _ffprobe_duration(path: str | pathlib.Path) -> float | None:
    p = pathlib.Path(path)
    if not p.exists() or not shutil.which("ffprobe"):
        return None
    try:
        out = subprocess.check_output(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "json", str(p)],
            stderr=subprocess.STDOUT, timeout=10,
        )
        d = json.loads(out)
        return float(d.get("format", {}).get("duration", 0)) or None
    except Exception as exc:
        _log.debug("ffprobe failed for %s: %s", p, exc)
        return None


# ---------- whisperX forced alignment (optional) ----------

def _whisperx_align(audio_path: str | pathlib.Path, expected_text: str,
                    language: str = "zh") -> tuple[float, float] | None:
    try:
        import whisperx  # type: ignore
    except Exception:
        return None
    try:
        model_a, metadata = whisperx.load_align_model(language_code=language, device="cpu")
        result = whisperx.align(
            transcript=[{"text": expected_text, "start": 0.0, "end": 30.0}],
            model=model_a, align_model_metadata=metadata,
            audio=str(audio_path), device="cpu",
        )
        seg = result["segments"][0]
        return float(seg["start"]), float(seg["end"])
    except Exception as exc:
        _log.debug("whisperx align failed: %s", exc)
        return None


# ---------- public API ----------

def build_timeline(
    lines: list[DialogueLine | dict[str, Any]],
    *, gap: float = _GAP_BETWEEN_LINES_SEC,
    use_whisperx: bool = False,
    language_default: str = "zh",
) -> Timeline:
    """Build a deterministic dialogue timeline.

    ``lines`` may be a list of ``DialogueLine`` dataclasses or simple dicts
    with keys ``index, text, speaker_role, emotion, language, audio_path``.
    """
    normalised: list[DialogueLine] = []
    for i, raw in enumerate(lines):
        if isinstance(raw, DialogueLine):
            line = raw
        else:
            line = DialogueLine(
                index=raw.get("index", i),
                text=raw.get("text", ""),
                speaker_role=raw.get("speaker_role"),
                emotion=raw.get("emotion"),
                language=raw.get("language", language_default),
                audio_path=raw.get("audio_path"),
            )
        normalised.append(line)

    timeline = Timeline(backend="estimate")
    cursor = 0.0
    used_whisperx, used_ffprobe = 0, 0

    for line in normalised:
        duration: float | None = None
        if use_whisperx and line.audio_path:
            res = _whisperx_align(line.audio_path, line.text, line.language)
            if res is not None:
                start_off, end_off = res
                duration = max(_MIN_LINE_SEC, end_off - start_off)
                used_whisperx += 1
        if duration is None and line.audio_path:
            d = _ffprobe_duration(line.audio_path)
            if d:
                duration = d
                used_ffprobe += 1
        if duration is None:
            duration = _estimate_line_duration(line.text, line.language)

        start = cursor
        end = start + duration
        timeline.lines.append(TimedLine(
            index=line.index, start=start, end=end, text=line.text,
            speaker_role=line.speaker_role, language=line.language,
        ))
        cursor = end + gap

    timeline.total_duration = max(cursor - gap, 0.0)
    if used_whisperx:
        timeline.backend = "whisperx"
        timeline.notes.append(f"whisperx aligned {used_whisperx} lines")
    elif used_ffprobe:
        timeline.backend = "ffprobe"
        timeline.notes.append(f"ffprobe measured {used_ffprobe} lines")
    return timeline


def save_timeline(timeline: Timeline, output_path: str | pathlib.Path) -> pathlib.Path:
    p = pathlib.Path(output_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(timeline.to_dict(), ensure_ascii=False, indent=2),
                 encoding="utf-8")
    return p


def timeline_to_ass_lines(timeline: Timeline,
                          style: str = "Default") -> list:
    """Convert to ``shell5_post_production.ass_subtitle.AssLine`` objects."""
    try:
        from ..shell5_post_production.ass_subtitle import AssLine
    except Exception:
        from dataclasses import dataclass

        @dataclass
        class AssLine:  # type: ignore
            start_seconds: float
            end_seconds: float
            text: str
            style: str = "Default"
    return [AssLine(start_seconds=l.start, end_seconds=l.end,
                    text=l.text, style=style) for l in timeline.lines]


__all__ = [
    "DialogueLine", "TimedLine", "Timeline",
    "build_timeline", "save_timeline", "timeline_to_ass_lines",
]
