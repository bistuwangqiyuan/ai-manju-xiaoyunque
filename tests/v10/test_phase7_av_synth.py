"""Phase 7 — Audio/Video synthesis tests."""
from __future__ import annotations

import pathlib
import pytest


def test_voice_library_loads_six_roles():
    from src.audio.voice_library import get_library
    lib = get_library()
    roles = lib.list_roles()
    assert len(roles) == 6
    keys = {r["key"] for r in roles}
    assert keys >= {"shaonv", "yujie", "funv", "shaonian", "qingnian", "zhonglao"}


def test_voice_library_resolve_emotion_map():
    from src.audio.voice_library import get_library
    lib = get_library()
    v = lib.resolve("shaonv", emotion="sad", intensity=0.9)
    assert v.role == "shaonv"
    assert v.provider in ("doubao", "minimax", "elevenlabs")
    assert v.emotion_native == "cry"          # mapped from sad
    assert v.speed < 1.0                       # sad slows down
    assert v.vol < 1.0
    assert v.fallback_chain                    # has at least one fallback


def test_voice_library_provider_override():
    from src.audio.voice_library import get_library
    lib = get_library()
    v = lib.resolve("qingnian", emotion="angry", provider="elevenlabs", intensity=0.8)
    assert v.provider == "elevenlabs"
    assert v.speed > 1.0
    assert v.vol > 1.0


def test_auto_speed_volume_bounded():
    from src.audio.voice_library import auto_speed_volume
    for emo in ("happy", "sad", "angry", "neutral"):
        s, v = auto_speed_volume(emo, 1.0)
        assert 0.6 <= s <= 1.5
        assert 0.5 <= v <= 1.5


def test_dialogue_timeline_estimator():
    from src.audio.dialogue_timeline import build_timeline
    lines = [
        {"index": 0, "text": "你好，我是主角。", "language": "zh"},
        {"index": 1, "text": "我们终于见面了！", "language": "zh"},
        {"index": 2, "text": "Nice to meet you.", "language": "en"},
    ]
    tl = build_timeline(lines)
    assert len(tl.lines) == 3
    assert tl.lines[0].start == 0.0
    assert tl.lines[1].start > tl.lines[0].end
    assert tl.total_duration > 0
    assert tl.backend == "estimate"


def test_dialogue_timeline_to_ass_lines():
    from src.audio.dialogue_timeline import build_timeline, timeline_to_ass_lines
    tl = build_timeline([{"index": i, "text": f"测试第{i}句"} for i in range(3)])
    ass = timeline_to_ass_lines(tl, style="Voiceover")
    assert len(ass) == 3
    assert all(a.style == "Voiceover" for a in ass)
    assert ass[0].end_seconds > ass[0].start_seconds


def test_bgm_library_loads_and_filters():
    from src.audio.bgm_library import get_library
    lib = get_library()
    all_entries = lib.list_entries()
    assert len(all_entries) >= 20
    ancient = lib.filter(genres=["ancient"])
    assert len(ancient) >= 3
    for e in ancient:
        assert "ancient" in [g.lower() for g in e.genre]
    bpm_range = lib.filter(bpm_range=(120, 140))
    for e in bpm_range:
        assert 120 <= e.bpm <= 140


def test_bgm_recommender_lexical():
    from src.audio.bgm_recommender import recommend
    res = recommend("古风宫斗，紧张高潮决战", use_clap=False)
    assert res.backend == "lexical"
    assert res.top is not None
    assert res.top.score > 0
    # Should pick an ancient + tense/intense entry
    top_tags = set(res.top.entry.genre) | set(res.top.entry.mood)
    assert top_tags & {"ancient", "intense", "tense", "epic"}


def test_bgm_recommender_horror_match():
    from src.audio.bgm_recommender import recommend
    res = recommend("深夜回廊里诡异的脚步声，惊吓临爆", use_clap=False, top_k=3)
    assert res.top is not None
    top_tags = set(res.top.entry.genre) | set(res.top.entry.mood)
    assert top_tags & {"horror", "scary", "eerie"}


def test_beat_align_constant_grid():
    from src.audio.beat_align import compute_beats, snap_cuts
    grid = compute_beats(None, bpm_hint=120.0, audio_duration=60.0)
    assert grid.backend == "constant"
    assert grid.bpm == 120.0
    assert len(grid.beat_times) >= 120  # 2 beats/sec * 60s
    cuts = snap_cuts(grid, [1.1, 5.2, 10.3])
    # at 120 BPM, beat interval = 0.5s
    for c in cuts:
        if c.beat_index >= 0:
            assert abs(c.delta_sec) <= 0.30


def test_beat_align_snap_outside_max_drift():
    from src.audio.beat_align import compute_beats, snap_cuts
    grid = compute_beats(None, bpm_hint=10.0, audio_duration=60.0)  # interval 6s
    cuts = snap_cuts(grid, [3.0], max_drift=0.30)
    # nearest beat is 3s away → exceeds max_drift → not snapped
    assert cuts[0].beat_index == -1
    assert cuts[0].snapped_sec == 3.0


def test_sfx_auto_inject_matches_keywords():
    from src.audio.sfx_auto_inject import auto_inject
    actions = [
        {"text": "她推开门，走了进来", "start": 1.0, "end": 3.0},
        {"text": "雨声越来越大，他打了个寒颤", "start": 5.0, "end": 8.0},
        {"text": "玻璃突然碎裂", "start": 10.0, "end": 11.0},
    ]
    cues = auto_inject(actions)
    sfx_ids = [c.sfx_id for c in cues]
    assert any("door_open" in s for s in sfx_ids)
    assert any("rain" in s for s in sfx_ids)
    assert any("glass_break" in s for s in sfx_ids)
    for c in cues:
        assert c.volume > 0
        assert c.start_sec >= 0


