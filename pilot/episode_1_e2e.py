"""End-to-end pilot — render Episode 1《荒寺月夜》80s.

Usage:
    python pilot/episode_1_e2e.py [--episode ep01] [--skip-assets] [--dry-run]

After the 2026-05 official Skylark Agent 2.0 doc was confirmed:
    - req_key locked to "pippit_iv2v_v20_cvtob_with_vinput" (no fallback)
    - reference assets flattened to img_url_list[] (cap 50)
    - duration enum: ～15s / ～30s / 40～60s  → 80s 集 = ep01 单 chunk = 60s 上限
    - duration > 60s → 自动走 chunk_renderer (ep04 / ep08 / ep09 = 90s)

For ep01 (80s plan): we render in 2 chunks (50s + 30s) and crossfade.
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import pathlib
import sys

import yaml


_REPO = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO))


from src.shell3_skylark_engine import (
    AigcMeta,
    ChunkedEpisodeRequest,
    DURATION_MAX_SECONDS,
    EpisodeRequest,
    ReferencePack,
    SkylarkAgentV2WithRefClient,
    build_splice_plan,
    compose_with_ffmpeg,
    dump_plan,
    extract_shots,
    render_chunked_episode,
    should_chunk,
    split_prompt_by_act,
)


_log = logging.getLogger("pilot")


# ---------------------------------------------------------------------------

def _load_episode(ep_id: str) -> dict:
    path = _REPO / "prompts" / "episodes" / "ep01-ep10.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    for ep in data["episodes"]:
        if ep["episode_id"] == ep_id:
            return ep
    raise KeyError(ep_id)


def _load_character(char_id: str) -> dict:
    path = _REPO / "prompts" / "characters" / f"{char_id}.yaml"
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _load_scene(scene_id: str) -> dict:
    path = _REPO / "prompts" / "scenes" / f"{scene_id}.yaml"
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _load_style() -> dict:
    path = _REPO / "prompts" / "style" / "ancient_3d_guoman.yaml"
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _render_skylark_prompt(episode: dict, characters: dict, scenes: dict, style: dict) -> str:
    """Compose the canonical Skylark-friendly prompt for an episode (≤2000 chars)."""

    char_block = "\n".join(
        _render_character_lock(characters[cid])
        for cid in episode["characters_in_episode"]
    )
    scene_block = "\n".join(
        _render_scene_lock(scenes[sid])
        for sid in episode["scenes_in_episode"]
    )
    shot_block = _render_shot_block(episode.get("shots", []))
    overrides = style.get("episode_overrides", {}).get(episode["episode_id"], {})

    sig = episode["signatures_check"]
    return f"""【画风设定】
{style['prompt_lock']}
本集色调：{overrides.get('palette_bias','')}；附加：{overrides.get('extra_keywords','')}

【人物设定】
{char_block}

【场景设定】
{scene_block}

【三大锁定符号（每镜必查）】
- 聂小倩眉间一点朱砂痣（必现={sig['zhusha_visible']}）
- 聂小倩左肩黑色藤纹（visibility={sig['black_vine_visibility']}）
- 革囊苍白手（{'出现' if sig['white_hand_appears'] else '不出现'}）

【第 {int(episode['episode_id'][2:])} 集分镜】 {episode['title']}（{episode['duration_seconds']}s）
钩子：{episode['hook_3s']}
{shot_block}

