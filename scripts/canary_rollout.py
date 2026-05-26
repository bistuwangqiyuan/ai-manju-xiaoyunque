"""V10 GA — veFaaS canary rollout orchestrator.

Stages (default):
    10%  → observe 24h (or --observe-minutes for CI)
    30%  → observe 24h
    100% → GA

Each stage:
    1. Writes traffic weight to ``deploy/cn-volc-vefaas/canary_state.json``
    2. (Optional) calls Volcengine API Gateway weight update when credentials
       are present — otherwise prints the manual CLI snippet.
    3. Runs ``tools/sla_probe.py`` against the canary base URL.
    4. Aborts if global success rate < ``--min-success-rate`` (default 0.99).

Usage::

    python scripts/canary_rollout.py --base-url https://xyq.example.com \\
        --stage 10 --dry-run
    python scripts/canary_rollout.py --base-url https://xyq.example.com \\
        --auto-advance --observe-minutes 5   # CI smoke
"""
from __future__ import annotations

import argparse
import json
import pathlib
import subprocess
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

REPO = pathlib.Path(__file__).resolve().parents[1]
STATE_PATH = REPO / "deploy" / "cn-volc-vefaas" / "canary_state.json"
GA_NOTICE_PATH = REPO / "docs" / "ga_v10_announcement.md"

STAGES = (10, 30, 100)


@dataclass
class CanaryStage:
    percent: int
    started_at: str = ""
    sla_probe: dict[str, Any] = field(default_factory=dict)
    status: str = "pending"   # pending | running | passed | failed


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def load_state() -> dict[str, Any]:
    if STATE_PATH.exists():
        return json.loads(STATE_PATH.read_text(encoding="utf-8"))
    return {"version": "v10", "stages": [], "current_percent": 0}


def save_state(state: dict[str, Any]) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(state, indent=2, ensure_ascii=False),
                          encoding="utf-8")


def run_sla_probe(base_url: str, *, iterations: int = 3) -> dict[str, Any]:
    probe_out = REPO / "data" / "observability" / "canary_sla_probe.json"
    cmd = [
        sys.executable, str(REPO / "tools" / "sla_probe.py"),
        "--base-url", base_url,
        "--iterations", str(iterations),
        "--out", str(probe_out),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if probe_out.exists():
        return json.loads(probe_out.read_text(encoding="utf-8"))
    return {"global_success_rate": 0.0, "error": proc.stderr or proc.stdout}


def apply_traffic_weight(percent: int, *, dry_run: bool) -> dict[str, Any]:
    """Best-effort traffic split update.

    When ``VOLC_ACCESS_KEY`` / ``VOLC_SECRET_KEY`` and ``VEFAAS_CANARY_UPSTREAMS``
    are set, delegates to ``deploy/cn-volc-vefaas/deploy.py --canary-weight``.
    Otherwise returns a manual snippet for operators.
    """
    import os
    snippet = (
        f"# Manual: set canary traffic to {percent}% on API Gateway\n"
        f"volc apig UpdateRoute --route-id $ROUTE_ID "
        f"--canary-weight {percent} --stable-weight {100 - percent}\n"
    )
    if dry_run:
        return {"backend": "dry_run", "percent": percent, "manual": snippet}
    if os.environ.get("VOLC_ACCESS_KEY") and os.environ.get("VEFAAS_CANARY_ROUTE_ID"):
        deploy = REPO / "deploy" / "cn-volc-vefaas" / "deploy.py"
        if deploy.exists():
            proc = subprocess.run(
                [sys.executable, str(deploy), "--canary-weight", str(percent)],
                capture_output=True, text=True, timeout=300,
            )
            if proc.returncode == 0:
                return {"backend": "volc_apig", "percent": percent}
            return {"backend": "volc_apig_failed", "percent": percent,
                    "stderr": proc.stderr[-500:]}
    return {"backend": "manual", "percent": percent, "manual": snippet}


def write_ga_notice(state: dict[str, Any]) -> None:
    GA_NOTICE_PATH.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Xiaoyunque V10 · General Availability",
        "",
        f"**Released:** {state.get('ga_at', _utc_now())}",
        "",
        "## What's new",
        "- 11-chapter V10 pipeline: text → visual → QA loop → AV synth → export",
        "- Wizard / Pro dual-mode dashboard",
        "- Team org + `/api/v1` public API with rate limits",
        "- 10 viral templates, pause-gate per-step confirmation, scheduled publishing",
        "- Multi-format export: GIF, frame sequences, storyboard grid, platform copy",
        "",
        "## Rollout history",
        "",
    ]
    for st in state.get("stages", []):
        pct = st.get("percent", "?")
        status = st.get("status", "?")
        sla = st.get("sla_probe", {})
        rate = sla.get("global_success_rate", "n/a")
        lines.append(f"- **{pct}%** — {status} (SLA success rate: {rate})")
    lines += [
        "",
        "## Upgrade notes",
        "- Run `alembic -c backend/alembic.ini upgrade head` before deploy",
        "- Set `pipeline_version=v10` on new jobs (default for wizard/pro UI)",
        "- Legacy dashboard remains at `/dashboard` (unchanged)",
        "",
    ]
    GA_NOTICE_PATH.write_text("\n".join(lines), encoding="utf-8")


