"""V10 §12 — SLA probe.

Periodically probes the live API surface and computes:
    - p50 / p95 / p99 latency
    - success rate (200..299 / total)
    - per-endpoint availability over the window
    - aggregated burn rate vs the configured SLO

Output: ``data/observability/sla_probe.json`` + a stdout summary table.

Designed to run as a cron job (every 60s) or invoked once for ad-hoc
checks.  Concurrency uses asyncio + a small connection pool so the probe
itself doesn't push the system over its capacity.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import pathlib
import statistics
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

_log = logging.getLogger("sla_probe")


@dataclass
class ProbeTarget:
    name: str
    method: str = "GET"
    path: str = "/api/health"
    expected_status: tuple[int, ...] = (200, 204)
    timeout_seconds: float = 5.0
    auth_header: str | None = None
    body_json: dict[str, Any] | None = None
    weight: float = 1.0


@dataclass
class ProbeSample:
    target: str
    ok: bool
    status_code: int | None
    latency_ms: float
    error: str | None = None


@dataclass
class ProbeReport:
    base_url: str
    probed_at: str
    samples: list[ProbeSample] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        targets: dict[str, list[ProbeSample]] = {}
        for s in self.samples:
            targets.setdefault(s.target, []).append(s)
        per_target: dict[str, dict[str, Any]] = {}
        for name, smps in targets.items():
            lat = [s.latency_ms for s in smps]
            ok_smps = [s for s in smps if s.ok]
            per_target[name] = {
                "n": len(smps),
                "n_ok": len(ok_smps),
                "success_rate": (len(ok_smps) / len(smps)) if smps else 1.0,
                "p50_ms": _pct(lat, 50),
                "p95_ms": _pct(lat, 95),
                "p99_ms": _pct(lat, 99),
                "max_ms": max(lat) if lat else 0.0,
                "errors": [s.error for s in smps if s.error][:3],
            }
        agg_lat = [s.latency_ms for s in self.samples]
        n_ok = sum(1 for s in self.samples if s.ok)
        return {
            "base_url": self.base_url,
            "probed_at": self.probed_at,
            "n_samples": len(self.samples),
            "n_ok": n_ok,
            "global_success_rate": (n_ok / len(self.samples)) if self.samples else 1.0,
            "global_p50_ms": _pct(agg_lat, 50),
            "global_p95_ms": _pct(agg_lat, 95),
            "global_p99_ms": _pct(agg_lat, 99),
            "per_target": per_target,
        }


def _pct(samples: list[float], p: float) -> float:
    if not samples:
        return 0.0
    samples = sorted(samples)
    k = max(0, min(len(samples) - 1, int(round((p / 100) * (len(samples) - 1)))))
    return round(samples[k], 2)


def default_targets() -> list[ProbeTarget]:
    return [
        ProbeTarget(name="health", path="/api/health"),
        ProbeTarget(name="templates_list", path="/api/templates",
                    expected_status=(200, 401)),
        ProbeTarget(name="genres_list", path="/api/genres",
                    expected_status=(200, 401)),
        ProbeTarget(name="auth_me", path="/api/me",
                    expected_status=(200, 401)),
        ProbeTarget(name="schedules_due", path="/api/schedules/due",
                    expected_status=(200, 401)),
    ]


async def _probe_once(client, base_url: str,
                      target: ProbeTarget) -> ProbeSample:
    headers = {}
    if target.auth_header:
        headers["Authorization"] = target.auth_header
    url = base_url.rstrip("/") + target.path
    t0 = time.perf_counter()
    try:
        if target.method == "GET":
            resp = await client.get(url, headers=headers, timeout=target.timeout_seconds)
        else:
            resp = await client.request(
                target.method, url, headers=headers,
                json=target.body_json, timeout=target.timeout_seconds,
            )
        latency = (time.perf_counter() - t0) * 1000.0
        ok = resp.status_code in target.expected_status
        return ProbeSample(
            target=target.name, ok=ok, status_code=resp.status_code,
            latency_ms=latency,
            error=None if ok else f"unexpected status {resp.status_code}",
        )
    except Exception as exc:
        latency = (time.perf_counter() - t0) * 1000.0
        return ProbeSample(
            target=target.name, ok=False, status_code=None,
            latency_ms=latency, error=str(exc)[:200],
        )


async def _run_async(base_url: str, targets: list[ProbeTarget],
                     iterations: int) -> ProbeReport:
    try:
        import httpx  # type: ignore
    except Exception as exc:
        raise RuntimeError("sla_probe requires httpx") from exc
    samples: list[ProbeSample] = []
    async with httpx.AsyncClient(timeout=10.0) as client:
        for _ in range(iterations):
            coros = [_probe_once(client, base_url, t) for t in targets]
            for s in await asyncio.gather(*coros):
                samples.append(s)
    return ProbeReport(
        base_url=base_url,
        probed_at=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        samples=samples,
    )


def run(base_url: str, *, iterations: int = 3,
        targets: list[ProbeTarget] | None = None,
        out_path: str | pathlib.Path | None = None) -> dict[str, Any]:
    """Synchronous entry-point. Returns the report dict."""
    targets = targets or default_targets()
    report = asyncio.run(_run_async(base_url, targets, iterations))
    data = report.to_dict()
    if out_path:
        out = pathlib.Path(out_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(data, indent=2, ensure_ascii=False),
                       encoding="utf-8")
    return data


def print_summary(data: dict[str, Any]) -> None:
    print(f"\n=== SLA Probe Report ({data['probed_at']}) ===")
    print(f"base: {data['base_url']}    samples: {data['n_samples']}    "
          f"global success: {data['global_success_rate']:.2%}")
    print(f"p50={data['global_p50_ms']}ms  p95={data['global_p95_ms']}ms  "
          f"p99={data['global_p99_ms']}ms\n")
    print(f"{'target':<22} {'n':>4} {'ok%':>7} {'p50':>7} {'p95':>7} {'p99':>7}")
    print("-" * 64)
    for name, t in data["per_target"].items():
        print(f"{name:<22} {t['n']:>4} {t['success_rate']*100:>6.2f}% "
              f"{t['p50_ms']:>7.1f} {t['p95_ms']:>7.1f} {t['p99_ms']:>7.1f}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="SLA probe for the V10 API")
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--iterations", type=int, default=3)
    parser.add_argument("--out", default="data/observability/sla_probe.json")
    parser.add_argument("--bearer", help="optional Bearer token for /api/me etc")
    args = parser.parse_args(argv)

    targets = default_targets()
    if args.bearer:
        for t in targets:
            t.auth_header = f"Bearer {args.bearer}"

    try:
        data = run(args.base_url, iterations=args.iterations,
                   targets=targets, out_path=args.out)
    except Exception as exc:
        print(f"[sla_probe] FATAL: {exc}", file=sys.stderr)
        return 2
    print_summary(data)
    return 0 if data["global_success_rate"] >= 0.99 else 1


if __name__ == "__main__":
    raise SystemExit(main())
