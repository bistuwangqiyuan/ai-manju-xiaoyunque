"""V10 §5.2 — Checkpoint resumer.

Persists per-step / per-shot status to ``<job_dir>/checkpoint.json`` so a
crashed or pre-empted worker can pick up exactly where it left off.

Schema::

    {
        "job_id": 42,
        "updated_at": "2026-05-26T12:34:56Z",
        "steps": {"1": "done", "2": "done", "3": "running", "4": "pending"},
        "shots": {"ep01:shot003": "done", "ep01:shot004": "failed"}
    }
"""
from __future__ import annotations

import json
import pathlib
from datetime import datetime, timezone
from typing import Iterable


CHECKPOINT_NAME = "checkpoint.json"


class Checkpoint:
    def __init__(self, job_dir: str | pathlib.Path):
        self.job_dir = pathlib.Path(job_dir)
        self.job_dir.mkdir(parents=True, exist_ok=True)
        self.path = self.job_dir / CHECKPOINT_NAME
        self.data: dict = {"steps": {}, "shots": {}}
        if self.path.exists():
            try:
                self.data = json.loads(self.path.read_text(encoding="utf-8"))
                self.data.setdefault("steps", {})
                self.data.setdefault("shots", {})
            except Exception:
                pass

    # ---------------- steps ------------------------------------------------
    def mark_step(self, step_no: int, status: str) -> None:
        self.data["steps"][str(step_no)] = status
        self._flush()

    def step_status(self, step_no: int) -> str:
        return self.data["steps"].get(str(step_no), "pending")

    def steps_done(self) -> list[int]:
        return [int(k) for k, v in self.data["steps"].items() if v == "done"]

    # ---------------- shots ------------------------------------------------
    @staticmethod
    def shot_key(episode: int, shot: int) -> str:
        return f"ep{episode:02d}:shot{shot:03d}"

    def mark_shot(self, episode: int, shot: int, status: str) -> None:
        self.data["shots"][self.shot_key(episode, shot)] = status
        self._flush()

    def shot_status(self, episode: int, shot: int) -> str:
        return self.data["shots"].get(self.shot_key(episode, shot), "pending")

    def shots_remaining(self, planned: Iterable[tuple[int, int]]) -> list[tuple[int, int]]:
        return [(ep, sh) for ep, sh in planned
                if self.shot_status(ep, sh) not in ("done",)]

    def pending_only(self, planned: Iterable[tuple[int, int]]) -> list[tuple[int, int]]:
        return [(ep, sh) for ep, sh in planned
                if self.shot_status(ep, sh) in ("pending", "failed")]

    # ---------------- bulk -------------------------------------------------
    def progress_summary(self) -> dict:
        steps = self.data["steps"]
        shots = self.data["shots"]
        done_shots = sum(1 for v in shots.values() if v == "done")
        failed_shots = sum(1 for v in shots.values() if v == "failed")
        return {
            "steps": dict(steps),
            "shots_total": len(shots),
            "shots_done": done_shots,
            "shots_failed": failed_shots,
            "shots_pending": len(shots) - done_shots - failed_shots,
            "updated_at": self.data.get("updated_at"),
        }

    def reset_failed(self) -> int:
        n = 0
        for k, v in list(self.data["shots"].items()):
            if v == "failed":
                self.data["shots"][k] = "pending"
                n += 1
        if n:
            self._flush()
        return n

    def _flush(self) -> None:
        self.data["updated_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        self.path.write_text(json.dumps(self.data, ensure_ascii=False, indent=2),
                             encoding="utf-8")


__all__ = ["Checkpoint", "CHECKPOINT_NAME"]
