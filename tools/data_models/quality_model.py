"""V10 quality model — 7-dim Monte Carlo + repair loop simulator.

Simulates ``need.md §6.1`` 7-dim scoring + ``§6.3`` repair loop to derive
reproducible pass-rate-vs-iteration curves and expected per-shot iteration
budget.  No scipy, no numpy — pure stdlib + ``random`` seeded with a
project-level constant so CI is bit-reproducible.

Run::

    python -m tools.data_models.quality_model
"""
from __future__ import annotations

import math
import random
import statistics
from dataclasses import dataclass, field
from typing import Iterable

from tools.data_models._common import (
    parse_cli_out,
    render_table,
    write_json,
    write_markdown,
)

SEVEN_DIM_KEYS = (
    "structure", "style", "detail", "clarity", "color", "no_deform", "intent",
)

# default weighting — derived from validation_model.py last calibration
DEFAULT_WEIGHTS: dict[str, float] = {
    "structure": 0.18,
    "style": 0.20,
    "detail": 0.12,
    "clarity": 0.10,
    "color": 0.10,
    "no_deform": 0.18,
    "intent": 0.12,
}


# ---------------------------------------------------------------------------
# Generation model (per-dim score follows truncated-normal in [0, 10])
# ---------------------------------------------------------------------------
@dataclass
class DimDistribution:
    mean: float
    std: float

    def sample(self, rng: random.Random) -> float:
        v = rng.gauss(self.mean, self.std)
        return max(0.0, min(10.0, v))


# ground truth distributions from arcface_check.py + seven_dim_scorer.py
# empirical fit on 200 mock-mode runs
BASELINE_DIST: dict[str, DimDistribution] = {
    "structure": DimDistribution(8.3, 0.9),
    "style":     DimDistribution(8.7, 0.7),
    "detail":    DimDistribution(7.9, 1.1),
    "clarity":   DimDistribution(8.4, 0.8),
    "color":     DimDistribution(8.5, 0.7),
    "no_deform": DimDistribution(7.6, 1.4),     # most volatile (hands, faces)
    "intent":    DimDistribution(8.1, 1.0),
}

# repair gain — per-route mean uplift on its primary dim
REPAIR_GAIN: dict[str, dict[str, float]] = {
    "face_drift":     {"no_deform": 1.4, "structure": 0.4},
    "closeup_lipsync":{"intent": 1.1, "no_deform": 0.5},
    "costume_drift":  {"detail": 1.0, "style": 0.6},
    "cross_show_style":{"style": 1.4, "color": 0.5},
    "motion_axis":    {"structure": 1.1, "no_deform": 0.4},
    "climax_enhance": {"detail": 0.9, "clarity": 0.7},
    "god_tier":       {k: 0.8 for k in SEVEN_DIM_KEYS},   # fallback uses all
    "hand_local":     {"no_deform": 1.6},
}


@dataclass
class ShotResult:
    initial_scores: dict[str, float] = field(default_factory=dict)
    final_scores: dict[str, float] = field(default_factory=dict)
    iterations: int = 0
    routes: list[str] = field(default_factory=list)
    overall: float = 0.0
    passed: bool = False


def overall_score(scores: dict[str, float], weights: dict[str, float] | None = None) -> float:
    w = weights or DEFAULT_WEIGHTS
    return sum(scores[k] * w[k] for k in SEVEN_DIM_KEYS)


def pick_route(scores: dict[str, float], threshold: float) -> str | None:
    """Choose repair route based on the worst-axis (simulates auto_diagnose)."""
    if all(scores[k] >= threshold for k in SEVEN_DIM_KEYS):
        return None
    worst = min(SEVEN_DIM_KEYS, key=lambda k: scores[k])
    return {
        "structure": "motion_axis",
        "style": "cross_show_style",
        "detail": "costume_drift",
        "clarity": "climax_enhance",
        "color": "cross_show_style",
        "no_deform": "hand_local",
        "intent": "closeup_lipsync",
    }[worst]


def simulate_shot(rng: random.Random, *, max_iter: int = 2,
                  pass_threshold: float = 7.0,
                  weights: dict[str, float] | None = None) -> ShotResult:
    scores = {k: BASELINE_DIST[k].sample(rng) for k in SEVEN_DIM_KEYS}
    result = ShotResult(initial_scores=dict(scores))
    for it in range(max_iter):
        route = pick_route(scores, pass_threshold)
        if route is None:
            break
        result.iterations = it + 1
        result.routes.append(route)
        for dim, gain in REPAIR_GAIN.get(route, {}).items():
            # repair gain is itself noisy
            actual = max(0.0, rng.gauss(gain, gain * 0.35))
            scores[dim] = min(10.0, scores[dim] + actual)
    result.final_scores = dict(scores)
    result.overall = overall_score(scores, weights)
    result.passed = all(scores[k] >= pass_threshold for k in SEVEN_DIM_KEYS)
    return result


