"""V10 throughput model — M/M/c queueing for the manju agent pipeline.

The orchestrator dispatches up to ``MANJU_PARALLEL`` concurrent episode
renders.  Each render is well-modelled as an M/M/c service: Poisson
arrival of new jobs from the queue, exponential service time, ``c``
parallel workers.

We compute Erlang-C (probability a job waits), expected wait time,
queue depth, and 95p latency directly from the closed form so the
script has no scipy dependency.

Run::

    python -m tools.data_models.throughput_model
"""
from __future__ import annotations

import math
from dataclasses import dataclass, asdict

from tools.data_models._common import (
    parse_cli_out,
    render_table,
    write_json,
    write_markdown,
)


# ---------------------------------------------------------------------------
# Measured base rates  (source: tests/test_serverless_tick.py + manual logs)
# ---------------------------------------------------------------------------
DEFAULT_SHOT_RENDER_SECONDS = 36.0      # mean Manju agent per-episode service time
DEFAULT_EPISODE_SECONDS = 165.0         # mean end-to-end per episode (script+assets+render)
DEFAULT_TEXT_FIRST_TOKEN_S = 3.2        # novel first-token latency
DEFAULT_SHOTS_PER_MIN_PER_WORKER = 60 / DEFAULT_SHOT_RENDER_SECONDS  # ≈ 1.67


# ---------------------------------------------------------------------------
# Erlang-C closed form (pure math.factorial; works up to c ≤ 170 safely)
# ---------------------------------------------------------------------------
def erlang_c(c: int, rho_total: float) -> float:
    """Probability an arriving job must wait (M/M/c, ρ = λ/(cμ)).

    Uses the numerically stable recursion ``t_k = t_{k-1} * a / k`` to
    avoid factorial / power overflow for c up to several thousand.
    """
    if c <= 0:
        return 1.0
    a = float(rho_total)
    if a >= c:
        return 1.0
    # term_k = a^k / k! computed incrementally
    term = 1.0   # k = 0
    sum_terms = 1.0
    for k in range(1, c):
        term *= a / k
        sum_terms += term
    last = term * a / c / (1 - a / c)
    p0 = 1.0 / (sum_terms + last)
    return last * p0


def queue_metrics(c: int, lambda_per_s: float, mu_per_s: float) -> dict:
    """Return latency / queue-depth / utilisation for an M/M/c."""
    if mu_per_s <= 0 or lambda_per_s < 0:
        return {"unstable": True}
    rho_total = lambda_per_s / mu_per_s          # offered load (Erlangs)
    rho = rho_total / max(c, 1)                  # per-server utilisation
    if rho >= 1.0:
        return {"unstable": True, "utilisation": rho, "rho_total": rho_total}
    p_wait = erlang_c(c, rho_total)
    e_wq = p_wait / (c * mu_per_s - lambda_per_s)  # expected wait in queue (sec)
    e_w = e_wq + 1.0 / mu_per_s                    # incl. service
    e_lq = lambda_per_s * e_wq                     # Little's Law (queue length)
    e_l = lambda_per_s * e_w                       # in system
    # 95p / 99p latency approximation for M/M/c (Khintchine-Pollaczek style):
    # W(t) = 1 - p_wait * exp(-(cμ-λ) t); invert.
    def percentile(p: float) -> float:
        if p_wait == 0:
            return 1.0 / mu_per_s
        if p >= 1.0:
            return float("inf")
        z = max(p_wait / max(1 - p, 1e-9), 1.0)
        return e_wq + math.log(z) / max(c * mu_per_s - lambda_per_s, 1e-9) + 1.0 / mu_per_s
    return {
        "utilisation": rho,
        "rho_total": rho_total,
        "p_wait_gt_0": p_wait,
        "expected_wait_in_queue_s": e_wq,
        "expected_wait_in_system_s": e_w,
        "expected_queue_length": e_lq,
        "expected_jobs_in_system": e_l,
        "p50_wait_in_system_s": percentile(0.5),
        "p95_wait_in_system_s": percentile(0.95),
        "p99_wait_in_system_s": percentile(0.99),
        "throughput_per_min": lambda_per_s * 60,
    }


# ---------------------------------------------------------------------------
# Scenarios
# ---------------------------------------------------------------------------
@dataclass
class TrafficScenario:
    name: str
    concurrent_users: int                       # active editors
    avg_jobs_per_user_per_h: float              # arrival intensity
    parallel_workers: int                       # MANJU_PARALLEL × instances
    mean_service_s: float = DEFAULT_EPISODE_SECONDS

    @property
    def lambda_per_s(self) -> float:
        return self.concurrent_users * self.avg_jobs_per_user_per_h / 3600.0

    @property
    def mu_per_s(self) -> float:
        return 1.0 / self.mean_service_s