【字幕规范】禁止在画面渲染任何文字，字幕由本地 ASS 渲染。
【负面 prompt】{style.get('negative_prompt', '')}
"""


def _render_character_lock(char: dict) -> str:
    bits = [f"- {char['name_zh']}（#{char['id']}）"]
    if char.get("age"):
        bits.append(f"  · {char['age']}岁/{char.get('height_cm','')}cm/{char.get('body','')}")
    for label, key in [("发", "hair"), ("眼", "eye"), ("服", "attire"), ("饰", "accessories")]:
        if char.get(key):
            v = char[key]
            v = "; ".join(v) if isinstance(v, list) else v
            bits.append(f"  · {label}：{v}")
    if char.get("signature_marks"):
        marks = "; ".join(char["signature_marks"]) if isinstance(char["signature_marks"], list) else char["signature_marks"]
        bits.append(f"  · ★ {marks}")
    return "\n".join(bits)


def _render_scene_lock(scene: dict) -> str:
    bits = [f"- {scene['name_zh']}（loc#{scene['id']}）"]
    if scene.get("description"):
        bits.append(f"  · {scene['description'].strip().split(chr(10))[0]}")
    if scene.get("palette"):
        bits.append(f"  · 色调：{scene['palette']}")
    return "\n".join(bits)


def _render_shot_block(shots: list[dict]) -> str:
    if not shots:
        return "（分镜略，由 Shell 1 LLM 管线产出）"
    lines = []
    for s in shots:
        title = f"[镜{s['shot_id']}/{s['duration_seconds']}s {s.get('type','')}] {s.get('camera_motion','')}"
        bits = [title, f"动作：{s['action_desc']}"]
        if s.get("dialogue"):
            bits.append(f"对：{s['dialogue']}")
        if s.get("voiceover"):
            bits.append(f"白：{s['voiceover']}")
        lines.append("\n".join(bits))
    return "\n\n".join(lines)


# ---------------------------------------------------------------------------

def _gather_references(episode: dict) -> ReferencePack:
    """Aggregate character + scene + style references into the flat官方契约."""

    char_imgs: list[str] = []
    for cid in episode["characters_in_episode"]:
        manifest = _REPO / "data" / "characters" / cid / "manifest.json"
        if not manifest.exists():
            raise FileNotFoundError(
                f"Missing character asset manifest for {cid}; run "
                f"`python -m src.shell2_character_assets.build_asset {cid}` first."
            )
        data = json.loads(manifest.read_text(encoding="utf-8"))
        # Top 8 per character to stay under the 50-img cap (5 chars × 8 = 40)
        char_imgs.extend(data["reference_image_urls"][:8])

    scene_imgs: list[str] = []
    for sid in episode["scenes_in_episode"]:
        scene_dir = _REPO / "data" / "scenes" / sid
        scene_imgs.extend(p.as_uri() for p in sorted(scene_dir.glob("*.jpg"))[:3])

    style_imgs: list[str] = []
    style_dir = _REPO / "data" / "style" / "reference_jpgs"
    if style_dir.exists():
        style_imgs.extend(p.as_uri() for p in sorted(style_dir.glob("*.jpg"))[:5])

    return ReferencePack(
        character_images=char_imgs,
        scene_images=scene_imgs,
        style_images=style_imgs,
    )


# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--episode", default="ep01")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--skip-assets", action="store_true",
                        help="Use empty reference packs (debug only)")
    parser.add_argument("--output", default=None)
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s [%(name)s] %(message)s")

    style = _load_style()
    episode = _load_episode(args.episode)
    characters = {cid: _load_character(cid) for cid in episode["characters_in_episode"]}
    scenes = {sid: _load_scene(sid) for sid in episode["scenes_in_episode"]}

    prompt = _render_skylark_prompt(episode, characters, scenes, style)
    if len(prompt) > 2000:
        _log.warning("prompt %d chars > 2000官方上限，自动截断角色块尾", len(prompt))
        prompt = prompt[:2000]

    if args.dry_run:
        _log.info("=== dry-run prompt for %s ===", args.episode)
        print(prompt)
        print()
        _log.info("Prompt chars: %d (cap 2000)", len(prompt))
        _log.info("Episode duration plan: %ds  (cap %ds per chunk)",
                  episode["duration_seconds"], DURATION_MAX_SECONDS)
        if should_chunk(episode["duration_seconds"]):
            _log.info("→ will dispatch via render_chunked_episode (2 chunks + crossfade)")
        else:
            _log.info("→ single-chunk render via SkylarkAgentV2WithRefClient.render_episode")
        _log.info("Premium tier: %s", episode["premium_tier"])
        return 0

    # ------------------------------------------------------------------
    refs = ReferencePack() if args.skip_assets else _gather_references(episode)

    aigc = AigcMeta(
        content_producer=os.environ.get("AIGC_CONTENT_PRODUCER", ""),
        producer_id=f"{args.episode}_{os.environ.get('RUN_ID', 'pilot')}",
        content_propagator=os.environ.get("AIGC_CONTENT_PROPAGATOR", ""),
        propagate_id=os.environ.get("AIGC_PROPAGATE_ID", ""),
    )
    client = SkylarkAgentV2WithRefClient(aigc_meta=aigc)

    # ------------------------------------------------------------------
    if should_chunk(episode["duration_seconds"]):
        prompt_a, prompt_b = split_prompt_by_act(prompt)
        request = ChunkedEpisodeRequest(
            prompt_a=prompt_a,
            prompt_b=prompt_b,
            references=refs,
            ratio="9:16",
            duration_a="40～60s",
            duration_b="40～60s",
            language="Chinese",
            enable_watermark=False,
        )
        result = render_chunked_episode(client, request, ep_id=args.episode, aigc_meta=aigc)
    else:
        request = EpisodeRequest(
            prompt=prompt,
            references=refs,
            ratio="9:16",
            duration="40～60s",
            language="Chinese",
            enable_watermark=False,
        )
        result = client.render_episode(request, ep_id=args.episode)

    _log.info("Skylark task=%s  archived=%s  aigc_tagged=%s  dur=%.1fs",
              result.task_id, result.archived_video_path,
              result.aigc_meta_tagged, result.output_duration_seconds)

    # ------------------------------------------------------------------
    splice_plan = build_splice_plan(result, args.episode, episode.get("shots", []))
    extract_shots(splice_plan,
                  _REPO / "data" / "episodes" / args.episode / "shots")
    plan_path = _REPO / "data" / "episodes" / args.episode / "plan.json"
    dump_plan(splice_plan, plan_path)
    _log.info("Splice plan → %s (%d shots)", plan_path, len(splice_plan.shots))

    output = pathlib.Path(args.output or
                          _REPO / "data" / "episodes" / args.episode / "final.mp4")
    compose_with_ffmpeg(splice_plan, output)
    _log.info("Final cut → %s", output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
