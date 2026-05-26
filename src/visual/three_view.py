"""V10 §4.1 — Three-view character sheets.

For every character we render *exactly three* views (front · 3/4 side · back)
using the same fixed seed + same anchor prompt, so the resulting sheets are
visually consistent (clothing details / hairstyle / accessory match across
all three angles).
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any


VIEW_DEFS = [
    {"view": "front",     "view_prompt": "full body, front view, centered, T-pose, neutral expression"},
    {"view": "three_quarter", "view_prompt": "full body, 3/4 side view, slight turn to camera right, neutral expression"},
    {"view": "back",      "view_prompt": "full body, back view, centered, T-pose"},
]


@dataclass
class CharacterSheet:
    character_name: str
    seed: int
    anchor_prompt: str
    views: list[dict[str, Any]] = field(default_factory=list)
    style_lock_prompt: str = ""
    palette_hex: list[str] = field(default_factory=list)


def derive_seed(character_name: str, style_id: str) -> int:
    """Deterministic 32-bit seed so the same (character, style) re-produces."""
    h = hashlib.sha1(f"{character_name}::{style_id}::v10".encode("utf-8")).digest()
    return int.from_bytes(h[:4], "big") & 0x7FFFFFFF


def build_three_view_prompts(
    *,
    character_name: str,
    character_description: str,
    style_id: str,
    style_lock_prompt: str = "",
    palette_hex: list[str] | None = None,
    negative_prompt: str = "blurry, deformed, extra fingers, low quality",
) -> CharacterSheet:
    """Return a CharacterSheet whose ``views`` list is ready for batch generation.

    The orchestrator picks each view dict and feeds it to Seedream + InfiniteYou,
    plumbing the ``seed`` and ``anchor_prompt`` so the resulting images form a
    semantically grouped sheet.
    """
    seed = derive_seed(character_name, style_id)
    anchor_prompt = (
        f"{character_description}, consistent character look, "
        f"{style_lock_prompt}, detailed costume, anatomically correct, "
        "single character, plain neutral background, soft studio lighting"
    ).strip(", ")

    views = []
    for vd in VIEW_DEFS:
        views.append({
            "view": vd["view"],
            "prompt": f"{anchor_prompt}, {vd['view_prompt']}",
            "negative_prompt": negative_prompt,
            "seed": seed,
            "aspect_ratio": "2:3",
            "size": "768x1152",
            "group_id": f"{character_name}__sheet",
        })

    return CharacterSheet(
        character_name=character_name,
        seed=seed,
        anchor_prompt=anchor_prompt,
        views=views,
        style_lock_prompt=style_lock_prompt,
        palette_hex=palette_hex or [],
    )


def consistency_check(generated_paths: list[str | "pathlib.Path"]) -> dict:
    """Sanity-check that all 3 generated views still match each other.

    Uses pHash distance (when imagehash is installed) as a proxy for visual
    consistency.  Returns a per-pair distance dict + an aggregate score.
    """
    import pathlib
    try:
        from PIL import Image  # type: ignore
        import imagehash  # type: ignore
    except Exception:
        return {"available": False, "reason": "imagehash/PIL not installed"}
    paths = [pathlib.Path(p) for p in generated_paths]
    if len(paths) < 2:
        return {"available": True, "ok": True, "n_views": len(paths)}
    hashes = [imagehash.phash(Image.open(p)) for p in paths]
    pairs = {}
    for i in range(len(paths)):
        for j in range(i + 1, len(paths)):
            pairs[f"{i}-{j}"] = int(hashes[i] - hashes[j])
    avg = sum(pairs.values()) / max(len(pairs), 1)
    return {
        "available": True,
        "ok": avg < 28,                # pHash > 28 typically means style drift
        "pair_distances": pairs,
        "avg_distance": round(avg, 2),
        "n_views": len(paths),
    }


__all__ = [
    "CharacterSheet",
    "VIEW_DEFS",
    "derive_seed",
    "build_three_view_prompts",
    "consistency_check",
]
