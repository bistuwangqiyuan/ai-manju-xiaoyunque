"""Shell 1 orchestrator: novel → events → episodes → skylark prompts → validated YAML."""
from __future__ import annotations

import argparse
import json
import logging
import pathlib
import sys
from typing import Callable

import yaml

_REPO = pathlib.Path(__file__).resolve().parents[2]

from .extract_events import EventExtractor
from .write_episodes import EpisodeWriter
from .reformat_skylark import SkylarkPromptFormatter
from .schema_validate import EpisodeSchemaValidator

_log = logging.getLogger(__name__)


def run(
    novel_text: str,
    *,
    output_path: str | pathlib.Path | None = None,
    episodes_count: int = 10,
    on_log: Callable[[str], None] | None = None,
) -> dict:
    """Run full Shell 1 pipeline; return episodes dict."""

    def log(msg: str) -> None:
        _log.info(msg)
        if on_log:
            on_log(msg)

    log("shell1: DeepSeek 事件抽取")
    extractor = EventExtractor()
    events = extractor.extract(novel_text)

    log(f"shell1: Claude 分集编剧 ({episodes_count} 集)")
    writer = EpisodeWriter()
    outline = "\n".join(f"- {e.name}: {e.summary}" for e in events)
    episodes = writer.write_all(events, outline)

    log("shell1: 豆包友好化 + Gemini schema 校验")
    formatter = SkylarkPromptFormatter()
    for ep in episodes:
        ep.raw["skylark_prompt"] = formatter.format_episode(ep)

    validator = EpisodeSchemaValidator()
    episodes = validator.validate_and_repair(episodes)
    plan = {"episodes": [ep.raw for ep in episodes]}

    out = output_path or (_REPO / "prompts" / "episodes" / "ep01-ep10.yaml")
    out = pathlib.Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        yaml.safe_dump(plan, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    log(f"shell1: 已写入 {out}")
    return plan


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Shell 1 screenwriter pipeline")
    parser.add_argument("--novel", required=True, help="Path to novel markdown")
    parser.add_argument("--output", default=None)
    parser.add_argument("--episodes", type=int, default=10)
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO)
    novel_path = pathlib.Path(args.novel)
    text = novel_path.read_text(encoding="utf-8")
    run(text, output_path=args.output, episodes_count=args.episodes)
    return 0


if __name__ == "__main__":
    sys.exit(main())
