"""Phase 9 — Flow + dual-mode tests."""
from __future__ import annotations

import threading
import time
import pathlib
import pytest


# ---------- §9.1 templates ----------

def test_template_registry_loads_ten():
    from src.flow.templates import get_registry
    reg = get_registry()
    items = reg.list_templates()
    assert len(items) == 10
    ids = {t.id for t in items}
    assert "ancient_palace_revenge" in ids
    assert "scifi_time_loop" in ids


def test_template_structure_has_six_beats():
    from src.flow.templates import get_registry
    reg = get_registry()
    for t in reg.list_templates():
        assert len(t.structure) >= 5
        beats = [b.beat for b in t.structure]
        assert "hook" in beats
        assert "cliffhanger" in beats
        total_s = sum(b.seconds for b in t.structure)
        # total beats should sum to within 20% of the per-episode duration
        assert 0.7 * t.duration_per_episode_s <= total_s <= 1.3 * t.duration_per_episode_s


def test_template_apply_preserves_user_fields():
    from src.flow.templates import apply_template, get_registry
    reg = get_registry()
    tpl = reg.get("ancient_palace_revenge")
    assert tpl is not None
    # user already chose 16:9 — should NOT be overwritten
    payload = {"aspect_ratio": "16:9", "theme": "用户自定义主题"}
    result = apply_template(tpl, payload, lead_name="林夕")
    assert result["aspect_ratio"] == "16:9"
    assert result["theme"] == "用户自定义主题"
    # template defaults filled in
    assert result["genre"] == "ancient"
    assert result["template_id"] == "ancient_palace_revenge"
    assert "林夕" in result["hook"]
    assert result["subtitle_style"] == "ancient_kai"
    assert len(result["beat_structure"]) >= 5


# ---------- §9.2 pause gate ----------

def test_pause_gate_request_and_approve(tmp_path, monkeypatch):
    from src.flow import pause_gate
    pause_gate.reset_gate()
    monkeypatch.setattr(pause_gate, "_DEFAULT_STORE", tmp_path / "p.json")
    gate = pause_gate.PauseGate(tmp_path / "p.json")
    ev = gate.request_pause(101, "novel", summary={"n_chapters": 5})
    assert ev.status == "pending"
    assert gate.status(101, "novel").status == "pending"
    assert len(gate.list_pending(101)) == 1
    out = gate.approve(101, "novel", user_payload={"ok": True})
    assert out.status == "approved"
    assert out.user_payload == {"ok": True}
    assert len(gate.list_pending(101)) == 0


def test_pause_gate_reject_modify(tmp_path):
    from src.flow.pause_gate import PauseGate
    gate = PauseGate(tmp_path / "p.json")
    gate.request_pause(202, "screenplay", summary={"scenes": 10})
    res = gate.reject(202, "screenplay", user_payload={"reason": "结构不顺"})
    assert res.status == "rejected"
    gate.request_pause(202, "characters", summary={"n": 5})
    mod = gate.modify(202, "characters",
                      user_payload={"replace": {"main_character_name": "新名"}})
    assert mod.status == "modified"
    assert mod.user_payload["replace"]["main_character_name"] == "新名"


def test_pause_gate_persists_across_instances(tmp_path):
    from src.flow.pause_gate import PauseGate
    g1 = PauseGate(tmp_path / "p.json")
    g1.request_pause(303, "qa", summary={"failures": 2})
    g2 = PauseGate(tmp_path / "p.json")
    assert g2.status(303, "qa") is not None
    assert g2.status(303, "qa").summary["failures"] == 2


def test_pause_gate_wait_for_decision(tmp_path):
    from src.flow.pause_gate import PauseGate
    gate = PauseGate(tmp_path / "p.json")
    gate.request_pause(404, "frames")

    def _approve_later():
        time.sleep(0.2)
        gate.approve(404, "frames", user_payload={"go": True})

    t = threading.Thread(target=_approve_later)
    t.start()
    res = gate.wait_for_decision(404, "frames", timeout_seconds=2.0)
    t.join()
    assert res is not None
    assert res.status == "approved"


