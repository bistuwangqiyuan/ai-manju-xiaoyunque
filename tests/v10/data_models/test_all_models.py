"""Smoke + sanity tests for the six V10 Phase-0 data models.

Each test:
  - imports + runs main()
  - asserts JSON + Markdown were emitted
  - asserts critical invariants (no NaN, totals positive, ratios in [0,1])
"""
from __future__ import annotations

import json
import math
import pathlib

import pytest

from tools.data_models import (
    capacity_model,
    cost_model,
    footprint_model,
    quality_model,
    throughput_model,
    validation_model,
)
from tools.data_models._common import DATA_DIR, DOCS_DIR


def _check_outputs_exist(name: str) -> dict:
    json_path = DATA_DIR / f"{name}.json"
    md_path = DOCS_DIR / f"{name}.md"
    assert json_path.exists(), f"missing {json_path}"
    assert md_path.exists(), f"missing {md_path}"
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert payload["model"] == name
    assert payload["version"].startswith("v10")
    return payload


# ---------- cost ----------------------------------------------------------
def test_cost_model_runs_and_is_positive():
    cost_model.main()
    payload = _check_outputs_exist("cost_model")
    baseline_total = payload["baseline"]["total_cny"]
    assert baseline_total > 0
    assert baseline_total < 1000, "baseline shouldn't exceed ¥1000 for 10 ep"
    # All tier costs increase with tier
    tier_costs = {n: t["cost_cny"] for n, t in payload["tiers"].items()}
    assert tier_costs["free"] < tier_costs["pro"] < tier_costs["studio"] < tier_costs["ent"]


def test_cost_model_breakdown_sums_to_total():
    payload = json.loads((DATA_DIR / "cost_model.json").read_text(encoding="utf-8"))
    breakdown = payload["baseline"]["breakdown"]
    total = payload["baseline"]["total_cny"]
    assert math.isclose(sum(breakdown.values()), total, abs_tol=0.05)


# ---------- throughput ----------------------------------------------------
def test_throughput_model_pilot_stable():
    throughput_model.main()
    payload = _check_outputs_exist("throughput_model")
    pilot = next(s for s in payload["scenarios"] if s["name"] == "pilot")
    assert not pilot["metrics"].get("unstable")
    assert 0 < pilot["metrics"]["utilisation"] < 1
    assert pilot["sla"]["queue_wait_p95_s_lt_target"]


def test_throughput_capacity_curve_monotonic():
    payload = json.loads((DATA_DIR / "throughput_model.json").read_text(encoding="utf-8"))
    curve = payload["capacity_curve"]
    assert curve, "capacity curve should not be empty"
    users = [r["users"] for r in curve]
    workers = [r["min_workers"] for r in curve]
    # workers should be monotonically non-decreasing as users grow
    assert all(workers[i] <= workers[i + 1] for i in range(len(workers) - 1))


# ---------- quality -------------------------------------------------------
def test_quality_model_pass_rate_improves_with_iter():
    quality_model.main()
    payload = _check_outputs_exist("quality_model")
    by_iter = payload["baseline_simulation"]["pass_rate_by_iter"]
    # More iterations strictly increases (or holds) pass rate
    rates = [by_iter[str(i)] for i in (0, 1, 2)]
    assert rates[0] <= rates[1] <= rates[2]
    assert 0 < rates[2] < 1


def test_quality_model_repair_gain_helps():
    payload = json.loads((DATA_DIR / "quality_model.json").read_text(encoding="utf-8"))
    sweep = payload["max_iter_sweep"]
    assert float(sweep["0"]) <= float(sweep["2"]) <= float(sweep["4"])


# ---------- capacity ------------------------------------------------------
def test_capacity_model_scales_with_dau():
    capacity_model.main()
    payload = _check_outputs_exist("capacity_model")
    scenarios = payload["scenarios"]
    # TOS storage should monotonically grow with DAU
    gbs = [s["storage"]["tos_total_gb"] for s in scenarios]
    assert gbs[0] < gbs[1] < gbs[2] < gbs[3]
    # Pilot should still fit on SQLite, peak should not
    assert scenarios[0]["database"]["use_sqlite_safe"]
    assert not scenarios[-1]["database"]["use_sqlite_safe"]


# ---------- footprint -----------------------------------------------------
def test_footprint_model_decisions_sane():
    footprint_model.main()
    payload = _check_outputs_exist("footprint_model")
    variants = {v["variant"]["name"]: v for v in payload["variants"]}
    # v9 < v10_main_lean < v10_main_monolith
    assert variants["v9_current"]["total_gb"] < variants["v10_main_lean"]["total_gb"]
    assert variants["v10_main_lean"]["total_gb"] < variants["v10_main_monolith"]["total_gb"]


# ---------- validation ----------------------------------------------------
def test_validation_model_recommends_best_backend():
    validation_model.main()
    payload = _check_outputs_exist("validation_model")
    rec = payload["recommendation"]
    backends = payload["calibration"]
    # The recommended backend has the lowest RMSE
    rmses = {b: v["rmse"] for b, v in backends.items()}
    assert min(rmses, key=rmses.get) == rec


def test_validation_model_weights_sum_to_one():
    payload = json.loads((DATA_DIR / "validation_model.json").read_text(encoding="utf-8"))
    for backend, data in payload["calibration"].items():
        s = sum(data["weights"].values())
        assert math.isclose(s, 1.0, abs_tol=0.01), f"{backend} weights sum to {s}"
