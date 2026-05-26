"""Phase 5 — frame generation modules."""
from __future__ import annotations

import asyncio
import pathlib

import pytest


def test_storyboard_layouter_basic():
    from src.frame_gen import storyboard_layouter

    layout = storyboard_layouter.layout_episode(
        episode=1,
        scenes=[
            {"heading": "庭院", "atmosphere": "tense", "is_climax": False,
             "dialogue": [
                 {"speaker": "甲", "line": "为何在此？", "emotion": "questioning", "intensity": 3},
                 {"speaker": "乙", "line": "你猜不到？", "emotion": "cold", "intensity": 3},
                 {"speaker": "甲", "line": "你！", "emotion": "angry", "intensity": 5},
             ]},
            {"heading": "竹林", "atmosphere": "battle", "is_climax": True,
             "dialogue": [
                 {"speaker": "甲", "line": "出招吧！", "emotion": "emphatic", "intensity": 5},
             ]},
        ],
        target_panel_count=9,
    )
    assert layout.panel_count == 9
    # At least one reverse shot got triggered (we have 3 dialogue lines in scene 1)
    assert any(p.is_reverse_shot for p in layout.panels)


def test_storyboard_grid_size_helper():
    from src.frame_gen.storyboard_layouter import _grid_size_for
    assert _grid_size_for(9) == (3, 3)
    assert _grid_size_for(16) == (4, 4)
    rows, cols = _grid_size_for(25)
    assert rows * cols >= 25


def test_storyboard_grid_compose(tmp_path):
    try:
        from PIL import Image  # type: ignore
    except Exception:
        pytest.skip("PIL not installed")
    paths = []
    for i, col in enumerate([(200, 50, 50), (50, 200, 50), (50, 50, 200), (200, 200, 50)]):
        p = tmp_path / f"panel_{i}.png"
        Image.new("RGB", (200, 280), col).save(p)
        paths.append(p)
    from src.frame_gen.storyboard_grid import compose_grid
    out = tmp_path / "grid.jpg"
    res = compose_grid(paths, output_path=out, cell_size=(240, 360))
    assert res.output_path is not None
    assert pathlib.Path(res.output_path).exists()
    assert res.cols * res.rows >= 4
    assert pathlib.Path(res.manifest_path).exists()


def test_parallel_scheduler_basic():
    from src.frame_gen.parallel_scheduler import run_bounded

    async def make_task(i, fail_for_first=False):
        await asyncio.sleep(0.01)
        if fail_for_first and i == 0:
            raise RuntimeError("simulated")
        return f"result-{i}"

    tasks = [(f"t{i}", (lambda x=i: make_task(x))) for i in range(8)]
    stats = asyncio.run(run_bounded(tasks, concurrency=3))
    assert stats.total == 8
    assert stats.succeeded == 8
    assert stats.failed == 0
    assert stats.elapsed_s > 0


def test_parallel_scheduler_retries():
    from src.frame_gen.parallel_scheduler import run_bounded

    state = {"calls": 0}

    async def flaky():
        state["calls"] += 1
        if state["calls"] < 2:
            raise RuntimeError("first call fails")
        return "ok"

    stats = asyncio.run(run_bounded([("flaky", lambda: flaky())],
                                    concurrency=1, max_retries=2,
                                    retry_backoff_s=0.0))
    assert stats.succeeded == 1
    assert stats.per_task[0].attempts == 2


def test_checkpoint_resume(tmp_path):
    from src.frame_gen.resumer import Checkpoint

    cp = Checkpoint(tmp_path)
    cp.mark_step(1, "done")
    cp.mark_shot(1, 1, "done")
    cp.mark_shot(1, 2, "failed")
    cp.mark_shot(1, 3, "pending")

    cp2 = Checkpoint(tmp_path)
    assert cp2.step_status(1) == "done"
    assert cp2.step_status(2) == "pending"
    assert cp2.shot_status(1, 1) == "done"
    assert cp2.shot_status(1, 2) == "failed"
    remaining = cp2.shots_remaining([(1, 1), (1, 2), (1, 3), (1, 4)])
    assert (1, 1) not in remaining
    assert (1, 4) in remaining

    pending_only = cp2.pending_only([(1, 1), (1, 2), (1, 3), (1, 4)])
    assert (1, 1) not in pending_only
    assert (1, 2) in pending_only  # failed counts as pending
    assert (1, 3) in pending_only
    assert (1, 4) in pending_only

    n = cp2.reset_failed()
    assert n == 1
    assert cp2.shot_status(1, 2) == "pending"


def test_anatomy_detector_heuristic_routes():
    from src.frame_gen.anatomy_detector import detect

    rep = detect("/tmp/shot003_handfailure.png")
    assert rep.score_hand >= 5
    assert "hand_local" in rep.suggested_routes

    rep2 = detect("/tmp/shot001_face_issue.png")
    assert rep2.score_face >= 5
    assert "face_drift" in rep2.suggested_routes


def test_repair_hand_local_fallback(tmp_path):
    try:
        from PIL import Image
    except Exception:
        pytest.skip("PIL not installed")
    img_path = tmp_path / "shot.png"
    Image.new("RGB", (512, 768), (200, 200, 200)).save(img_path)
    from src.frame_gen.repair_hand_local import repair_hand_local
    res = repair_hand_local(image_path=img_path, output_dir=tmp_path / "out")
    assert res is not None
    assert len(res) >= 1
    assert pathlib.Path(res[0].crop_path).exists()
    assert pathlib.Path(res[0].mask_path).exists()
    x0, y0, x1, y1 = res[0].bbox_xyxy
    assert x1 > x0 and y1 > y0
