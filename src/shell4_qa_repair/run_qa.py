"""CLI entry: run Shell-4 QA + auto-repair loop on a finished episode.

Usage:
    python -m src.shell4_qa_repair.run_qa --episode ep01
    python -m src.shell4_qa_repair.run_qa --episode ep01 --mock
    python -m src.shell4_qa_repair.run_qa --shots data/episodes/ep01/shots --out qa_report.json
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import pathlib
import sys
from typing import Iterable

from .auto_diagnose import diagnose
from .repair_router import RepairContext, RepairRouter
from .seven_dim_scorer import (
    SEVEN_DIM_KEYS,
    PASS_THRESHOLD,
    SevenDimensionScorer,
    ShotScore,
)


_log = logging.getLogger(__name__)


def _build_default_router() -> RepairRouter:
    """Best-effort registration of all known repair routes.

    Each handler is constructed lazily so that missing API keys (e.g. no
    REPLICATE_API_TOKEN in mock CI) skip that route gracefully without
    breaking the whole router. Class names are pinned to the actual
    implementations in this package — see docs/api-contracts-2026-05.md
    section "Drift summary" row B-1 for the historic name mismatch fixed
    in v8.
    """
    router = RepairRouter()
    handlers: dict[str, object] = {}
    try:
        from .repair_wan_flf import WanFlfRepair
        handlers["face_drift"] = WanFlfRepair()
    except Exception:
        pass
    try:
        from .repair_hedra import HedraRepair
        handlers["closeup_lipsync"] = HedraRepair()
    except Exception:
        pass
    try:
        from .repair_flux_kontext import FluxKontextShotRepair
        handlers["costume_drift"] = FluxKontextShotRepair()
    except Exception:
        pass
    try:
        from .repair_aleph import AlephRepair
        handlers["cross_show_style"] = AlephRepair()
    except Exception:
        pass
    try:
        from .repair_veo31 import Veo31Repair
        handlers["climax_enhance"] = Veo31Repair()
    except Exception:
        pass
    try:
        from .repair_sora2 import Sora2ProRepair
        handlers["god_tier"] = Sora2ProRepair()
    except Exception:
        pass

    for route, h in handlers.items():
        router.routes[route] = h
    return router


def _iter_shot_paths(shot_dir: pathlib.Path) -> Iterable[pathlib.Path]:
    if not shot_dir.exists():
        return []
    return sorted(p for p in shot_dir.iterdir() if p.suffix.lower() in {".mp4", ".mov", ".jpg", ".png"})


def run_qa(
    *,
    episode: str | None = None,
    shots_dir: str | pathlib.Path | None = None,
    canonical_image_url: str | None = None,
    out_path: str | pathlib.Path | None = None,
    mock: bool = False,
    repair: bool = True,
    pass_threshold: float = PASS_THRESHOLD,
    max_iter: int = 2,
) -> dict:
    """Run QA + (optionally) repair on every shot in ``shots_dir``.

    Returns a structured report:
        {
          "episode": "ep01",
          "shots": [ { ShotScore.to_dict() + repair history } ... ],
          "summary": { "avg_overall": .., "pass_rate": .., "n_repaired": .. }
        }
    """
    if mock:
        os.environ["FORCE_MOCK_SCORER"] = "1"

    if shots_dir is None:
        if episode is None:
            raise SystemExit("Either --episode or --shots is required")
        shots_dir = pathlib.Path("data") / "episodes" / episode / "shots"
    shots_dir = pathlib.Path(shots_dir)

    scorer = SevenDimensionScorer(pass_threshold=pass_threshold)
    router = _build_default_router() if repair else RepairRouter()

    shots: list[dict] = []
    paths = list(_iter_shot_paths(shots_dir))
    if not paths:
        _log.warning("no shot files under %s", shots_dir)

    for idx, p in enumerate(paths):
        score = scorer.score(idx + 1, p, canonical_image_url=canonical_image_url)
        diag = [d.__dict__ for d in diagnose(score, pass_threshold=pass_threshold)]
        record: dict = {
            "shot_id": idx + 1,
            "path": str(p),
            "score": score.to_dict(),
            "diagnose": diag,
        }

        if repair and not score.passed:
            ctx = RepairContext(
                shot_id=idx + 1,
                shot_url=str(p),
                shot_prompt="",
                canonical_image_url=canonical_image_url or "",
            )
            try:
                loop = router.repair_until_pass(
                    ctx,
                    scorer=scorer,
                    max_iter=max_iter,
                    pass_threshold=pass_threshold,
                )
                record["repair"] = loop.to_dict()
            except Exception as e:  # noqa: BLE001
                record["repair"] = {"error": str(e)}

        shots.append(record)

    pass_n = sum(1 for s in shots if s["score"]["passed"])
    repaired_n = sum(1 for s in shots if s.get("repair", {}).get("passed"))
    avg = sum(s["score"]["overall"] for s in shots) / max(len(shots), 1)
    report = {
        "episode": episode,
        "shots_dir": str(shots_dir),
        "shots": shots,
        "summary": {
            "n_shots": len(shots),
            "n_passed_initial": pass_n,
            "n_passed_after_repair": pass_n + repaired_n,
            "pass_rate": round(pass_n / max(len(shots), 1), 3),
            "avg_overall": round(avg, 2),
            "pass_threshold": pass_threshold,
        },
    }

    if out_path:
        out = pathlib.Path(out_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        _log.info("wrote QA report → %s", out)

    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="run_qa")
    parser.add_argument("--episode", default=None)
    parser.add_argument("--shots", default=None, help="shots directory (overrides --episode)")
    parser.add_argument("--out", default=None, help="output JSON path")
    parser.add_argument("--canonical", default=None, help="canonical reference image URL")
    parser.add_argument("--mock", action="store_true", help="force mock scorer (no API calls)")
    parser.add_argument("--no-repair", dest="repair", action="store_false")
    parser.add_argument("--threshold", type=float, default=PASS_THRESHOLD)
    parser.add_argument("--max-iter", type=int, default=2)
    args = parser.parse_args(argv)

    logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO").upper())
    report = run_qa(
        episode=args.episode,
        shots_dir=args.shots,
        canonical_image_url=args.canonical,
        out_path=args.out,
        mock=args.mock,
        repair=args.repair,
        pass_threshold=args.threshold,
        max_iter=args.max_iter,
    )
    if args.out is None:
        print(json.dumps(report["summary"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