def scenarios() -> list[TrafficScenario]:
    return [
        TrafficScenario("dev",          concurrent_users=2,    avg_jobs_per_user_per_h=2.0,  parallel_workers=3),
        TrafficScenario("pilot",        concurrent_users=20,   avg_jobs_per_user_per_h=0.8,  parallel_workers=6),
        TrafficScenario("launch",       concurrent_users=200,  avg_jobs_per_user_per_h=0.5,  parallel_workers=24),
        TrafficScenario("scale",        concurrent_users=1500, avg_jobs_per_user_per_h=0.3,  parallel_workers=120),
        TrafficScenario("peak_friday",  concurrent_users=3000, avg_jobs_per_user_per_h=0.6,  parallel_workers=200),
    ]


def sla_targets() -> dict[str, float]:
    """SLA from need.md §11.2."""
    return {
        "novel_first_token_s_lt": 5.0,
        "single_image_s_lt": 15.0,
        "five_second_clip_s_lt": 180.0,
        "queue_wait_p95_s_lt": 600.0,
    }


def sla_pass(metrics: dict, sla: dict) -> dict:
    if metrics.get("unstable"):
        return {"overall": False, "reason": "unstable"}
    p95 = metrics["p95_wait_in_system_s"]
    return {
        "queue_wait_p95_s_lt_target": p95 < sla["queue_wait_p95_s_lt"],
        "p95_actual": p95,
        "target": sla["queue_wait_p95_s_lt"],
    }


def build_report() -> dict:
    sla = sla_targets()
    rows = []
    for sc in scenarios():
        m = queue_metrics(sc.parallel_workers, sc.lambda_per_s, sc.mu_per_s)
        pass_check = sla_pass(m, sla)
        rows.append({
            "name": sc.name,
            "scenario": asdict(sc),
            "lambda_per_s": sc.lambda_per_s,
            "mu_per_s": sc.mu_per_s,
            "metrics": m,
            "sla": pass_check,
        })
    # Capacity planning curve: for each user count, find min workers s.t. p95 < target
    curve = []
    for users in (50, 100, 200, 500, 1000, 2000, 5000):
        lam = users * 0.5 / 3600.0
        for c in range(1, 1024):
            m = queue_metrics(c, lam, 1.0 / DEFAULT_EPISODE_SECONDS)
            if not m.get("unstable") and m["p95_wait_in_system_s"] < sla["queue_wait_p95_s_lt"]:
                curve.append({
                    "users": users, "min_workers": c,
                    "p95_s": round(m["p95_wait_in_system_s"], 1),
                    "throughput_per_min": round(m["throughput_per_min"], 3),
                })
                break
    return {
        "model": "throughput_model",
        "version": "v10.0",
        "constants": {
            "default_shot_render_seconds": DEFAULT_SHOT_RENDER_SECONDS,
            "default_episode_seconds": DEFAULT_EPISODE_SECONDS,
        },
        "sla_targets": sla,
        "scenarios": rows,
        "capacity_curve": curve,
    }


def render_markdown(report: dict) -> str:
    rows = [
        [
            s["name"], s["scenario"]["concurrent_users"],
            s["scenario"]["parallel_workers"],
            f"{s['lambda_per_s']:.4f}",
            s["metrics"].get("utilisation", "N/A") if not s["metrics"].get("unstable") else "💥",
            f"{s['metrics'].get('p_wait_gt_0', 0):.3f}" if not s["metrics"].get("unstable") else "—",
            f"{s['metrics'].get('p95_wait_in_system_s', 0):.1f}" if not s["metrics"].get("unstable") else "∞",
            "✅" if s["sla"].get("queue_wait_p95_s_lt_target") else "❌",
        ]
        for s in report["scenarios"]
    ]
    curve_rows = [[r["users"], r["min_workers"], r["p95_s"], r["throughput_per_min"]]
                  for r in report["capacity_curve"]]
    parts = [
        "# 吞吐量模型 (throughput_model)",
        "",
        "> M/M/c 排队论：估算 V10 在不同流量场景下的等待时间、队列深度、SLA 达标率。",
        "",
        "## 1. SLA 目标 (need.md §11.2)",
        "",
        render_table(["指标", "阈值 (s)"], [[k, v] for k, v in report["sla_targets"].items()]),
        "",
        "## 2. 五档场景",
        "",
        render_table(
            ["场景", "并发用户", "并行 worker 数", "λ/s", "利用率 ρ", "P(等待>0)", "P95 系统时延 s", "SLA"],
            rows,
        ),
        "",
        "## 3. 容量曲线 — 为达 P95 < 600s 所需 worker 数",
        "",
        render_table(
            ["并发用户", "最少 worker", "实际 P95 s", "吞吐量 /min"],
            curve_rows,
        ),
        "",
        "## 4. 复现",
        "",
        "```bash",
        "python -m tools.data_models.throughput_model",
        "```",
    ]
    return "\n".join(parts)


def main() -> dict:
    parse_cli_out()
    report = build_report()
    write_json("throughput_model", report)
    write_markdown("throughput_model", render_markdown(report))
    pilot = next(s for s in report["scenarios"] if s["name"] == "pilot")
    print(f"pilot p95={pilot['metrics'].get('p95_wait_in_system_s', float('nan')):.1f}s, "
          f"utilisation={pilot['metrics'].get('utilisation', float('nan')):.3f}")
    return report


if __name__ == "__main__":
    main()