def test_subtitle_styles_six_plus():
    from src.shell5_post_production.ass_subtitle import (
        SUBTITLE_STYLES, STYLE_PRESETS, resolve_style, render_ass, AssLine,
    )
    assert len(SUBTITLE_STYLES) >= 6
    # Six required: ancient seal, ancient kai, modern sans, modern round, danmu top, danmu roll
    must = {"AncientSeal", "AncientKai", "ModernSans", "ModernRound",
            "DanmuTop", "DanmuRoll"}
    assert must.issubset(set(SUBTITLE_STYLES))
    assert resolve_style("ancient_kai") == "AncientKai"
    assert resolve_style("bullet") == "DanmuRoll"
    assert resolve_style("unknown_style") == "Default"


def test_subtitle_render_picks_up_new_style(tmp_path):
    from src.shell5_post_production.ass_subtitle import AssLine, render_ass
    p = render_ass([
        AssLine(0.0, 2.5, "古风字幕", style="AncientSeal"),
        AssLine(2.5, 5.0, "现代字幕", style="ModernRound"),
    ], tmp_path / "test.ass")
    text = pathlib.Path(p).read_text(encoding="utf-8")
    assert "AncientSeal" in text
    assert "ModernRound" in text
    assert "古风字幕" in text


def test_transitions_build_plan_two_clips():
    from src.video.transitions import build_plan
    plan = build_plan(
        ["/tmp/a.mp4", "/tmp/b.mp4"],
        clip_durations=[5.0, 6.0],
        transitions=["fade"],
        transition_duration=0.6,
    )
    assert len(plan.transitions) == 1
    assert plan.transitions[0] == "fade"
    assert abs(plan.offsets[0] - 4.4) < 0.01
    assert abs(plan.total_duration - 11.0 + 0.6) < 0.01


def test_transitions_build_plan_three_clips():
    from src.video.transitions import build_plan
    plan = build_plan(
        ["/tmp/a.mp4", "/tmp/b.mp4", "/tmp/c.mp4"],
        clip_durations=[4.0, 4.0, 4.0],
        transitions=["fade", "wipeleft"],
        transition_duration=0.5,
    )
    assert plan.transitions == ["fade", "wipeleft"]
    assert plan.offsets[0] == pytest.approx(3.5)
    assert plan.offsets[1] == pytest.approx(7.0)


def test_transitions_invalid_falls_back():
    from src.video.transitions import build_plan
    plan = build_plan(
        ["/tmp/a.mp4", "/tmp/b.mp4"],
        clip_durations=[3.0, 3.0],
        transitions=["nonexistent_transition"],
    )
    assert plan.transitions[0] == "fade"


def test_transitions_build_filter_complex():
    from src.video.transitions import build_plan, build_filter_complex
    plan = build_plan(
        ["/tmp/a.mp4", "/tmp/b.mp4"],
        clip_durations=[5.0, 5.0],
        transition_duration=0.6,
    )
    inputs, fc, v_lab, a_lab = build_filter_complex(plan)
    assert inputs == ["-i", "/tmp/a.mp4", "-i", "/tmp/b.mp4"]
    assert "xfade=transition=fade" in fc
    assert v_lab == "[v1]"
    assert a_lab == "[a1]"


def test_lufs_normalize_passthrough_when_no_backend(tmp_path, monkeypatch):
    """If neither pyloudnorm nor ffmpeg are available, normalize falls back to copy."""
    from src.audio import lufs_normalize
    monkeypatch.setattr(lufs_normalize, "_try_pyloudnorm", lambda *a, **k: None)
    monkeypatch.setattr(lufs_normalize, "_ffmpeg_loudnorm", lambda *a, **k: None)
    in_p = tmp_path / "in.wav"
    in_p.write_bytes(b"RIFF\x00\x00\x00\x00WAVEfmt ")  # tiny fake content
    out_p = tmp_path / "out.wav"
    rep = lufs_normalize.normalize(in_p, out_p, target_lufs=-14.0)
    assert rep.backend == "passthrough"
    assert out_p.exists()


def test_compose_v10_dry_run_emits_full_plan(tmp_path, monkeypatch):
    """Smoke test of plan_and_compose_episode in dry_run mode."""
    from src.video import compose_v10
    # avoid ffprobe call by injecting clip durations
    monkeypatch.setattr(compose_v10.trans_mod, "_probe_duration", lambda p: 4.0)
    report = compose_v10.plan_and_compose_episode(
        shot_video_paths=["/tmp/shot_001.mp4", "/tmp/shot_002.mp4", "/tmp/shot_003.mp4"],
        output_path=tmp_path / "episode.mp4",
        dialogue_lines=[
            {"index": 0, "text": "古风的开场白。", "speaker_role": "shaonv"},
            {"index": 1, "text": "回应一句简短的话！", "speaker_role": "qingnian"},
        ],
        scene_text_for_bgm="古风宫斗紧张高潮",
        scene_actions=[{"text": "推开门走进", "start": 0.0, "end": 2.0}],
        transition_name="fade",
        subtitle_style="ancient_kai",
        dry_run=True,
        work_dir=tmp_path,
    )
    assert "concat_command" in report.to_dict()
    assert len(report.concat_command) > 5
    assert report.transition_plan["clip_paths"] == [
        "/tmp/shot_001.mp4", "/tmp/shot_002.mp4", "/tmp/shot_003.mp4",
    ]
    assert len(report.dialogue_timeline["lines"]) == 2
    assert report.bgm_choice  # at least metadata
    assert any("door_open" in c["sfx_id"] for c in report.sfx_cues)
    # subtitle should have been rendered
    assert report.subtitle_path is not None
    assert pathlib.Path(report.subtitle_path).exists()
