"""V10 capacity model — veFaaS / TOS / NAS / SQLite→Postgres tipping points.

Closed-form sizing of every persistence and compute resource needed
for given DAU + retention assumptions.

Run::

    python -m tools.data_models.capacity_model
"""
from __future__ import annotations

from dataclasses import dataclass, asdict

from tools.data_models._common import (
    parse_cli_out,
    render_table,
    write_json,
    write_markdown,
)


# ---------------------------------------------------------------------------
# Per-resource unit sizing
# ---------------------------------------------------------------------------
# Avg bytes per asset (after gzip / x264)
ASSET_BYTES = {
    "master_mp4_per_minute": 7.0 * 1024 * 1024,    # 7 MB / min (1080p @ 1Mbps)
    "rough_cut_per_minute": 8.5 * 1024 * 1024,
    "cover_jpg": 280 * 1024,
    "scene_jpg": 350 * 1024,
    "character_view_jpg": 320 * 1024,
    "storyboard_grid_jpg": 1.6 * 1024 * 1024,
    "tts_mp3_per_minute": 1.0 * 1024 * 1024,
    "bgm_mp3_per_minute": 1.0 * 1024 * 1024,
    "ass_subtitle": 18 * 1024,
    "log_json_per_job": 24 * 1024,
}

# SQLite stops being acceptable at ~200 concurrent writers (lock thrash)
SQLITE_LOCK_THRESHOLD_WRITERS = 200

# veFaaS instance sizing: 2 GB RAM, 1 vCPU, supports ~3 parallel manju tasks
WORKERS_PER_VEFAAS_INSTANCE = 3
VEFAAS_INSTANCE_RAM_GB = 2


@dataclass
class CapacityScenario:
    name: str
    daily_active_users: int
    avg_projects_per_dau: float
    avg_episodes_per_project: float = 8
    avg_minutes_per_episode: float = 1.5
    storage_retention_days: int = 90
    shots_per_episode: int = 16
    concurrent_writers_peak_ratio: float = 0.04   # 4% DAU writing simultaneously


def scenarios() -> list[CapacityScenario]:
    return [
        CapacityScenario("v10_pilot",   1_000,   0.20),
        CapacityScenario("v10_launch", 10_000,   0.30),
        CapacityScenario("v10_scale", 100_000,   0.25),
        CapacityScenario("v10_peak",  500_000,   0.20),
    ]


def derive(s: CapacityScenario) -> dict:
    daily_projects = s.daily_active_users * s.avg_projects_per_dau
    daily_episodes = daily_projects * s.avg_episodes_per_project
    daily_minutes = daily_episodes * s.avg_minutes_per_episode
    daily_shots = daily_episodes * s.shots_per_episode

    # Storage (cumulative over retention)
    total_minutes_retained = daily_minutes * s.storage_retention_days
    total_shots_retained = daily_shots * s.storage_retention_days
    total_projects_retained = daily_projects * s.storage_retention_days

    master_b = total_minutes_retained * ASSET_BYTES["master_mp4_per_minute"]
    rough_b  = total_minutes_retained * ASSET_BYTES["rough_cut_per_minute"]
    cover_b  = total_projects_retained * ASSET_BYTES["cover_jpg"]
    scene_b  = total_projects_retained * 6 * ASSET_BYTES["scene_jpg"]    # 6 scenes
    char_b   = total_projects_retained * 5 * 3 * ASSET_BYTES["character_view_jpg"]  # 5 chars * 3 views
    grid_b   = total_projects_retained * s.avg_episodes_per_project * ASSET_BYTES["storyboard_grid_jpg"]
    tts_b    = total_minutes_retained * ASSET_BYTES["tts_mp3_per_minute"]
    bgm_b    = total_minutes_retained * ASSET_BYTES["bgm_mp3_per_minute"]
    ass_b    = total_projects_retained * s.avg_episodes_per_project * ASSET_BYTES["ass_subtitle"]
    log_b    = total_projects_retained * ASSET_BYTES["log_json_per_job"]
    total_b  = master_b + rough_b + cover_b + scene_b + char_b + grid_b + tts_b + bgm_b + ass_b + log_b
    total_gb = total_b / (1024 ** 3)

    # NAS sizing (only logs + SQLite + small assets, no master mp4)
    nas_gb = (log_b + ass_b + char_b * 0.2) / (1024 ** 3)   # NAS for hot small files
    # Postgres expected row count
    pg_rows_jobs = total_projects_retained
    pg_rows_shots = total_shots_retained
    pg_rows_logs = pg_rows_jobs * 80      # ~80 log rows per job avg

    # Concurrent writers at peak
    concurrent_writers = int(s.daily_active_users * s.concurrent_writers_peak_ratio)
    sqlite_safe = concurrent_writers < SQLITE_LOCK_THRESHOLD_WRITERS

    # veFaaS instances needed for steady-state
    # use throughput_model assumption: 1 worker = 0.36 shots/min sustained
    # → 1 instance = 3 workers = 1.08 shots/min
    daily_seconds = 86_400
    shots_per_second_needed = daily_shots / daily_seconds * 4  # 4x for peak burst
    workers_needed = shots_per_second_needed / (0.36 / 60)     # convert
    vefaas_instances = max(1, int(workers_needed / WORKERS_PER_VEFAAS_INSTANCE + 0.999))

    return {
        "scenario": asdict(s),
        "derived": {
            "daily_projects": daily_projects,
            "daily_episodes": daily_episodes,
            "daily_minutes": daily_minutes,
            "daily_shots": daily_shots,
            "concurrent_writers_peak": concurrent_writers,
        },
        "storage": {
            "tos_total_gb": round(total_gb, 1),
            "tos_breakdown_gb": {
                "master_mp4":     round(master_b / (1024**3), 1),
                "rough_cut":      round(rough_b / (1024**3), 1),
                "cover":          round(cover_b / (1024**3), 2),
                "scene_lib":      round(scene_b / (1024**3), 2),
                "char_views":     round(char_b / (1024**3), 2),
                "storyboard":     round(grid_b / (1024**3), 2),
                "tts":            round(tts_b / (1024**3), 1),
                "bgm":            round(bgm_b / (1024**3), 1),
                "subtitles":      round(ass_b / (1024**3), 3),
                "logs":           round(log_b / (1024**3), 3),
            },
            "nas_total_gb": round(nas_gb, 2),
        },
        "compute": {
            "workers_needed": int(workers_needed + 0.999),
            "vefaas_instances": vefaas_instances,
            "vefaas_total_ram_gb": vefaas_instances * VEFAAS_INSTANCE_RAM_GB,
        },
        "database": {
            "use_sqlite_safe": sqlite_safe,
            "postgres_row_estimates": {
                "xyq_jobs": int(pg_rows_jobs),
                "xyq_shots": int(pg_rows_shots),
                "xyq_job_logs": int(pg_rows_logs),
            },
            "recommendation":
                "SQLite" if sqlite_safe else "Postgres ≥ 14 (managed: 火山 RDS / Neon / Supabase)",
        },
    }


