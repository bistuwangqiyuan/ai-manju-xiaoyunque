"""Two-chunk renderer for episodes that exceed the 60-second官方 cap.

Per official 2026-05 docs, `duration` is an enum of:
    ["～15s", "～30s", "40～60s"]

For episodes > 60s (in our plan: ep04 = 90s, ep08 = 90s, ep09 = 90s) we split
the prompt at a natural beat (typically the 高潮 / 反转 transition) and submit
two sequential generations:

    chunk_a (前半，0 → ~45s)   →  archive last frame as `tail_a.jpg`
    chunk_b (后半，~45s → end) →  add `tail_a.jpg` as the FIRST img_url_list
                                  entry so chunk_b starts visually
                                  continuous with chunk_a

Then ffmpeg-concat the two chunks. The boundary is a single-frame cross-fade
to mask any micro-flicker.

Cost impact: 2 × Skylark calls per >60s episode (~¥54-80 vs ¥27-40).
"""
from __future__ import annotations

import logging
import pathlib
import subprocess
from dataclasses import dataclass
from typing import Optional

from .client import (
    AigcMeta,
    DURATION_VALUES,
    EpisodeRequest,
    EpisodeResult,
    ReferencePack,
    SkylarkAgentV2WithRefClient,
)


_log = logging.getLogger(__name__)


@dataclass
class ChunkedEpisodeRequest:
    """A request for an episode that needs ≥ 2 chunks because total > 60s."""

    prompt_a: str                   # 前半 prompt（含人物设定块 + 钩子 + 铺垫）
    prompt_b: str                   # 后半 prompt（含人物设定块 + 高潮 + 反转 + 悬念）
    references: ReferencePack
    duration_a: str = "40～60s"     # 通常取最长
    duration_b: str = "40～60s"
    ratio: str = "9:16"
    language: str = "Chinese"
    enable_watermark: bool = False
    crossfade_duration: float = 0.25  # 边界过渡时长


def render_chunked_episode(
    client: SkylarkAgentV2WithRefClient,
    request: ChunkedEpisodeRequest,
    *,
    ep_id: str,
    out_dir: str | pathlib.Path = None,
    aigc_meta: AigcMeta | None = None,
) -> EpisodeResult:
    """Render an episode in 2 chunks and concat into one mp4."""

    if request.duration_a not in DURATION_VALUES:
        raise ValueError(f"duration_a={request.duration_a!r} invalid")
    if request.duration_b not in DURATION_VALUES:
        raise ValueError(f"duration_b={request.duration_b!r} invalid")

    out_dir = pathlib.Path(out_dir or f"./data/episodes/{ep_id}")
    out_dir.mkdir(parents=True, exist_ok=True)

    # ----- chunk A -----
    req_a = EpisodeRequest(
        prompt=request.prompt_a,
        references=request.references,
        ratio=request.ratio,
        duration=request.duration_a,
        language=request.language,
        enable_watermark=request.enable_watermark,
    )
    result_a = client.render_episode(req_a, ep_id=ep_id, chunk_id="a")
    _log.info("[%s] chunk A done — %.2fs", ep_id, result_a.output_duration_seconds)

    # ----- extract tail frame of chunk A for continuity -----
    tail_jpg = out_dir / "tail_a.jpg"
    _extract_tail_frame(result_a.archived_video_path, tail_jpg)

    # ----- chunk B (插入 tail_jpg 作为第一张参考图，保证视觉续片) -----
    refs_b = ReferencePack(
        character_images=[tail_jpg.as_uri()] + list(request.references.character_images),
        scene_images=request.references.scene_images,
        style_images=request.references.style_images,
        video_references=request.references.video_references,
    )
    req_b = EpisodeRequest(
        prompt=request.prompt_b,
        references=refs_b,
        ratio=request.ratio,
        duration=request.duration_b,
        language=request.language,
        enable_watermark=request.enable_watermark,
    )
    result_b = client.render_episode(req_b, ep_id=ep_id, chunk_id="b")
    _log.info("[%s] chunk B done — %.2fs", ep_id, result_b.output_duration_seconds)

    # ----- concat with crossfade -----
    output = out_dir / "full.mp4"
    _concat_with_crossfade(
        result_a.archived_video_path,
        result_b.archived_video_path,
        output,
        crossfade=request.crossfade_duration,
    )

    total_duration = result_a.output_duration_seconds + result_b.output_duration_seconds \
                     - request.crossfade_duration

    return EpisodeResult(
        task_id=f"{result_a.task_id}+{result_b.task_id}",
        video_url="",
        archived_video_path=str(output),
        input_video_duration_sum=result_a.input_video_duration_sum + result_b.input_video_duration_sum,
        output_duration_seconds=total_duration,
        aigc_meta_tagged=result_a.aigc_meta_tagged and result_b.aigc_meta_tagged,
        raw_response={"chunk_a": result_a.raw_response, "chunk_b": result_b.raw_response},
    )


# ---------------------------------------------------------------------------

def _extract_tail_frame(video_path: str, out_jpg: pathlib.Path) -> None:
    out_jpg.parent.mkdir(parents=True, exist_ok=True)
    # 用 -sseof -0.5 取倒数 0.5s 的一帧（最稳的"末帧"做法）
    cmd = [
        "ffmpeg", "-y",
        "-sseof", "-0.5",
        "-i", str(video_path),
        "-frames:v", "1",
        "-q:v", "2",
        str(out_jpg),
    ]
    _log.debug("extract tail frame: %s", " ".join(cmd))
    subprocess.run(cmd, check=True, capture_output=True)


def _concat_with_crossfade(
    a: str, b: str, output: pathlib.Path,
    *, crossfade: float = 0.25,
) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    # xfade requires offset = duration(a) - crossfade
    probe_a = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", a],
        check=True, capture_output=True, text=True,
    )
    dur_a = float(probe_a.stdout.strip())
    offset = max(0.0, dur_a - crossfade)
    cmd = [
        "ffmpeg", "-y",
        "-i", a, "-i", b,
        "-filter_complex",
        f"[0:v][1:v]xfade=transition=fade:duration={crossfade}:offset={offset}[v];"
        f"[0:a][1:a]acrossfade=d={crossfade}[a]",
        "-map", "[v]", "-map", "[a]",
        "-c:v", "libx264", "-preset", "slow", "-crf", "18", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k",
        str(output),
    ]
    _log.info("ffmpeg concat with crossfade: %s", " ".join(cmd))
    subprocess.run(cmd, check=True)


# ---------------------------------------------------------------------------

def should_chunk(episode_total_seconds: float, threshold: float = 60.0) -> bool:
    """Decide whether an episode exceeds the single-call cap."""

    return episode_total_seconds > threshold


def split_prompt_by_act(prompt: str) -> tuple[str, str]:
    """Heuristic prompt splitter for episodes >60s.

    Looks for the 「【高潮 / 反转 / 悬念】」 section break in the Skylark-friendly
    prompt and splits there. Both halves keep the full 人物 + 场景 + 风格设定
    block so the chunks render with the same identity / wardrobe lock.
    """

    markers = ("【高潮", "[高潮", "高潮 25", "高潮25", "高潮：")
    for marker in markers:
        idx = prompt.find(marker)
        if idx > 200:
            return prompt[:idx], prompt[idx:]
    # fallback: midpoint
    mid = len(prompt) // 2
    return prompt[:mid], prompt[mid:]
