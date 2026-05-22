"""Shell 5 — Post-production (TTS / BGM / SFX / subtitle / cover / 4K + 母带精修)."""

from .tts_doubao_icl import DoubaoIclClient, TTSRequest
from .bgm_elevenlabs import ElevenLabsMusicClient
from .sfx_elevenlabs import ElevenLabsSfxClient
from .ass_subtitle import render_ass, AssLine
from .cover_seedream import build_cover
from .upscale_veo31 import Veo31Upscaler
from .ffmpeg_compose import compose_final
from .cinematic_master import (
    MasterConfig,
    MasterError,
    cyberpunk_v1_config,
    master,
    select_chinese_bold_font,
)
from .quality_metrics import (
    ffprobe_streams_format,
    is_faststart,
    parse_top_level_boxes,
    sample_roi_stats,
    sample_roi_y_brightness,
)
from .platform_export import export_for_platforms, PLATFORM_SPECS, PlatformSpec
from .marketing_copy import generate_marketing_copy
from .watermark import apply_watermark

__all__ = [
    "DoubaoIclClient",
    "TTSRequest",
    "ElevenLabsMusicClient",
    "ElevenLabsSfxClient",
    "render_ass",
    "AssLine",
    "build_cover",
    "Veo31Upscaler",
    "compose_final",
    "MasterConfig",
    "MasterError",
    "cyberpunk_v1_config",
    "master",
    "select_chinese_bold_font",
    "ffprobe_streams_format",
    "is_faststart",
    "parse_top_level_boxes",
    "sample_roi_stats",
    "sample_roi_y_brightness",
    "export_for_platforms",
    "PLATFORM_SPECS",
    "PlatformSpec",
    "generate_marketing_copy",
    "apply_watermark",
]
