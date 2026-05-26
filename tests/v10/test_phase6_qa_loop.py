"""Phase 6 — QA closed-loop tests."""
from __future__ import annotations

import pathlib
import pytest


def test_visual_diagnose_pil_fallback(tmp_path):
    try:
        from PIL import Image  # type: ignore
    except Exception:
        pytest.skip("PIL not installed")
    p = tmp_path / "frame.png"
    img = Image.new("RGB", (256, 256), (180, 60, 60))
    # add a noisy patch in the bottom-right corner
    for x in range(200, 250):
        for y in range(200, 250):
            img.putpixel((x, y), ((x * 7) % 255, (y * 11) % 255, ((x + y) * 13) % 255))
    img.save(p)
    from src.qa import visual_diagnose
    rep = visual_diagnose.diagnose(p, output_dir=tmp_path / "out")
    assert rep.bbox_overlay_path is not None
    assert pathlib.Path(rep.bbox_overlay_path).exists()
    assert len(rep.regions) > 0
    assert rep.regions[0].label.startswith("hotspot")


def test_visual_diagnose_save_report(tmp_path):
    try:
        from PIL import Image
    except Exception:
        pytest.skip("PIL not installed")
    p = tmp_path / "frame.png"
    Image.new("RGB", (128, 128), (200, 200, 200)).save(p)
    from src.qa import visual_diagnose
    rep = visual_diagnose.diagnose(p, output_dir=tmp_path)
    out_json = visual_diagnose.save_report(rep, tmp_path / "report.json")
    assert out_json.exists()
    import json
    data = json.loads(out_json.read_text(encoding="utf-8"))
    assert "regions" in data
    assert "severity" in data


def test_style_consistency_identical_pair_high_score(tmp_path):
    try:
        from PIL import Image
    except Exception:
        pytest.skip("PIL not installed")
    p1 = tmp_path / "a.png"
    p2 = tmp_path / "b.png"
    Image.new("RGB", (64, 64), (123, 200, 50)).save(p1)
    Image.new("RGB", (64, 64), (123, 200, 50)).save(p2)
    from src.qa import style_consistency
    rep = style_consistency.score([p1, p2])
    assert rep.n_shots == 2
    assert rep.style_score_10 > 7.0
    assert rep.outlier_index in (0, 1)


def test_style_consistency_outlier_detection(tmp_path):
    try:
        from PIL import Image, ImageDraw
    except Exception:
        pytest.skip("PIL not installed")
    paths = []

    def make_circle_img(p, fill, radius_offset=0):
        img = Image.new("RGB", (128, 128), (240, 240, 240))
        draw = ImageDraw.Draw(img)
        r = 50 + radius_offset
        draw.ellipse((64 - r, 64 - r, 64 + r, 64 + r), fill=fill)
        img.save(p)

    # 3 similar shots (same style/colors), 1 dramatic outlier
    for i, (col, r_off) in enumerate([((200, 50, 50), 0), ((195, 55, 50), 1),
                                       ((205, 45, 55), -2)]):
        p = tmp_path / f"img_{i}.png"
        make_circle_img(p, col, r_off)
        paths.append(p)
    # Outlier: completely different layout (stripes)
    p_out = tmp_path / "img_3.png"
    out_img = Image.new("RGB", (128, 128), (255, 255, 255))
    od = ImageDraw.Draw(out_img)
    for y in range(0, 128, 16):
        od.rectangle((0, y, 128, y + 8), fill=(0, 0, 0))
    out_img.save(p_out)
    paths.append(p_out)

    from src.qa import style_consistency
    rep = style_consistency.score(paths)
    assert rep.n_shots == 4
    assert rep.outlier_index == 3


def test_repair_router_7d_fires_correct_route():
    from src.qa import repair_router
    plan = repair_router.plan_repair(
        image_path="/tmp/frame.png",
        scores_7d={"structure": 8, "style": 8, "detail": 8, "clarity": 8,
                   "color": 8, "no_deform": 4.5, "intent": 8},
    )
    assert len(plan.tasks) >= 1
    route_names = [t.route for t in plan.tasks]
    assert "hand_local" in route_names or "face_drift" in route_names or "god_tier" in route_names


def test_repair_router_safety_takes_priority():
    from src.qa import repair_router
    plan = repair_router.plan_repair(
        image_path="/tmp/frame.png",
        scores_7d={"structure": 8, "style": 8, "detail": 8, "clarity": 8,
                   "color": 8, "no_deform": 4.5, "intent": 8},
        safety_report={
            "blocked": True, "blocked_axes": ["adult"],
            "recommended_route": "cover_safe_swap",
        },
    )
    # safety route should be priority 1 → first task
    assert plan.tasks[0].route == "cover_safe_swap"
    assert plan.tasks[0].priority == 1


def test_repair_router_anatomy_hand_gets_addendum():
    from src.qa import repair_router

    def mask_provider(route, image_path):
        return f"/tmp/mock_mask_{route}.png" if route == "hand_local" else None

    plan = repair_router.plan_repair(
        image_path="/tmp/frame.png",
        anatomy_report={"score_face": 1, "score_hand": 7.5, "score_body": 2,
                        "suggested_routes": ["hand_local"]},
        mask_provider=mask_provider,
    )
    hand_task = next(t for t in plan.tasks if t.route == "hand_local")
    assert hand_task.mask_path == "/tmp/mock_mask_hand_local.png"
    assert "anatomically" in hand_task.prompt_addendum or "five fingers" in hand_task.prompt_addendum
    assert plan.estimated_cost_cny > 0


def test_repair_router_cost_estimate():
    from src.qa import repair_router
    plan = repair_router.plan_repair(
        image_path="/tmp/frame.png",
        scores_7d={"structure": 4, "style": 8, "detail": 8, "clarity": 8,
                   "color": 8, "no_deform": 8, "intent": 8},
    )
    # plan should have at least one route, and cost > 0
    assert plan.estimated_cost_cny > 0
    assert repair_router.route_backend("hand_local") == "flux_kontext_inpaint"
    assert repair_router.route_cost_cny("god_tier") == 1.45


def test_feedback_store_distill(tmp_path):
    from src.qa import feedback_distill as fd
    store = fd.FeedbackStore(tmp_path / "store.json")
    for i in range(5):
        store.add(job_id=1, episode=1, shot=i, genre="ancient",
                  route="hand_local", success=(i % 2 == 0),
                  before_score_10=6.0, after_score_10=7.5,
                  worst_axis="no_deform")
    store.add(job_id=1, episode=1, shot=10, genre="ancient",
              route="face_drift", success=True,
              before_score_10=5.8, after_score_10=8.0,
              worst_axis="no_deform")
    ins = store.distill()
    assert ins.sample_size == 6
    assert "hand_local" in ins.route_effectiveness
    assert ins.route_effectiveness["hand_local"]["success_rate"] == pytest.approx(0.6)
    # recurring axes
    assert ("no_deform", 6) in ins.recurring_axes_top10
    # suggested addenda for no_deform
    assert "no_deform" in ins.suggested_addenda


def test_feedback_store_roundtrip(tmp_path):
    from src.qa import feedback_distill as fd
    p = tmp_path / "store.json"
    s1 = fd.FeedbackStore(p)
    s1.add(job_id=42, episode=2, shot=3, genre="modern",
           route="cover_safe_swap", success=True)
    s2 = fd.FeedbackStore(p)
    assert len(s2) == 1
    assert s2.events[0].job_id == 42
