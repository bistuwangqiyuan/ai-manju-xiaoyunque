"""Custom user-supplied style → dynamic genre.yaml generator (V10 §1.1).

Workflow:
    1. User uploads 3-8 reference images via ``POST /api/styles``.
    2. We compute a fingerprint:
        - Colour histogram (HSV, 8×4×4) → dominant palette
        - Optional CLIP image embedding (if open_clip + torch installed)
        - SHA-1 of concatenated image bytes for deterministic style_id
    3. The fingerprint is reduced to:
        - 5 hex palette colours
        - a textual ``style_lock_prompt`` (English tags)
        - a ``signature_marks`` list (visual cues)
    4. We materialise ``config/genres/custom/<style_id>.yaml`` so the orchestrator
       and ``GET /api/genres`` pick it up transparently.

The module degrades gracefully:
    - PIL absent → 5 evenly-distributed default palette colours
    - open_clip absent → no embedding stored (tags still emitted)
"""
from __future__ import annotations

import hashlib
import io
import json
import pathlib
from collections import Counter
from dataclasses import dataclass, field, asdict
from typing import Any

import yaml

_REPO = pathlib.Path(__file__).resolve().parents[2]
CUSTOM_DIR = _REPO / "config" / "genres" / "custom"
CUSTOM_DIR.mkdir(parents=True, exist_ok=True)
CUSTOM_EMBED_DIR = _REPO / "data" / "custom_styles"
CUSTOM_EMBED_DIR.mkdir(parents=True, exist_ok=True)


# Style tag dictionary keyed on dominant hue ranges (HSV degrees)
_HUE_TAGS = [
    (0, 15,    "warm crimson", "drama"),
    (15, 45,   "amber gold",   "ancient"),
    (45, 70,   "luminous yellow", "fantasy"),
    (70, 170,  "verdant green",  "naturalistic"),
    (170, 220, "cyan turquoise", "futuristic"),
    (220, 285, "indigo violet",  "mystical"),
    (285, 340, "magenta rose",   "romantic"),
    (340, 360, "warm crimson",   "drama"),
]

_SAT_TAGS = [
    (0.0, 0.20, "monochrome",        "minimal palette"),
    (0.20, 0.50, "muted desaturated", "vintage"),
    (0.50, 0.80, "rich saturated",   "cinematic"),
    (0.80, 1.01, "vivid neon",       "stylized"),
]

_VAL_TAGS = [
    (0.0, 0.30, "deep shadow",   "noir"),
    (0.30, 0.60, "balanced",     "natural"),
    (0.60, 0.85, "soft pastel",  "lyrical"),
    (0.85, 1.01, "high-key bright", "airy"),
]


@dataclass
class CustomStyleFingerprint:
    style_id: str
    name: str
    palette_hex: list[str] = field(default_factory=list)
    style_tags: list[str] = field(default_factory=list)
    signature_marks: list[str] = field(default_factory=list)
    style_lock_prompt: str = ""
    negative_prompt: str = ""
    dominant_hue_deg: float = 0.0
    mean_saturation: float = 0.0
    mean_value: float = 0.0
    n_reference_images: int = 0
    clip_embedding: list[float] | None = None
    user_id: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# ---------------------------------------------------------------------------
# Colour analysis (PIL optional)
# ---------------------------------------------------------------------------
def _safe_open_image(blob: bytes):
    try:
        from PIL import Image  # type: ignore
        img = Image.open(io.BytesIO(blob)).convert("RGB")
        img.thumbnail((256, 256))
        return img
    except Exception:
        return None


def _rgb_to_hsv(r: int, g: int, b: int) -> tuple[float, float, float]:
    rf, gf, bf = r / 255.0, g / 255.0, b / 255.0
    mx, mn = max(rf, gf, bf), min(rf, gf, bf)
    d = mx - mn
    if d == 0:
        h = 0.0
    elif mx == rf:
        h = (60 * ((gf - bf) / d) + 360) % 360
    elif mx == gf:
        h = 60 * ((bf - rf) / d) + 120
    else:
        h = 60 * ((rf - gf) / d) + 240
    s = 0.0 if mx == 0 else d / mx
    v = mx
    return h, s, v


