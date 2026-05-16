"""Shell 3 — Skylark Agent 2.0 (Pippit IV2V with vinput) rendering engine.

Public API:
    - SkylarkAgentV2WithRefClient            high-level submit + poll + archive
    - EpisodeRequest / ReferencePack         flat官方契约 wrapper
    - AigcMeta                               隐式 AIGC 标识
    - render_chunked_episode / ChunkedEpisodeRequest
                                              >60s 集分块生成
    - SplicePlan / Shot                      本地 ffmpeg 切镜数据模型
    - extract_shots / compose_with_ffmpeg     单镜级别质检 + 修复回灌
"""

from .client import (
    AigcMeta,
    DURATION_VALUES,
    DURATION_MAX_SECONDS,
    EpisodeRequest,
    EpisodeResult,
    LANGUAGE_VALUES,
    MAX_PROMPT_CHARS,
    MAX_REFS_PER_REQUEST,
    RATIO_VALUES,
    SKYLARK_REQ_KEY,
    ReferencePack,
    SkylarkAgentV2WithRefClient,
    SkylarkAuditError,
    SkylarkError,
    SkylarkRetryable,
    SkylarkTimeout,
)
from .chunk_renderer import (
    ChunkedEpisodeRequest,
    render_chunked_episode,
    should_chunk,
    split_prompt_by_act,
)
from .req_key_resolver import REQ_KEY_CANDIDATES, ReqKeyResolver
from .shot_video_extractor import (
    Shot,
    SplicePlan,
    build_splice_plan,
    compose_with_ffmpeg,
    dump_plan,
    extract_shots,
    load_plan,
    replace_shot,
)


# Backwards-compatible alias preserved for callers from the pre-spec era
CharacterReference = ReferencePack       # not perfect, but flagged for migration
SceneReference = ReferencePack


__all__ = [
    "SKYLARK_REQ_KEY",
    "RATIO_VALUES", "DURATION_VALUES", "LANGUAGE_VALUES",
    "DURATION_MAX_SECONDS", "MAX_REFS_PER_REQUEST", "MAX_PROMPT_CHARS",
    "AigcMeta",
    "EpisodeRequest", "EpisodeResult", "ReferencePack",
    "SkylarkAgentV2WithRefClient",
    "SkylarkAuditError", "SkylarkError", "SkylarkRetryable", "SkylarkTimeout",
    "ChunkedEpisodeRequest", "render_chunked_episode",
    "should_chunk", "split_prompt_by_act",
    "REQ_KEY_CANDIDATES", "ReqKeyResolver",
    "Shot", "SplicePlan",
    "build_splice_plan", "compose_with_ffmpeg", "dump_plan",
    "extract_shots", "load_plan", "replace_shot",
    "CharacterReference", "SceneReference",
]
