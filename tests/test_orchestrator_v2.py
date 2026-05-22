"""Phase 1: orchestrator_v2 e2e in mock mode."""
import json
import pathlib
import tempfile

from src.pipeline.orchestrator_v2 import PipelineOrchestratorV2


def test_run_produces_master_and_scores(tmp_path: pathlib.Path):
    orch = PipelineOrchestratorV2(
        work_root=tmp_path,
        use_real_apis=False,
        genre="ancient",
    )
    events: list[tuple] = []

    def on_progress(step, pct, msg, art):
        events.append((step, pct, msg))

    novel = (
        "夜色低垂，少女白衣立于古寺檐下。她眉间一点朱砂，目光清亮如月，仿佛千年间从未磨损。"
        "书生执卷而过，二人擦肩，命运在此刻被悄悄按下了启动键。"
        "兰若寺的钟声响起，她转身离去，留下一串轻浅的脚印。"
    )
    result = orch.run(
        job_id=1,
        novel_excerpt=novel,
        style="ancient_3d_guoman",
        episodes=1,
        on_progress=on_progress,
        version_no=1,
    )
    assert pathlib.Path(result.result_url).exists()
    # 7-dim scores present + reasonable
    assert set(result.scores_7d.keys()) >= {"structure", "style", "detail"}
    assert all(0.0 <= v <= 10.0 for v in result.scores_7d.values())
    # Version snapshot persisted
    versions = list((tmp_path / "artifacts" / "versions").iterdir())
    assert any(v.name.startswith("v0001") for v in versions)
    # Step labels emitted in order
    steps_seen = sorted({s for s, _, _ in events})
    assert steps_seen == [1, 2, 3, 4, 5, 6]


def test_run_with_theme_mode(tmp_path: pathlib.Path):
    orch = PipelineOrchestratorV2(tmp_path, use_real_apis=False, genre="modern")
    result = orch.run(
        job_id=2,
        novel_excerpt="",
        style="modern_cinematic",
        episodes=1,
        mode="theme",
        theme="高考重生 — 少女回到 17 岁要改写父母的婚姻。",
        genre="modern",
    )
    assert result.quality_score > 0
    assert result.scores_7d


def test_step_artifacts_contain_compliance_and_version(tmp_path: pathlib.Path):
    orch = PipelineOrchestratorV2(tmp_path, use_real_apis=False)
    result = orch.run(
        job_id=3,
        novel_excerpt="这是一个完全原创的短剧文本，主角少年初入江湖，遇见神秘门派。" * 5,
        style="ancient_3d_guoman",
        episodes=1,
    )
    artifacts = result.step_artifacts
    step1 = artifacts["steps"]["1"]
    assert "compliance" in step1
    assert step1["compliance"]["copyright_blacklist"] == "ok"
    assert "version" in artifacts
    assert artifacts["version"]["version_no"] == 1