def advance_stage(
    base_url: str,
    percent: int,
    *,
    dry_run: bool,
    min_success_rate: float,
    observe_minutes: float,
) -> bool:
    print(f"\n=== Canary stage {percent}% ===")
    traffic = apply_traffic_weight(percent, dry_run=dry_run)
    print(f"Traffic: {json.dumps(traffic, ensure_ascii=False, indent=2)}")
    if observe_minutes > 0 and not dry_run:
        print(f"Observing for {observe_minutes:.0f} minutes …")
        time.sleep(observe_minutes * 60)
    if dry_run:
        sla = {"global_success_rate": 1.0, "skipped": True, "reason": "dry_run"}
        print("SLA probe skipped (dry-run)")
    else:
        sla = run_sla_probe(base_url)
        rate = float(sla.get("global_success_rate") or 0.0)
        print(f"SLA probe global success rate: {rate:.2%}")
    rate = float(sla.get("global_success_rate") or 0.0)
    ok = dry_run or rate >= min_success_rate
    stage_rec = {
        "percent": percent,
        "started_at": _utc_now(),
        "traffic": traffic,
        "sla_probe": sla,
        "status": "passed" if ok else "failed",
    }
    state = load_state()
    state["current_percent"] = percent if ok else state.get("current_percent", 0)
    stages = [s for s in state.get("stages", []) if s.get("percent") != percent]
    stages.append(stage_rec)
    state["stages"] = stages
    if percent == 100 and ok:
        state["ga_at"] = _utc_now()
        write_ga_notice(state)
        print(f"GA notice written: {GA_NOTICE_PATH}")
    save_state(state)
    if not ok:
        print(f"ABORT: success rate {rate:.2%} < {min_success_rate:.2%}", file=sys.stderr)
    return ok


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="V10 veFaaS canary rollout")
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--stage", type=int, choices=STAGES,
                        help="run a single stage (10/30/100)")
    parser.add_argument("--auto-advance", action="store_true",
                        help="run 10→30→100 sequentially")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--observe-minutes", type=float, default=0.0,
                        help="wait N minutes between probe and next stage (0=skip)")
    parser.add_argument("--min-success-rate", type=float, default=0.99)
    args = parser.parse_args(argv)

    if args.stage is not None:
        ok = advance_stage(
            args.base_url, args.stage, dry_run=args.dry_run,
            min_success_rate=args.min_success_rate,
            observe_minutes=args.observe_minutes,
        )
        return 0 if ok else 1

    if args.auto_advance:
        for pct in STAGES:
            ok = advance_stage(
                args.base_url, pct, dry_run=args.dry_run,
                min_success_rate=args.min_success_rate,
                observe_minutes=args.observe_minutes,
            )
            if not ok:
                return 1
        return 0

    parser.error("provide --stage or --auto-advance")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
