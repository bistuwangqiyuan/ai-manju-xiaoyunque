"""V10 validation model — 7-dim scoring calibration via ridge regression.

Uses 50 synthetic ground-truth labels (generated deterministically) to
fit per-backend RMSE and produce updated 7-dim weights.  Real labels can
be dropped into ``data/calibration_labels.json`` to override.

No sklearn dependency: we implement Ridge closed-form ``(XᵀX + λI)⁻¹ Xᵀy``
in pure Python with a tiny matrix-inverse helper.

Run::

    python -m tools.data_models.validation_model
"""
from __future__ import annotations

import json
import math
import pathlib
import random
from dataclasses import dataclass
from typing import Sequence

from tools.data_models._common import (
    DATA_DIR,
    parse_cli_out,
    render_table,
    write_json,
    write_markdown,
)

SEVEN_DIM_KEYS = (
    "structure", "style", "detail", "clarity", "color", "no_deform", "intent",
)
BACKENDS = ("multi_vlm", "doubao_seed16", "mock_sha256")


# ---------------------------------------------------------------------------
# Tiny linear algebra (pure Python, OK for 7×7 matrices)
# ---------------------------------------------------------------------------
def _matmul(a: list[list[float]], b: list[list[float]]) -> list[list[float]]:
    n, m, p = len(a), len(b), len(b[0])
    return [[sum(a[i][k] * b[k][j] for k in range(m)) for j in range(p)] for i in range(n)]


def _transpose(a: list[list[float]]) -> list[list[float]]:
    return [list(row) for row in zip(*a)]


def _inverse(m: list[list[float]]) -> list[list[float]]:
    n = len(m)
    aug = [row[:] + [1.0 if i == j else 0.0 for j in range(n)] for i, row in enumerate(m)]
    for i in range(n):
        pivot = aug[i][i]
        if abs(pivot) < 1e-12:
            for r in range(i + 1, n):
                if abs(aug[r][i]) > 1e-12:
                    aug[i], aug[r] = aug[r], aug[i]
                    pivot = aug[i][i]
                    break
        for j in range(2 * n):
            aug[i][j] /= pivot
        for r in range(n):
            if r == i:
                continue
            factor = aug[r][i]
            for j in range(2 * n):
                aug[r][j] -= factor * aug[i][j]
    return [row[n:] for row in aug]


def ridge_regression(X: list[list[float]], y: list[float],
                     reg_lambda: float = 0.5) -> list[float]:
    """Solve β = (XᵀX + λI)⁻¹ Xᵀy."""
    Xt = _transpose(X)
    XtX = _matmul(Xt, X)
    n = len(XtX)
    XtX_reg = [[XtX[i][j] + (reg_lambda if i == j else 0.0) for j in range(n)]
               for i in range(n)]
    inv = _inverse(XtX_reg)
    XtXinv_Xt = _matmul(inv, Xt)
    return [sum(XtXinv_Xt[i][j] * y[j] for j in range(len(y))) for i in range(n)]


# ---------------------------------------------------------------------------
# Synthetic labels (50 samples) — bit-reproducible
# ---------------------------------------------------------------------------
@dataclass
class LabelSample:
    backend_scores: dict[str, dict[str, float]]   # backend → dim → score
    ground_truth: float                          # human-judged 0-10


def _maybe_load_real() -> list[LabelSample] | None:
    fp = DATA_DIR / "calibration_labels.json"
    if not fp.exists():
        return None
    try:
        raw = json.loads(fp.read_text(encoding="utf-8"))
        return [LabelSample(s["backend_scores"], float(s["ground_truth"])) for s in raw]
    except Exception:
        return None