def _analyse_pixels(images: list[bytes]) -> tuple[list[tuple[int, int, int]], float, float, float]:
    """Return (top-5 RGB tuples, mean H, mean S, mean V)."""
    counter: Counter = Counter()
    h_sum = s_sum = v_sum = 0.0
    px_count = 0
    for blob in images:
        img = _safe_open_image(blob)
        if img is None:
            continue
        pixels = list(img.getdata())
        for r, g, b in pixels:
            # quantise to 32 buckets per channel
            key = (r >> 3 << 3, g >> 3 << 3, b >> 3 << 3)
            counter[key] += 1
            h, s, v = _rgb_to_hsv(r, g, b)
            h_sum += h
            s_sum += s
            v_sum += v
            px_count += 1
    if px_count == 0:
        return _DEFAULT_PALETTE_RGB, 30.0, 0.5, 0.6
    top = [c for c, _ in counter.most_common(5)]
    if len(top) < 5:
        top += _DEFAULT_PALETTE_RGB[: 5 - len(top)]
    return top, h_sum / px_count, s_sum / px_count, v_sum / px_count


_DEFAULT_PALETTE_RGB = [
    (220, 180, 130), (170, 90, 60), (60, 80, 110),
    (200, 200, 200), (40, 40, 50),
]


def _to_hex(rgb: tuple[int, int, int]) -> str:
    return "#{:02X}{:02X}{:02X}".format(*rgb)


def _tag_for_range(value: float, table) -> tuple[str, str]:
    for lo, hi, t, s in table:
        if lo <= value < hi:
            return t, s
    return table[-1][2], table[-1][3]


# ---------------------------------------------------------------------------
# Optional CLIP embedding
# ---------------------------------------------------------------------------
def _maybe_clip_embed(images: list[bytes]) -> list[float] | None:
    try:
        import torch  # type: ignore
        import open_clip  # type: ignore
        from PIL import Image  # type: ignore
    except Exception:
        return None
    try:
        model, _, preprocess = open_clip.create_model_and_transforms(
            "ViT-B-32", pretrained="laion2b_s34b_b79k"
        )
        model.eval()
        embs = []
        with torch.no_grad():
            for blob in images:
                img = Image.open(io.BytesIO(blob)).convert("RGB")
                x = preprocess(img).unsqueeze(0)
                e = model.encode_image(x).cpu().numpy().flatten().tolist()
                embs.append(e)
        if not embs:
            return None
        n = len(embs[0])
        avg = [sum(e[i] for e in embs) / len(embs) for i in range(n)]
        norm = sum(v * v for v in avg) ** 0.5
        return [v / norm for v in avg] if norm > 0 else avg
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Main API
# ---------------------------------------------------------------------------
def fingerprint_style(
    images: list[bytes],
    *,
    name: str,
    user_id: int | None = None,
    include_clip: bool = True,
) -> CustomStyleFingerprint:
    if not images:
        raise ValueError("at least one reference image required")
    # Deterministic id
    h = hashlib.sha1()
    for blob in images:
        h.update(blob)
        h.update(b"||")
    style_id = "custom_" + h.hexdigest()[:12]

    top_rgb, hue, sat, val = _analyse_pixels(images)
    palette_hex = [_to_hex(rgb) for rgb in top_rgb]
    hue_tag, hue_keyword = _tag_for_range(hue, _HUE_TAGS)
    sat_tag, sat_keyword = _tag_for_range(sat, _SAT_TAGS)
    val_tag, val_keyword = _tag_for_range(val, _VAL_TAGS)

    style_tags = list(dict.fromkeys([hue_tag, sat_tag, val_tag, hue_keyword,
                                     sat_keyword, val_keyword]))
    style_lock_prompt = (
        f"{hue_tag} dominant palette, {sat_tag} colors, {val_tag} lighting, "
        f"{sat_keyword} {hue_keyword} {val_keyword} cinematic short-drama frame, "
        "consistent character look across shots, no style drift, "
        "9:16 vertical composition"
    )
    negative_prompt = "blurry, deformed, extra fingers, watermark, low quality, oversaturated"

    signature_marks = [
        f"dominant tone {hue_tag}",
        f"{sat_keyword} chroma",
        f"{val_keyword} luminance",
    ]

    clip_emb = _maybe_clip_embed(images) if include_clip else None

    return CustomStyleFingerprint(
        style_id=style_id,
        name=name,
        palette_hex=palette_hex,
        style_tags=style_tags,
        signature_marks=signature_marks,
        style_lock_prompt=style_lock_prompt,
        negative_prompt=negative_prompt,
        dominant_hue_deg=round(hue, 2),
        mean_saturation=round(sat, 4),
        mean_value=round(val, 4),
        n_reference_images=len(images),
        clip_embedding=clip_emb,
        user_id=user_id,
    )