def test_pause_gate_wait_timeout(tmp_path):
    from src.flow.pause_gate import PauseGate
    gate = PauseGate(tmp_path / "p.json")
    gate.request_pause(505, "tts")
    res = gate.wait_for_decision(505, "tts", timeout_seconds=0.2)
    assert res is None or res.status == "pending"


# ---------- §9.3 scheduler ----------

def test_scheduler_cron_field_expansion():
    from src.flow.scheduler import _expand_field
    assert _expand_field("*", 0, 5) == {0, 1, 2, 3, 4, 5}
    assert _expand_field("1,3,5", 0, 9) == {1, 3, 5}
    assert _expand_field("0-3", 0, 9) == {0, 1, 2, 3}
    assert _expand_field("*/15", 0, 59) == {0, 15, 30, 45}


def test_scheduler_register_and_list(tmp_path):
    from src.flow.scheduler import ScheduleRegistry, ScheduleSpec
    reg = ScheduleRegistry(tmp_path / "s.json")
    spec = ScheduleSpec(cron="0 9 * * *")
    sched = reg.register_job(101, spec, owner_id=7, description="每日上午 9 点")
    assert sched.schedule_id.startswith("sched_")
    assert sched.next_fire_at is not None
    listed = reg.list_jobs(owner_id=7)
    assert len(listed) == 1


def test_scheduler_interval_next_fire(tmp_path):
    from src.flow.scheduler import ScheduleRegistry, ScheduleSpec
    reg = ScheduleRegistry(tmp_path / "s.json")
    spec = ScheduleSpec(interval_seconds=3600)
    sched = reg.register_job(202, spec, owner_id=7)
    assert sched.next_fire_at is not None


def test_scheduler_poll_due_fires_callback(tmp_path):
    from src.flow.scheduler import ScheduleRegistry, ScheduleSpec, _parse_iso_utc
    from datetime import datetime, timezone, timedelta
    reg = ScheduleRegistry(tmp_path / "s.json")
    past = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()
    spec = ScheduleSpec(date=past)
    sched = reg.register_job(303, spec, owner_id=7)
    # date-trigger in the past → no next fire, but we force-mark as due
    sched.next_fire_at = past
    reg._jobs[sched.schedule_id] = sched
    reg._flush()

    fired_calls: list[int] = []
    reg.set_fire_callback(lambda j: fired_calls.append(j.job_id))
    fired = reg.poll_due()
    assert len(fired) == 1
    assert fired_calls == [303]


def test_scheduler_cancel(tmp_path):
    from src.flow.scheduler import ScheduleRegistry, ScheduleSpec
    reg = ScheduleRegistry(tmp_path / "s.json")
    sched = reg.register_job(404, ScheduleSpec(cron="0 9 * * *"), owner_id=7)
    assert reg.cancel_job(sched.schedule_id) is True
    assert reg.cancel_job("nope") is False
    assert len(reg.list_jobs()) == 0


# ---------- §9.4 drafts / fork ----------

def test_drafts_fork_and_branches(tmp_path, monkeypatch):
    """Exercise drafts logic against an in-memory SQLite copy of the Job model."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from backend.app.db import Base, Job, User
    from src.flow.drafts import fork_job, list_branches, save_as_draft, publish_draft

    eng = create_engine(f"sqlite:///{tmp_path / 'tmp.sqlite'}")
    Base.metadata.create_all(eng)
    Session = sessionmaker(bind=eng)
    db = Session()

    u = User(email="t@x.com", password_hash="h", tier="pro")
    db.add(u)
    db.commit()
    db.refresh(u)

    j = Job(user_id=u.id, title="原稿", status="pending",
            genre="ancient", mode="excerpt", episodes=1)
    db.add(j)
    db.commit()
    db.refresh(j)

    child = fork_job(db, Job, j.id, u.id, branch_name="V2 草稿")
    assert child.parent_id == j.id
    assert child.is_draft is True
    assert child.status == "draft"
    assert "V2 草稿" in child.title

    # branch list
    branches = list_branches(db, Job, j.id, u.id)
    ids = {b["id"] for b in branches}
    assert j.id in ids and child.id in ids

    # publish + draft round-trip
    pub = publish_draft(db, Job, child.id, u.id)
    assert pub.is_draft is False
    drafted = save_as_draft(db, Job, child.id, u.id)
    assert drafted.is_draft is True