def synth_labels(n: int = 50, seed: int = 20260526) -> list[LabelSample]:
    rng = random.Random(seed)
    samples: list[LabelSample] = []
    # Ground truth from a hidden "true weights"
    true_w = {
        "structure": 0.17, "style": 0.21, "detail": 0.13, "clarity": 0.10,
        "color": 0.09, "no_deform": 0.19, "intent": 0.11,
    }
    for _ in range(n):
        true_dim = {k: max(0.0, min(10.0, rng.gauss(8.3, 1.0))) for k in SEVEN_DIM_KEYS}
        gt = sum(true_dim[k] * true_w[k] for k in SEVEN_DIM_KEYS)
        # Backend-specific noise
        b_scores = {
            "multi_vlm":     {k: max(0.0, min(10.0, v + rng.gauss(0, 0.35))) for k, v in true_dim.items()},
            "doubao_seed16": {k: max(0.0, min(10.0, v + rng.gauss(0, 0.55))) for k, v in true_dim.items()},
            "mock_sha256":   {k: max(0.0, min(10.0, v + rng.gauss(0, 1.10))) for k, v in true_dim.items()},
        }
        samples.append(LabelSample(b_scores, gt))
    return samples


def calibrate(samples: list[LabelSample], reg_lambda: float = 0.5) -> dict:
    out = {}
    for backend in BACKENDS:
        X = [[s.backend_scores[backend][k] for k in SEVEN_DIM_KEYS] for s in samples]
        y = [s.ground_truth for s in samples]
        beta = ridge_regression(X, y, reg_lambda)
        preds = [sum(X[i][j] * beta[j] for j in range(7)) for i in range(len(y))]
        residuals = [preds[i] - y[i] for i in range(len(y))]
        rmse = math.sqrt(sum(r ** 2 for r in residuals) / len(residuals))
        mae = sum(abs(r) for r in residuals) / len(residuals)
        # Normalise weights to sum=1 for downstream compatibility
        s = sum(beta)
        norm_weights = [b / s for b in beta] if abs(s) > 1e-9 else beta
        out[backend] = {
            "weights": {k: round(norm_weights[i], 4) for i, k in enumerate(SEVEN_DIM_KEYS)},
            "raw_betas": {k: round(beta[i], 4) for i, k in enumerate(SEVEN_DIM_KEYS)},
            "rmse": round(rmse, 4),
            "mae": round(mae, 4),
            "sample_count": len(samples),
        }
    return out


def build_report() -> dict:
    real = _maybe_load_real()
    samples = real or synth_labels()
    calibration = calibrate(samples)
    return {
        "model": "validation_model",
        "version": "v10.0",
        "source": "real labels" if real else "synthetic 50 samples",
        "regularisation_lambda": 0.5,
        "calibration": calibration,
        "recommendation": min(BACKENDS, key=lambda b: calibration[b]["rmse"]),
    }


def render_markdown(report: dict) -> str:
    backends = report["calibration"]
    parts = [
        "# 7 维评分校准模型 (validation_model)",
        "",
        f"> 数据源：**{report['source']}** · 推荐主 backend：**{report['recommendation']}**",
        "",
        "## 1. 各 backend RMSE / MAE",
        "",
        render_table(
            ["backend", "RMSE", "MAE", "样本数"],
            [[b, v["rmse"], v["mae"], v["sample_count"]] for b, v in backends.items()],
        ),
        "",
        "## 2. 推荐 backend 校准后权重 (normalised)",
        "",
        render_table(
            ["维度", "校准权重"],
            [[k, v] for k, v in backends[report["recommendation"]]["weights"].items()],
        ),
        "",
        "## 3. 复现",
        "",
        "```bash",
        "python -m tools.data_models.validation_model",
        "# 用真实标签覆盖：",
        "# echo '[{\"backend_scores\":{...},\"ground_truth\":8.5}]' > data/data_models/calibration_labels.json",
        "```",
    ]
    return "\n".join(parts)


def main() -> dict:
    parse_cli_out()
    report = build_report()
    write_json("validation_model", report)
    write_markdown("validation_model", render_markdown(report))
    best = report["recommendation"]
    print(f"best_backend={best} "
          f"rmse={report['calibration'][best]['rmse']:.3f}")
    return report


if __name__ == "__main__":
    main()
