"""V10 §7 — Audio production layer.

Submodules:
    voice_library      §7.1  6 timbres × 7 emotions, multi-provider fallback
    dialogue_timeline  §7.1  whisperX-aligned per-line start/end timestamps
    bgm_library        §7.2  curated BGM catalogue (mood × bpm × duration)
    bgm_recommender    §7.2  laion-clap text→audio matching with fallback
    beat_align         §7.2  librosa beat-tracking → cut-on-beat planner
    sfx_auto_inject    §7.2  action/scene keyword → SFX library auto-insert
    lufs_normalize     §7.4  pyloudnorm streaming-platform loudness
"""
from __future__ import annotations

__all__ = [
    "voice_library", "dialogue_timeline",
    "bgm_library", "bgm_recommender", "beat_align", "sfx_auto_inject",
    "lufs_normalize",
]