def build_report() -> dict:
    return {
        "model": "capacity_model",
        "version": "v10.0",
        "constants": {
            "sqlite_lock_threshold_writers": SQLITE_LOCK_THRESHOLD_WRITERS,
            "workers_per_vefaas_instance": WORKERS_PER_VEFAAS_INSTANCE,
            "vefaas_instance_ram_gb": VEFAAS_INSTANCE_RAM_GB,
        },
        "asset_bytes": ASSET_BYTES,
        "scenarios": [derive(s) for s in scenarios()],
    }


def render_markdown(report: dict) -> str:
    parts = [
        "# 容量模型 (capacity_model)",
        "",
        "> 给定 DAU + 保留期 → veFaaS 实例 / TOS GB / NAS / SQLite 是否需迁 Postgres",
        "",
        "## 1. 关键拐点常量",
        "",
        render_table(
            ["常量", "值"],
            [[k, v] for k, v in report["constants"].items()],
        ),
        "",
        "## 2. 四档容量场景",
        "",
        render_table(
            ["场景", "DAU", "日项目数", "日分钟数", "并发写", "TOS GB", "NAS GB", "veFaaS 实例", "DB 推荐"],
            [
                [
                    s["scenario"]["name"],
                    s["scenario"]["daily_active_users"],
                    int(s["derived"]["daily_projects"]),
                    int(s["derived"]["daily_minutes"]),
                    s["derived"]["concurrent_writers_peak"],
                    s["storage"]["tos_total_gb"],
                    s["storage"]["nas_total_gb"],
                    s["compute"]["vefaas_instances"],
                    s["database"]["recommendation"],
                ]
                for s in report["scenarios"]
            ],
        ),
        "",
        "## 3. v10_launch 详细 TOS 拆分",
        "",
        render_table(
            ["类别", "GB"],
            [[k, v] for k, v in report["scenarios"][1]["storage"]["tos_breakdown_gb"].items()],
        ),
        "",
        "## 4. 复现",
        "",
        "```bash",
        "python -m tools.data_models.capacity_model",
        "```",
    ]
    return "\n".join(parts)


def main() -> dict:
    parse_cli_out()
    report = build_report()
    write_json("capacity_model", report)
    write_markdown("capacity_model", render_markdown(report))
    launch = report["scenarios"][1]
    print(f"launch: tos={launch['storage']['tos_total_gb']:.0f}GB, "
          f"vefaas={launch['compute']['vefaas_instances']}, "
          f"db={launch['database']['recommendation']}")
    return report


if __name__ == "__main__":
    main()