def materialise_genre_yaml(fp: CustomStyleFingerprint) -> pathlib.Path:
    """Write ``config/genres/custom/<style_id>.yaml`` so it loads via load_genres()."""
    payload = {
        "id": fp.style_id,
        "name_zh": fp.name,
        "name_en": fp.name,
        "description": f"用户自定义画风（基于 {fp.n_reference_images} 张参考图）",
        "style_id": fp.style_id,
        "aspect_ratio": "9:16",
        "default_episodes": 10,
        "default_duration_per_episode_s": 80,
        "preferred_resolution": "1080x1920",
        "language": "Chinese",
        "voice_pack": "default",
        "bgm_mood": "custom",
        "platform_preset": ["douyin"],
        "palette": {"primary": fp.palette_hex},
        "character_archetypes": [],
        "scenes": [],
        "signature_marks": fp.signature_marks,
        "sample_themes": [],
        "style_lock_prompt": fp.style_lock_prompt,
        "negative_prompt": fp.negative_prompt,
        "_custom_owner_user_id": fp.user_id,
        "_style_tags": fp.style_tags,
    }
    path = CUSTOM_DIR / f"{fp.style_id}.yaml"
    path.write_text(yaml.safe_dump(payload, allow_unicode=True, sort_keys=False),
                    encoding="utf-8")

    # Persist embedding separately to keep the yaml small.
    if fp.clip_embedding is not None:
        emb_path = CUSTOM_EMBED_DIR / f"{fp.style_id}.json"
        emb_path.write_text(json.dumps({"embedding": fp.clip_embedding}, ensure_ascii=False),
                            encoding="utf-8")

    # Invalidate genre cache so next load picks it up
    try:
        from . import load_genres
        load_genres.cache_clear()
    except Exception:
        pass
    return path


def list_custom_styles(user_id: int | None = None) -> list[dict[str, Any]]:
    out = []
    for fp in sorted(CUSTOM_DIR.glob("custom_*.yaml")):
        try:
            data = yaml.safe_load(fp.read_text(encoding="utf-8")) or {}
        except Exception:
            continue
        if user_id is not None and data.get("_custom_owner_user_id") not in (None, user_id):
            continue
        out.append({
            "style_id": data.get("id"),
            "name": data.get("name_zh"),
            "palette": data.get("palette", {}).get("primary", []),
            "style_tags": data.get("_style_tags", []),
            "owner_user_id": data.get("_custom_owner_user_id"),
        })
    return out


def delete_custom_style(style_id: str, user_id: int | None = None) -> bool:
    path = CUSTOM_DIR / f"{style_id}.yaml"
    if not path.exists():
        return False
    if user_id is not None:
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except Exception:
            data = {}
        if data.get("_custom_owner_user_id") not in (None, user_id):
            return False
    path.unlink()
    emb_path = CUSTOM_EMBED_DIR / f"{style_id}.json"
    if emb_path.exists():
        emb_path.unlink()
    try:
        from . import load_genres
        load_genres.cache_clear()
    except Exception:
        pass
    return True


__all__ = [
    "CustomStyleFingerprint",
    "fingerprint_style",
    "materialise_genre_yaml",
    "list_custom_styles",
    "delete_custom_style",
    "CUSTOM_DIR",
    "CUSTOM_EMBED_DIR",
]
