"""Asset library endpoints — characters / scenes / expressions / actions / wardrobe.

Requirement doc §3 + §4.
"""
from __future__ import annotations

import json
import pathlib
from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from ..db import User, get_db  # noqa: F401
from ..security import get_current_user  # noqa: F401


router = APIRouter(prefix="/library", tags=["library"])

_REPO = pathlib.Path(__file__).resolve().parents[3]


def _read_char_manifest(char_id: str) -> dict | None:
    path = _REPO / "data" / "characters" / char_id / "manifest.json"
    if not path.exists():
        # Fallback: read prompts/characters yaml as a "stub manifest"
        ystub = _REPO / "prompts" / "characters" / f"{char_id}.yaml"
        if ystub.exists():
            import yaml
            data = yaml.safe_load(ystub.read_text(encoding="utf-8")) or {}
            return {
                "char_id": data.get("id", char_id),
                "name_zh": data.get("name_zh", char_id),
                "reference_image_urls": data.get("preset_canonical_images", []),
                "canonical_image_url": (data.get("preset_canonical_images") or [None])[0],
                "signature_marks": data.get("signature_marks", []),
                "metadata": data,
                "stub": True,
            }
        return None
    return json.loads(path.read_text(encoding="utf-8"))


@router.get("/characters")
def list_characters() -> list[dict[str, Any]]:
    """Catalog of available character templates (each genre seeds its archetypes)."""
    out: list[dict[str, Any]] = []
    char_root = _REPO / "data" / "characters"
    if char_root.exists():
        for p in sorted(char_root.iterdir()):
            if p.is_dir() and (p / "manifest.json").exists():
                m = _read_char_manifest(p.name) or {}
                out.append(m)

    # Add prompts/characters/*.yaml as stubs (especially useful in mock mode)
    yaml_root = _REPO / "prompts" / "characters"
    seen_ids = {c.get("char_id") for c in out}
    if yaml_root.exists():
        for yp in sorted(yaml_root.glob("*.yaml")):
            if yp.stem in seen_ids:
                continue
            m = _read_char_manifest(yp.stem)
            if m:
                out.append(m)
    return out


@router.get("/characters/{char_id}")
def get_character(char_id: str) -> dict[str, Any]:
    m = _read_char_manifest(char_id)
    if not m:
        raise HTTPException(status_code=404, detail="角色不存在")

    char_dir = _REPO / "data" / "characters" / char_id
    expressions = None
    actions = None
    wardrobe = None
    try:
        ep = char_dir / "expressions" / "sheet.json"
        if ep.exists():
            expressions = json.loads(ep.read_text(encoding="utf-8"))
        ap = char_dir / "actions" / "sheet.json"
        if ap.exists():
            actions = json.loads(ap.read_text(encoding="utf-8"))
        wp = char_dir / "wardrobe" / "sheet.json"
        if wp.exists():
            wardrobe = json.loads(wp.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {
        "character": m,
        "expressions": expressions,
        "actions": actions,
        "wardrobe": wardrobe,
    }


@router.get("/scenes")
def list_scenes(category: str | None = None) -> list[dict[str, Any]]:
    from src.shell2_character_assets.scene_library import SceneLibrary

    lib = SceneLibrary(data_dir=str(_REPO / "data" / "scenes"))
    if not list(lib.list()):  # empty, seed once from genres
        lib.seed_from_genres()
    return [s.to_dict() for s in lib.list(category=category)]


@router.get("/scenes/{scene_id}")
def get_scene(scene_id: str) -> dict[str, Any]:
    from src.shell2_character_assets.scene_library import SceneLibrary

    lib = SceneLibrary(data_dir=str(_REPO / "data" / "scenes"))
    sc = lib.get(scene_id)
    if not sc:
        raise HTTPException(status_code=404, detail="场景不存在")
    return sc.to_dict()


@router.get("/expressions")
def list_expression_keys() -> list[dict[str, str]]:
    from src.shell2_character_assets.expression_library import EMOTIONS

    return [
        {"key": k, "name_zh": zh, "description": d}
        for (k, zh, d) in EMOTIONS
    ]


@router.get("/actions")
def list_action_keys() -> list[dict[str, str]]:
    from src.shell2_character_assets.action_library import ACTIONS

    return [
        {"key": k, "name_zh": zh, "description": d}
        for (k, zh, d) in ACTIONS
    ]


@router.get("/wardrobe")
def list_wardrobe_keys() -> list[dict[str, str]]:
    from src.shell2_character_assets.wardrobe_swap import COSTUME_PRESETS

    return [
        {"key": k, "name_zh": zh, "description": d}
        for (k, zh, d) in COSTUME_PRESETS
    ]
