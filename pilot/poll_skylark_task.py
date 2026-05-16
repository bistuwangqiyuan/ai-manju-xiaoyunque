"""Poll an existing Skylark task_id to completion and archive mp4.

Usage:
    python pilot/poll_skylark_task.py <task_id> <ep_id_label>
"""
from __future__ import annotations

import pathlib
import shutil
import sys


_REPO = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO))


def load_env_file(path: pathlib.Path) -> None:
    import os

    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, _, val = line.partition("=")
        key = key.strip()
        val = val.strip()
        if "#" in val:
            val = val.split("#", 1)[0].strip()
        if key and val:
            os.environ.setdefault(key, val)


def main(argv: list[str]) -> int:
    import os

    if len(argv) != 3:
        print("usage: python pilot/poll_skylark_task.py <task_id> <ep_id>", file=sys.stderr)
        return 2

    task_id, ep_id = argv[1], argv[2]
    load_env_file(_REPO / ".env")
    os.environ.setdefault("STORAGE_ROOT", str(_REPO / "data" / "pilot_short_skylark"))

    from src.shell3_skylark_engine import SkylarkAgentV2WithRefClient

    client = SkylarkAgentV2WithRefClient(
        poll_interval_seconds=10.0,
        timeout_seconds=7200.0,
        aigc_meta=None,
    )
    result = client.wait_and_archive(task_id, ep_id=ep_id)
    out_root = _REPO / "data" / "pilot_short_skylark"
    out_root.mkdir(parents=True, exist_ok=True)
    dest = out_root / f"{ep_id}.mp4"
    shutil.copy2(result.archived_video_path, dest)
    print(dest.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
