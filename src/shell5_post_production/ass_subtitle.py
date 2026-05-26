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
Style: AncientSeal,方正小篆体,80,&H00D9B575,&H000000FF,&H00000000,&H00000000,-1,0,0,0,100,100,0,0,1,3,3,2,40,40,160,134
Style: AncientKai,方正楷体_GBK,72,&H00F2EBD5,&H000000FF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,3,2,2,40,40,140,134
Style: ModernSans,思源黑体 CN Bold,68,&H00FFFFFF,&H000000FF,&H00080808,&H00000000,-1,0,0,0,100,100,0,0,1,4,2,2,40,40,130,134
Style: ModernRound,阿里巴巴普惠体 R,68,&H00FFFFFF,&H000000FF,&H00121212,&H00000000,0,0,0,0,100,100,0,0,1,4,2,2,40,40,130,134
Style: DanmuTop,思源黑体 CN,52,&H00FFFFFF,&H000000FF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,2,1,8,40,40,80,134
Style: DanmuRoll,思源黑体 CN,48,&H66FFFFFF,&H000000FF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,1,1,7,40,40,300,134

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

SUBTITLE_STYLES = (
    "Default", "Voiceover",
    "AncientSeal", "AncientKai", "ModernSans", "ModernRound",
    "DanmuTop", "DanmuRoll",
)

STYLE_PRESETS = {
    "modern":         "Default",
    "modern_round":   "ModernRound",
    "modern_sans":    "ModernSans",
    "voiceover":      "Voiceover",
    "ancient_seal":   "AncientSeal",
    "ancient_kai":    "AncientKai",
    "ancient":        "AncientKai",
    "danmu_top":      "DanmuTop",
    "danmu_roll":     "DanmuRoll",
    "bullet":         "DanmuRoll",
}


def resolve_style(name: str | None) -> str:
    if not name:
        return "Default"
    if name in SUBTITLE_STYLES:
        return name
    return STYLE_PRESETS.get(name.lower(), "Default")


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