def simulate_project(
    *,
    n_shots: int = 160,
    trials: int = 10_000,
    max_iter: int = 2,
    pass_threshold: float = 7.0,
    seed: int = 20260526,
    weights: dict[str, float] | None = None,
) -> dict:
    rng = random.Random(seed)
    # Pass rate by iteration cap
    pass_rate_by_iter: dict[int, float] = {}
    for cap in range(0, max_iter + 1):
        passes = 0
        for _ in range(trials):
            r = simulate_shot(rng, max_iter=cap, pass_threshold=pass_threshold, weights=weights)
            if r.passed:
                passes += 1
        pass_rate_by_iter[cap] = passes / trials
    # Per-shot metrics distribution
    results = [simulate_shot(rng, max_iter=max_iter, pass_threshold=pass_threshold, weights=weights)
               for _ in range(trials)]
    avg_iter = statistics.fmean(r.iterations for r in results)
    pass_final = sum(1 for r in results if r.passed) / trials
    overall_avg = statistics.fmean(r.overall for r in results)
    overall_p10 = sorted(r.overall for r in results)[int(trials * 0.10)]
    overall_p90 = sorted(r.overall for r in results)[int(trials * 0.90)]
    # project pass: all n_shots must pass independently
    expected_shot_pass = pass_final
    project_pass_prob = expected_shot_pass ** n_shots
    return {
        "pass_rate_by_iter": pass_rate_by_iter,
        "expected_iter_per_shot": avg_iter,
        "shot_pass_rate_final": pass_final,
        "shot_overall_mean": overall_avg,
        "shot_overall_p10": overall_p10,
        "shot_overall_p90": overall_p90,
        "project_pass_probability": project_pass_prob,
        "n_shots_per_project": n_shots,
        "trials": trials,
        "seed": seed,
        "pass_threshold": pass_threshold,
        "max_iter": max_iter,
    }


def build_report() -> dict:
    base = simulate_project()
    threshold_sweep = {
        f"{t:.1f}": simulate_project(pass_threshold=t)["shot_pass_rate_final"]
        for t in (6.5, 7.0, 7.5, 8.0)
    }
    iter_sweep = {
        str(it): simulate_project(max_iter=it)["shot_pass_rate_final"]
        for it in (0, 1, 2, 3, 4)
    }
    return {
        "model": "quality_model",
        "version": "v10.0",
        "weights": DEFAULT_WEIGHTS,
        "baseline_distributions": {k: {"mean": v.mean, "std": v.std}
                                   for k, v in BASELINE_DIST.items()},
        "repair_gains": REPAIR_GAIN,
        "baseline_simulation": base,
        "pass_threshold_sweep": threshold_sweep,
        "max_iter_sweep": iter_sweep,
    }


def render_markdown(report: dict) -> str:
    base = report["baseline_simulation"]
    parts = [
        "# 质量评分模型 (quality_model)",
        "",
        "> 10 000 次 Monte Carlo 模拟，按 `need.md §6.1` 7 维评分 + `§6.3` 修复闭环。",
        "",
        "## 1. 7 维权重",
        "",
        render_table(["维度", "权重"], [[k, v] for k, v in report["weights"].items()]),
        "",
        "## 2. 各维度基线分布 (μ, σ)",
        "",
        render_table(
            ["维度", "μ", "σ"],
            [[k, v["mean"], v["std"]] for k, v in report["baseline_distributions"].items()],
        ),
        "",
        "## 3. 基线结果 (max_iter=2, threshold=7.0)",
        "",
        render_table(
            ["指标", "值"],
            [
                ["pass_rate_by_iter=0", f"{base['pass_rate_by_iter'][0]*100:.1f}%"],
                ["pass_rate_by_iter=1", f"{base['pass_rate_by_iter'][1]*100:.1f}%"],
                ["pass_rate_by_iter=2", f"{base['pass_rate_by_iter'][2]*100:.1f}%"],
                ["expected_iter_per_shot", base["expected_iter_per_shot"]],
                ["shot_overall_mean", base["shot_overall_mean"]],
                ["shot_overall_p10", base["shot_overall_p10"]],
                ["shot_overall_p90", base["shot_overall_p90"]],
                ["project_pass_probability (160 shots)", f"{base['project_pass_probability']*100:.2f}%"],
            ],
        ),
        "",
        "## 4. 阈值灵敏度",
        "",
        render_table(
            ["pass_threshold", "shot_pass_rate"],
            [[k, f"{v*100:.1f}%"] for k, v in report["pass_threshold_sweep"].items()],
        ),
        "",
        "## 5. max_iter 灵敏度",
        "",
        render_table(
            ["max_iter", "shot_pass_rate"],
            [[k, f"{v*100:.1f}%"] for k, v in report["max_iter_sweep"].items()],
        ),
        "",
        "## 6. 复现 (固定 seed = 20260526)",
        "",
        "```bash",
        "python -m tools.data_models.quality_model",
        "```",
    ]
    return "\n".join(parts)


def main() -> dict:
    parse_cli_out()
    report = build_report()
    write_json("quality_model", report)
    write_markdown("quality_model", render_markdown(report))
    base = report["baseline_simulation"]
    print(f"pass_rate_iter2={base['pass_rate_by_iter'][2]*100:.1f}%, "
          f"avg_iter={base['expected_iter_per_shot']:.2f}, "
          f"project_pass={base['project_pass_probability']*100:.2f}%")
    return report


if __name__ == "__main__":
    main()
