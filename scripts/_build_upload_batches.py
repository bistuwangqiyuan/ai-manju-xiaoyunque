"""Generate per-batch JSON files for MCP `manageHosting upload` (files-mode).

The CLoudBase tcb hosting deploy and bulk manageHosting upload both hang up
on this network. Per-file upload works. We chunk web/out into ~6MB / ≤25 file
batches and save each as JSON for direct shell-level reading.
"""
from __future__ import annotations

import json
import pathlib
import sys

BASE = pathlib.Path(r"D:\project\cursor\dev\ai-manju-xiaoyunque\web\out")
OUT_DIR = pathlib.Path(r"C:\Users\HUAWEI\AppData\Local\Temp")

MAX_SIZE = 6 * 1024 * 1024
MAX_FILES = 25


def main() -> int:
    files = sorted(p for p in BASE.rglob("*") if p.is_file())
    batches: list[list[dict]] = []
    current: list[dict] = []
    cur_size = 0
    for p in files:
        size = p.stat().st_size
        if current and (cur_size + size > MAX_SIZE or len(current) >= MAX_FILES):
            batches.append(current)
            current, cur_size = [], 0
        rel = p.relative_to(BASE).as_posix()
        current.append({"localPath": str(p), "cloudPath": rel, "size": size})
        cur_size += size
    if current:
        batches.append(current)

    for i, b in enumerate(batches):
        out = OUT_DIR / f"xyq_batch_{i}.json"
        clean = [{"localPath": x["localPath"], "cloudPath": x["cloudPath"]} for x in b]
        out.write_text(json.dumps(clean, ensure_ascii=False), encoding="utf-8")
        size_mb = sum(x["size"] for x in b) / 1024 / 1024
        print(f"batch {i}: {len(b)} files, {size_mb:.2f} MB -> {out}")

    print(f"\nTotal: {len(files)} files, {len(batches)} batches")
    return 0


if __name__ == "__main__":
    sys.exit(main())
