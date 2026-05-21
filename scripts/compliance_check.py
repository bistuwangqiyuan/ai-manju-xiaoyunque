#!/usr/bin/env python3
"""Run compliance gates on novel/script text and optional video outputs."""
from __future__ import annotations

import argparse
import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO))

from src.compliance import scan_copyright, scan_sensitive_text


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--text", type=pathlib.Path, help="Novel or script file")
    parser.add_argument("--all", action="store_true", help="Check bundled novel + prompts")
    args = parser.parse_args(argv)

    files: list[pathlib.Path] = []
    if args.text:
        files.append(args.text)
    if args.all:
        files.extend([
            _REPO / "novel-聂小倩.md",
            _REPO / "prompts" / "episodes" / "ep01-ep10.yaml",
        ])

    if not files:
        parser.error("Specify --text or --all")

    ok = True
    for f in files:
        if not f.exists():
            print(f"SKIP missing {f}")
            continue
        text = f.read_text(encoding="utf-8", errors="replace")
        cr = scan_copyright(text)
        sr = scan_sensitive_text(text)
        status = "PASS" if cr.passed and sr.passed else "FAIL"
        print(f"\n=== {f.name} [{status}] ===")
        print("  copyright:", "ok" if cr.passed else cr.hits)
        print("  sensitive:", "ok" if sr.passed else sr.hits)
        if not cr.passed or not sr.passed:
            ok = False

    print("\nAIGC checklist: see compliance/aigc_label_checklist.md")
    print("Filing template: see compliance/filing_template.md")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
