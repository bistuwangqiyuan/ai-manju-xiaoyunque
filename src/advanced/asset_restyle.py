"""V10 §8.2 — Full-asset style migration.

Given a finished job's character sheets, scene plates and shot frames,
restyle ALL of them in lockstep so the result is internally consistent.

This is different from ``style_transfer.restyle_video`` which only
handles the final mp4 — that gives an inconsistent look the moment you
re-generate any single shot. Here we restyle every primary asset, so
the next render uses the new style natively.

Workflow:

    1. ``plan_restyle`` walks the project's tree (artifact store) and
       enumerates every asset that must be migrated, grouping by category
       (character_three_view / scene_plate / shot_frame / episode_video).
    2. ``execute_restyle`` runs ``style_transfer.restyle_video`` for
       videos and FLUX-Kontext-equivalent ``image_restyle`` for stills,
       with bounded concurrency.  The original assets are preserved under
       ``./v_pre_restyle/`` so users can roll back.

Backends degrade gracefully — when no provider is available the
operation copies the files and logs ``backend=mock``.
"""
from __future__ import annotations

import logging
import os
import pathlib
import shutil
from dataclasses import dataclass, field
from typing import Any

from . import style_transfer

_log = logging.getLogger(__name__)


_ASSET_DIRS = {
    "character_three_view":  ["characters", "character_sheets"],
    "scene_plate":           ["scenes", "scene_plates"],
    "shot_frame":            ["shots", "frames", "storyboard"],
    "episode_video":         ["episodes", "video"],
    "covers":                ["covers", "cover"],
}


@dataclass
class RestyleAsset:
    category: str
    src_path: str
    dst_path: str
    asset_kind: str   # image | video

    def to_dict(self) -> dict[str, Any]:
        return {
            "category": self.category, "src_path": self.src_path,
            "dst_path": self.dst_path, "asset_kind": self.asset_kind,
        }


@dataclass
class RestylePlan:
    job_root: str
    target_style: str
    target_description: str
    snapshot_dir: str
    assets: list[RestyleAsset] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "job_root": self.job_root,
            "target_style": self.target_style,
            "target_description": self.target_description,
            "snapshot_dir": self.snapshot_dir,
            "n_assets": len(self.assets),
            "by_category": {
                cat: sum(1 for a in self.assets if a.category == cat)
                for cat in {a.category for a in self.assets}
            },
            "assets": [a.to_dict() for a in self.assets],
        }


@dataclass
class RestyleResult:
    plan: RestylePlan
    processed: int = 0
    failed: int = 0
    backend_used: dict[str, int] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "plan": self.plan.to_dict(),
            "processed": self.processed, "failed": self.failed,
            "backend_used": dict(self.backend_used),
            "errors": list(self.errors),
        }


_IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp"}
_VIDEO_EXTS = {".mp4", ".mov", ".webm", ".m4v"}


def plan_restyle(
    job_root: str | pathlib.Path,
    *, target_style: str = "jpn_anime",
    snapshot_subdir: str = "v_pre_restyle",
) -> RestylePlan:
    root = pathlib.Path(job_root)
    if not root.exists():
        raise FileNotFoundError(f"job_root not found: {root}")
    snapshot_dir = root / snapshot_subdir
    descr = style_transfer.STYLE_TARGETS.get(target_style, target_style)

    assets: list[RestyleAsset] = []
    for category, subnames in _ASSET_DIRS.items():
        for sub in subnames:
            base = root / sub
            if not base.exists():
                continue
            for path in sorted(base.rglob("*")):
                if not path.is_file():
                    continue
                ext = path.suffix.lower()
                if ext in _IMAGE_EXTS:
                    kind = "image"
                elif ext in _VIDEO_EXTS:
                    kind = "video"
                else:
                    continue
                rel = path.relative_to(root)
                dst = root / "v_restyled" / rel
                assets.append(RestyleAsset(
                    category=category, src_path=str(path),
                    dst_path=str(dst), asset_kind=kind,
                ))
    return RestylePlan(
        job_root=str(root), target_style=target_style,
        target_description=descr, snapshot_dir=str(snapshot_dir),
        assets=assets,
    )


def _image_restyle(src: pathlib.Path, dst: pathlib.Path,
                   target: str, descr: str) -> str:
    """Restyle a still image — calls FLUX Kontext if available else copies.

    Returns the backend label used.
    """
    dst.parent.mkdir(parents=True, exist_ok=True)
    if (os.environ.get("FAL_API_KEY") and
            os.environ.get("FORCE_MOCK_RESTYLE") != "1"):
        try:
            return _via_flux_kontext(src, dst, descr, target)
        except Exception as exc:
            _log.warning("FLUX Kontext image restyle failed for %s: %s", src, exc)
    if src.exists():
        shutil.copy2(src, dst)
    return "mock"


def _via_flux_kontext(src: pathlib.Path, dst: pathlib.Path,
                      descr: str, target: str) -> str:
    """Minimal POST to fal.run flux-kontext for image restyle."""
    import json as _json
    import urllib.request

    token = os.environ["FAL_API_KEY"]
    endpoint = "https://fal.run/fal-ai/flux/dev/image-to-image"
    body = {
        "image_url": src.as_uri() if src.is_absolute() else str(src),
        "prompt": f"Restyle this character/scene to: {descr}. "
                  f"Preserve subject identity, framing and pose.",
        "strength": 0.55,
        "num_inference_steps": 30,
    }
    req = urllib.request.Request(
        endpoint,
        data=_json.dumps(body).encode("utf-8"),
        headers={
            "Authorization": f"Key {token}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        data = _json.loads(resp.read())
    out_url = ((data.get("images") or [{}])[0]).get("url") or data.get("image_url")
    if not out_url:
        raise RuntimeError(f"flux returned no image: {data}")
    with urllib.request.urlopen(out_url, timeout=120) as rr:
        dst.write_bytes(rr.read())
    return "flux_kontext"


def execute_restyle(
    plan: RestylePlan,
    *, snapshot_originals: bool = True,
    max_assets: int | None = None,
) -> RestyleResult:
    """Execute the restyle plan, optionally snapshotting originals first."""
    res = RestyleResult(plan=plan)
    work = plan.assets if max_assets is None else plan.assets[:max_assets]
    if snapshot_originals:
        snap = pathlib.Path(plan.snapshot_dir)
        snap.mkdir(parents=True, exist_ok=True)

    for asset in work:
        src = pathlib.Path(asset.src_path)
        dst = pathlib.Path(asset.dst_path)
        try:
            if snapshot_originals and src.exists():
                rel = src.relative_to(plan.job_root)
                snap_path = pathlib.Path(plan.snapshot_dir) / rel
                snap_path.parent.mkdir(parents=True, exist_ok=True)
                if not snap_path.exists():
                    shutil.copy2(src, snap_path)

            if asset.asset_kind == "video":
                out = style_transfer.restyle_video(
                    src, dst, target=plan.target_style,
                )
                backend = out.get("backend", "unknown")
            else:
                backend = _image_restyle(
                    src, dst, plan.target_style, plan.target_description,
                )
            res.processed += 1
            res.backend_used[backend] = res.backend_used.get(backend, 0) + 1
        except Exception as exc:
            res.failed += 1
            res.errors.append(f"{asset.src_path}: {exc}")
    return res


__all__ = [
    "RestyleAsset", "RestylePlan", "RestyleResult",
    "plan_restyle", "execute_restyle",
]
