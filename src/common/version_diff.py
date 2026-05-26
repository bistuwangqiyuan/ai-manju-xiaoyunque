"""V10 §2.3 — three-axis version diff: text · visual · 7-dim score.

Given two :class:`VersionSnapshot` (or any pair of directories) we produce a
machine-readable diff for the front-end "version compare" page:

    {
        "text": { "ep01/screenplay.txt": {"status":"changed",
                                          "diff": [unified-diff-lines]} },
        "visual": { "ep01/shot001.png": {"status":"changed", "phash_hamming": 18,
                                          "abs_diff_pct": 0.235} },
        "scores_7d": { "structure": {"from": 7.4, "to": 8.2, "delta": 0.8} },
        "stats": { "files_changed": 4, "files_added": 1, "files_removed": 0 }
    }

Heavy deps (PIL, ``imagehash``) are optional — the routine degrades to size+sha
comparison.
"""
from __future__ import annotations

import difflib
import hashlib
import pathlib
from typing import Any, Mapping


def _read_text(p: pathlib.Path) -> str:
    try:
        return p.read_text(encoding="utf-8")
    except Exception:
        try:
            return p.read_text(encoding="gbk", errors="ignore")
        except Exception:
            return ""


def _phash_distance(a: pathlib.Path, b: pathlib.Path) -> int | None:
    try:
        from PIL import Image  # type: ignore
        import imagehash  # type: ignore
    except Exception:
        return None
    try:
        ha = imagehash.phash(Image.open(a))
        hb = imagehash.phash(Image.open(b))
        return int(ha - hb)
    except Exception:
        return None


def _abs_diff_pct(a: pathlib.Path, b: pathlib.Path) -> float | None:
    try:
        from PIL import Image, ImageChops  # type: ignore
    except Exception:
        return None
    try:
        ia = Image.open(a).convert("RGB").resize((128, 128))
        ib = Image.open(b).convert("RGB").resize((128, 128))
        diff = ImageChops.difference(ia, ib)
        total = sum(sum(px) for px in diff.getdata())  # type: ignore
        return total / (128 * 128 * 3 * 255)
    except Exception:
        return None


def _sha(p: pathlib.Path) -> str:
    try:
        return hashlib.sha256(p.read_bytes()).hexdigest()
    except Exception:
        return ""


def _is_text(name: str) -> bool:
    return name.lower().endswith((".txt", ".md", ".json", ".yaml", ".yml",
                                  ".srt", ".ass", ".csv"))


def _is_image(name: str) -> bool:
    return name.lower().endswith((".png", ".jpg", ".jpeg", ".webp"))


def diff_directories(dir_a: pathlib.Path, dir_b: pathlib.Path,
                     *, max_diff_lines: int = 800) -> dict[str, Any]:
    a_files = {str(p.relative_to(dir_a)).replace("\\", "/"): p
               for p in dir_a.rglob("*") if p.is_file()}
    b_files = {str(p.relative_to(dir_b)).replace("\\", "/"): p
               for p in dir_b.rglob("*") if p.is_file()}
    keys = sorted(set(a_files) | set(b_files))

    text: dict[str, dict[str, Any]] = {}
    visual: dict[str, dict[str, Any]] = {}
    other: dict[str, dict[str, Any]] = {}
    added = removed = changed = unchanged = 0

    for k in keys:
        a, b = a_files.get(k), b_files.get(k)
        if a is None:
            added += 1
            entry = {"status": "added"}
        elif b is None:
            removed += 1
            entry = {"status": "removed"}
        else:
            sa, sb = _sha(a), _sha(b)
            if sa == sb:
                unchanged += 1
                entry = {"status": "same", "sha256": sa[:16]}
            else:
                changed += 1
                entry = {"status": "changed",
                         "from_sha": sa[:16], "to_sha": sb[:16]}

        if _is_text(k):
            if entry["status"] == "changed":
                a_lines = _read_text(a).splitlines()
                b_lines = _read_text(b).splitlines()
                diff_lines = list(difflib.unified_diff(
                    a_lines, b_lines, fromfile="a/" + k, tofile="b/" + k,
                    lineterm=""))[:max_diff_lines]
                entry["diff"] = diff_lines
            text[k] = entry
        elif _is_image(k):
            if entry["status"] == "changed" and a and b:
                ham = _phash_distance(a, b)
                if ham is not None:
                    entry["phash_hamming"] = ham
                pct = _abs_diff_pct(a, b)
                if pct is not None:
                    entry["abs_diff_pct"] = round(pct, 4)
            visual[k] = entry
        else:
            other[k] = entry

    return {
        "text": text,
        "visual": visual,
        "other": other,
        "stats": {
            "files_added": added,
            "files_removed": removed,
            "files_changed": changed,
            "files_unchanged": unchanged,
            "files_total": len(keys),
        },
    }


def diff_scores_7d(a: Mapping[str, float] | None,
                   b: Mapping[str, float] | None) -> dict[str, dict[str, float]]:
    out: dict[str, dict[str, float]] = {}
    a = a or {}
    b = b or {}
    keys = set(a) | set(b)
    for k in sorted(keys):
        va, vb = float(a.get(k, 0.0)), float(b.get(k, 0.0))
        out[k] = {"from": round(va, 3), "to": round(vb, 3),
                  "delta": round(vb - va, 3)}
    return out


def full_diff_from_snapshots(
    snap_a, snap_b,
    *, vdir_a: pathlib.Path, vdir_b: pathlib.Path,
) -> dict[str, Any]:
    """High-level helper used by routes/jobs.py."""
    dir_diff = diff_directories(vdir_a, vdir_b)
    return {
        **dir_diff,
        "scores_7d": diff_scores_7d(snap_a.scores, snap_b.scores),
        "params_a": snap_a.params,
        "params_b": snap_b.params,
        "version_a": snap_a.version_no,
        "version_b": snap_b.version_no,
    }


__all__ = ["diff_directories", "diff_scores_7d", "full_diff_from_snapshots"]
