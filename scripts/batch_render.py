#!/usr/bin/env python3
"""Batch-render multiple episodes via the 6-step orchestrator."""
from __future__ import annotations

import argparse
import logging
import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO))

logging.basicConfig(level=logging.INFO)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--episodes", default="ep01,ep02,ep03", help="Comma-separated ep ids")
    parser.add_argument("--work-dir", default="data/batch_render")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    from src.pipeline.orchestrator import PipelineOrchestrator

    ep_ids = [e.strip() for e in args.episodes.split(",") if e.strip()]
    work = _REPO / args.work_dir
    orch = PipelineOrchestrator(work)

    import yaml
    plan_path = _REPO / "prompts" / "episodes" / "ep01-ep10.yaml"
    plan = yaml.safe_load(plan_path.read_text(encoding="utf-8"))
    by_id = {e["episode_id"]: e for e in plan.get("episodes", [])}

    for i, eid in enumerate(ep_ids):
        ep = by_id.get(eid)
        if not ep:
            logging.error("Unknown episode %s", eid)
            continue
        if args.dry_run:
            logging.info("Would render %s: %s", eid, ep.get("title"))
            continue
        logging.info("Rendering %s …", eid)
        result = orch.run(
            job_id=1000 + i,
            novel_excerpt=ep.get("synopsis", "聊斋聂小倩"),
            style="ancient_3d_guoman",
            episodes=1,
        )
        logging.info("Done %s score=%s url=%s", eid, result.quality_score, result.result_url)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
