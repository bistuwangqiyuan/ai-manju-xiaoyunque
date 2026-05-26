"""V10 §6.1 — Cross-shot style consistency scorer.

For a group of N rendered shots we want a *numerical* answer to "does the
style stay consistent across all shots?".  We compute pairwise CLIP-image
cosine similarities (or pHash fallback) and turn the matrix into:

    - mean similarity (0-1)
    - min similarity (worst pair)
    - 0-10 style consistency score (mapped from min similarity)

If a "style anchor" image is supplied we additionally measure each shot's
distance to that anchor, surfacing the *single shot* most off-style.
"""
from __future__ import annotations

import hashlib
import math
import pathlib
from dataclasses import dataclass, field


@dataclass
class ConsistencyReport:
    n_shots: int
    mean_similarity: float
    min_similarity: float
    max_drift: float
    style_score_10: float
    outlier_index: int | None = None
    pair_matrix: list[list[float]] = field(default_factory=list)
    backend: str = "phash"

    def to_dict(self) -> dict:
        return {
            "n_shots": self.n_shots,
            "mean_similarity": round(self.mean_similarity, 4),
            "min_similarity": round(self.min_similarity, 4),
            "max_drift": round(self.max_drift, 4),
            "style_score_10": round(self.style_score_10, 2),
            "outlier_index": self.outlier_index,
            "backend": self.backend,
            "pair_matrix": [[round(v, 3) for v in row] for row in self.pair_matrix],
        }


def _try_clip():
    try:
        import torch  # type: ignore
        import open_clip  # type: ignore
        return torch, open_clip
    except Exception:
        return None, None


def _clip_embed(paths: list[pathlib.Path]) -> list[list[float]] | None:
    torch, open_clip = _try_clip()
    if torch is None:
        return None
    try:
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
            for p in paths:
                x = preprocess(Image.open(p).convert("RGB")).unsqueeze(0)
                e = model.encode_image(x).cpu().numpy().flatten().tolist()
                n = math.sqrt(sum(v * v for v in e))
                embs.append([v / n for v in e] if n > 0 else e)
        return embs
    except Exception:
        return None


def _phash_embed(paths: list[pathlib.Path]) -> list[list[float]]:
    """Perceptual embedding for similarity.

    Tries (in order):
        1. imagehash.phash (8x8 DCT hash) — true pHash
        2. average-hash: 8x8 grayscale + per-pixel z-score (PIL only).
           Also concatenates a 12-bin colour histogram so style/colour
           drift is detectable on solid-colour fixtures.
        3. SHA-1 of raw bytes (truly degenerate fallback).
    """
    try:
        from PIL import Image  # type: ignore
        import imagehash  # type: ignore
        out = []
        for p in paths:
            h = imagehash.phash(Image.open(p), hash_size=8)
            bits = h.hash.flatten().astype(float).tolist()
            out.append([2 * v - 1 for v in bits])
        return out
    except Exception:
        pass

    try:
        from PIL import Image  # type: ignore
        out = []
        for p in paths:
            img = Image.open(p).convert("RGB")
            # 8x8 grayscale → 64-dim z-scored vector
            gray = img.convert("L").resize((8, 8))
            px = list(gray.getdata())
            mean = sum(px) / 64.0
            var = sum((v - mean) ** 2 for v in px) / 64.0
            std = math.sqrt(var) + 1e-6
            ahash = [(v - mean) / std for v in px]
            # 12-bin colour histogram (4 R + 4 G + 4 B) normalised
            small = img.resize((32, 32))
            r_bins = [0] * 4
            g_bins = [0] * 4
            b_bins = [0] * 4
            for (r, g, b) in small.getdata():
                r_bins[min(r * 4 // 256, 3)] += 1
                g_bins[min(g * 4 // 256, 3)] += 1
                b_bins[min(b * 4 // 256, 3)] += 1
            tot = 32 * 32
            hist = [v * 2 - 1 for v in
                    [c / tot for c in r_bins + g_bins + b_bins]]
            vec = ahash + hist  # 76-dim
            # L2 normalise so cosine ∈ [-1, 1]
            n = math.sqrt(sum(v * v for v in vec)) + 1e-9
            out.append([v / n for v in vec])
        return out
    except Exception:
        out = []
        for p in paths:
            digest = hashlib.sha1(p.read_bytes()).digest()
            out.append([(b / 255.0) * 2 - 1 for b in digest])
        return out


def _cos(a: list[float], b: list[float]) -> float:
    n = min(len(a), len(b))
    return sum(a[i] * b[i] for i in range(n))


def score(image_paths: list[str | pathlib.Path],
          *, style_anchor: str | pathlib.Path | None = None) -> ConsistencyReport:
    paths = [pathlib.Path(p) for p in image_paths]
    if len(paths) < 2:
        return ConsistencyReport(
            n_shots=len(paths), mean_similarity=1.0, min_similarity=1.0,
            max_drift=0.0, style_score_10=10.0,
        )
    embs = _clip_embed(paths)
    backend = "clip" if embs is not None else "phash"
    if embs is None:
        embs = _phash_embed(paths)

    n = len(embs)
    mat = [[0.0] * n for _ in range(n)]
    for i in range(n):
        for j in range(n):
            if i == j:
                mat[i][j] = 1.0
            else:
                mat[i][j] = _cos(embs[i], embs[j])
    pairs = [mat[i][j] for i in range(n) for j in range(i + 1, n)]
    mean_sim = sum(pairs) / max(len(pairs), 1)
    min_sim = min(pairs)
    max_drift = 1.0 - min_sim

    # Outlier shot: lowest avg sim with everyone else
    avg_per_shot = [sum(mat[i][j] for j in range(n) if j != i) / (n - 1) for i in range(n)]
    outlier_index = int(min(range(n), key=lambda i: avg_per_shot[i])) if n > 1 else None

    # Style anchor (optional)
    if style_anchor is not None and pathlib.Path(style_anchor).exists():
        anchor_emb = _clip_embed([pathlib.Path(style_anchor)]) or _phash_embed([pathlib.Path(style_anchor)])
        anchor_sims = [_cos(anchor_emb[0], e) for e in embs]
        min_anchor = min(anchor_sims)
        # Score combines pairwise + anchor
        consistency_score = 10 * (0.55 * (mean_sim + 1) / 2 + 0.30 * (min_sim + 1) / 2 + 0.15 * (min_anchor + 1) / 2)
    else:
        consistency_score = 10 * (0.65 * (mean_sim + 1) / 2 + 0.35 * (min_sim + 1) / 2)

    return ConsistencyReport(
        n_shots=n, mean_similarity=mean_sim, min_similarity=min_sim,
        max_drift=max_drift,
        style_score_10=max(0.0, min(10.0, consistency_score)),
        outlier_index=outlier_index, pair_matrix=mat, backend=backend,
    )


__all__ = ["ConsistencyReport", "score"]
