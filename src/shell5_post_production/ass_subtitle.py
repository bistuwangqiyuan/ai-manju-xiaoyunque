"""ASS subtitle renderer — local 思源黑体 18pt 描边 2px.

The Skylark engine's AI-rendered subtitles have a ~25% garble rate on Chinese.
We bypass them entirely by:

1. Telling the prompt 「画面中禁止出现任何文字」 (handled by reformat_skylark).
2. Generating an ASS subtitle file locally and burning it in with ffmpeg.
"""
from __future__ import annotations

import logging
import pathlib
from dataclasses import dataclass


_log = logging.getLogger(__name__)


@dataclass
class AssLine:
    start_seconds: float
    end_seconds: float
    text: str
    style: str = "Default"


_HEADER = """[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
ScaledBorderAndShadow: yes
YCbCr Matrix: TV.709

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,思源黑体 CN Bold,72,&H00FFFFFF,&H000000FF,&H00000000,&H00000000,-1,0,0,0,100,100,0,0,1,4,2,2,40,40,140,134
Style: Voiceover,思源宋体 CN,64,&H00E8D9B0,&H000000FF,&H00000000,&H00000000,0,1,0,0,100,100,0,0,1,3,2,8,40,40,180,134

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""


def _fmt_ts(seconds: float) -> str:
    h = int(seconds // 3600)
    m = int(seconds // 60) % 60
    s = seconds % 60
    return f"{h:d}:{m:02d}:{s:05.2f}"


def render_ass(lines: list[AssLine], output_path: str | pathlib.Path) -> str:
    out = pathlib.Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    body = [_HEADER]
    for ln in lines:
        text = ln.text.replace("\n", "\\N").replace(",", "，")
        body.append(
            f"Dialogue: 0,{_fmt_ts(ln.start_seconds)},{_fmt_ts(ln.end_seconds)},"
            f"{ln.style},,0,0,0,,{text}"
        )
    out.write_text("\n".join(body) + "\n", encoding="utf-8")
    _log.info("ASS subtitle → %s (%d lines)", out, len(lines))
    return str(out)
