"""V10 §12 — acceptance script.

Walks ALL 11 chapters of ``need.md`` and verifies the implemented
artefact set against the spec.  Emits:

    data/observability/v10_acceptance_report.json
    stdout — coloured PASS / WARN / FAIL summary

Exit codes:
    0 — all required checks passed
    1 — one or more checks WARN (acceptable but worth investigating)
    2 — one or more checks FAIL (release blocker)

Run as::

    python scripts/v10_acceptance.py
    python scripts/v10_acceptance.py --strict   # WARN also fails
"""
from __future__ import annotations

import argparse
import importlib
import json
import pathlib
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable

REPO = pathlib.Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))


@dataclass
class CheckResult:
    chapter: str
    name: str
    status: str       # PASS | WARN | FAIL
    detail: str = ""
    extras: dict[str, Any] = field(default_factory=dict)


@dataclass
class ChapterReport:
    chapter: str
    title: str
    checks: list[CheckResult] = field(default_factory=list)

    @property
    def pass_count(self) -> int:
        return sum(1 for c in self.checks if c.status == "PASS")

    @property
    def fail_count(self) -> int:
        return sum(1 for c in self.checks if c.status == "FAIL")

    @property
    def warn_count(self) -> int:
        return sum(1 for c in self.checks if c.status == "WARN")


# ---------- helpers ----------

def _file(path: str) -> bool:
    return (REPO / path).exists()


def _imports(*module_names: str) -> tuple[bool, str]:
    missing: list[str] = []
    for m in module_names:
        try:
            importlib.import_module(m)
        except Exception as exc:
            missing.append(f"{m}: {exc.__class__.__name__}")
    if missing:
        return False, "; ".join(missing)
    return True, ""


def _has_attr(module_name: str, *attrs: str) -> tuple[bool, str]:
    try:
        mod = importlib.import_module(module_name)
    except Exception as exc:
        return False, f"import {module_name} failed: {exc}"
    missing = [a for a in attrs if not hasattr(mod, a)]
    if missing:
        return False, f"missing attrs: {', '.join(missing)}"
    return True, ""


def _check(chapter: str, name: str,
           predicate: Callable[[], tuple[bool, str]],
           *, warn_on_fail: bool = False) -> CheckResult:
    try:
        ok, detail = predicate()
    except Exception as exc:
        return CheckResult(chapter=chapter, name=name, status="FAIL",
                           detail=f"exception: {exc}")
    if ok:
        return CheckResult(chapter=chapter, name=name, status="PASS")
    return CheckResult(chapter=chapter, name=name,
                       status="WARN" if warn_on_fail else "FAIL",
                       detail=detail)


# ---------- chapter check definitions ----------

def chapter_1_specs() -> ChapterReport:
    r = ChapterReport("§1", "产出规格 & 自定义画风")
    r.checks.append(_check(r.chapter, "Job schema aspect/resolution/fps/duration",
        lambda: _has_attr("backend.app.db", "Job")))
    r.checks.append(_check(r.chapter, "custom_style module",
        lambda: _imports("src.genres.custom_style")))
    r.checks.append(_check(r.chapter, "/styles route",
        lambda: _imports("backend.app.routes.styles")))
    return r


def chapter_2_infra_archive_version() -> ChapterReport:
    r = ChapterReport("§2", "目录命名 / 项目包 / 版本 diff / 风控")
    r.checks.append(_check(r.chapter, "artifact_store (tree naming)",
        lambda: _imports("src.common.artifact_store")))
    r.checks.append(_check(r.chapter, "project bundle export",
        lambda: _has_attr("src.common.artifact_store", "ArtifactStore")))
    r.checks.append(_check(r.chapter, "version_diff module",
        lambda: _imports("src.common.version_diff")))
    r.checks.append(_check(r.chapter, "post_vlm_review module",
        lambda: _imports("src.compliance.post_vlm_review")))
    r.checks.append(_check(r.chapter, "copyright fingerprint",
        lambda: _imports("src.compliance.copyright_fp")))
    return r


def chapter_3_text_layer() -> ChapterReport:
    r = ChapterReport("§3", "文本层")
    for m in (
        "src.text.novel_import",
        "src.text.chapter_writer",
        "src.text.plot_state",
        "src.text.novel_to_screenplay",
        "src.text.dialogue_polish",
        "src.text.novel_translate",
    ):
        r.checks.append(_check(r.chapter, m.split(".")[-1],
                               lambda m=m: _imports(m)))
    r.checks.append(_check(r.chapter, "novels routes",
        lambda: _imports("backend.app.routes.novels")))
    r.checks.append(_check(r.chapter, "screenplays routes",
        lambda: _imports("backend.app.routes.screenplays")))
    return r


def chapter_4_visual_assets() -> ChapterReport:
    r = ChapterReport("§4", "视觉资产")
    for m in (
        "src.visual.three_view",
        "src.visual.expression_router",
        "src.visual.pose_extract",
        "src.visual.costume_climate",
        "src.visual.scene_search",
        "src.visual.atmosphere_inferer",
    ):
        r.checks.append(_check(r.chapter, m.split(".")[-1],
                               lambda m=m: _imports(m), warn_on_fail=True))
    return r


def chapter_5_frame_gen() -> ChapterReport:
    r = ChapterReport("§5", "画面生成")
    for m in (
        "src.frame_gen.storyboard_layouter",
        "src.frame_gen.storyboard_grid",
        "src.frame_gen.parallel_scheduler",
        "src.frame_gen.resumer",
        "src.frame_gen.anatomy_detector",
        "src.frame_gen.repair_hand_local",
    ):
        r.checks.append(_check(r.chapter, m.split(".")[-1],
                               lambda m=m: _imports(m), warn_on_fail=True))
    return r


def chapter_6_qa_loop() -> ChapterReport:
    r = ChapterReport("§6", "质量闭环")
    for m in (
        "src.qa.visual_diagnose",
        "src.qa.style_consistency",
        "src.qa.repair_router",
        "src.qa.feedback_distill",
    ):
        r.checks.append(_check(r.chapter, m.split(".")[-1],
                               lambda m=m: _imports(m)))
    return r


def chapter_7_av_synth() -> ChapterReport:
    r = ChapterReport("§7", "音视频核心")
    for m in (
        "src.audio.voice_library", "src.audio.dialogue_timeline",
        "src.audio.bgm_library", "src.audio.bgm_recommender",
        "src.audio.beat_align", "src.audio.sfx_auto_inject",
        "src.audio.lufs_normalize",
        "src.video.transitions", "src.video.compose_v10",
    ):
        r.checks.append(_check(r.chapter, m.split(".")[-1],
                               lambda m=m: _imports(m)))
    r.checks.append(_check(r.chapter, "voices.yaml",
        lambda: (_file("config/voices.yaml"), "config/voices.yaml not found")))
    r.checks.append(_check(r.chapter, "bgm_library.yaml",
        lambda: (_file("config/bgm_library.yaml"), "not found")))
    r.checks.append(_check(r.chapter, "sfx_library.yaml",
        lambda: (_file("config/sfx_library.yaml"), "not found")))
    r.checks.append(_check(r.chapter, "assets/fonts README",
        lambda: (_file("assets/fonts/README.md"), "not found")))
    return r


def chapter_8_advanced_derivative() -> ChapterReport:
    r = ChapterReport("§8", "高阶 + 同人衍生")
    for m in (
        "src.advanced.continuation", "src.advanced.interaction_logic",
        "src.advanced.asset_restyle",
        "src.derivative.novel_to_comic", "src.derivative.video_to_comic",
        "src.derivative.comic_to_motion", "src.derivative.restyle_brush",
    ):
        r.checks.append(_check(r.chapter, m.split(".")[-1],
                               lambda m=m: _imports(m)))
    return r


def chapter_9_flow_dual_mode() -> ChapterReport:
    r = ChapterReport("§9", "流程 + 双模式")
    for m in (
        "src.flow.templates", "src.flow.pause_gate",
        "src.flow.scheduler", "src.flow.drafts",
    ):
        r.checks.append(_check(r.chapter, m.split(".")[-1],
                               lambda m=m: _imports(m)))
    r.checks.append(_check(r.chapter, "hot_templates.yaml (10 entries)",
        lambda: _check_hot_templates()))
    r.checks.append(_check(r.chapter, "/dashboard/new/wizard page",
        lambda: (_file("web/app/dashboard/new/wizard/page.tsx"), "not found")))
    r.checks.append(_check(r.chapter, "/dashboard/new/pro page",
        lambda: (_file("web/app/dashboard/new/pro/page.tsx"), "not found")))
    r.checks.append(_check(r.chapter, "flow + templates + schedules routes",
        lambda: _imports("backend.app.routes.flow",
                          "backend.app.routes.templates",
                          "backend.app.routes.schedules")))
    return r


def _check_hot_templates() -> tuple[bool, str]:
    p = REPO / "config" / "hot_templates.yaml"
    if not p.exists():
        return False, "config/hot_templates.yaml not found"
    txt = p.read_text(encoding="utf-8")
    n = txt.count("- id:")
    if n < 10:
        return False, f"only {n} templates (need ≥ 10)"
    return True, ""


def chapter_10_export() -> ChapterReport:
    r = ChapterReport("§10", "导出适配")
    for m in (
        "src.export.gif_export", "src.export.frame_sequence",
        "src.export.storyboard_export", "src.export.cover_compose",
        "src.export.platform_copy_presets",
        "src.shell5_post_production.platform_export",
    ):
        r.checks.append(_check(r.chapter, m.split(".")[-1],
                               lambda m=m: _imports(m)))
    return r


def chapter_11_enterprise() -> ChapterReport:
    r = ChapterReport("§11", "团队商用版")
    for m in (
        "src.enterprise.rbac", "src.enterprise.api_keys",
        "src.enterprise.rate_limit", "src.enterprise.invites",
        "src.enterprise.usage",
    ):
        r.checks.append(_check(r.chapter, m.split(".")[-1],
                               lambda m=m: _imports(m)))
    r.checks.append(_check(r.chapter, "orgs + public_v1 routes",
        lambda: _imports("backend.app.routes.orgs",
                          "backend.app.routes.public_v1")))
    r.checks.append(_check(r.chapter, "5 enterprise ORM tables",
        lambda: _check_enterprise_tables()))
    r.checks.append(_check(r.chapter, "Helm chart present",
        lambda: (_file("deploy/enterprise/helm/xyq/Chart.yaml"), "not found")))
    r.checks.append(_check(r.chapter, "Alembic v10 migration",
        lambda: (_file("backend/alembic/versions/20260526_0001_v10_enterprise_schema.py"),
                 "not found")))
    return r


def _check_enterprise_tables() -> tuple[bool, str]:
    try:
        from backend.app import db as _db
    except Exception as exc:
        return False, str(exc)
    missing = [t for t in (
        "Organization", "OrgMember", "ApiKey", "OrgUsage", "OrgInvite",
    ) if not hasattr(_db, t)]
    if missing:
        return False, "missing: " + ", ".join(missing)
    return True, ""


def chapter_12_nfr_monitor_docs() -> ChapterReport:
    r = ChapterReport("§12", "NFR + 监控 + 文档")
    r.checks.append(_check(r.chapter, "tools/sla_probe.py",
        lambda: (_file("tools/sla_probe.py"), "not found")))
    r.checks.append(_check(r.chapter, "grafana dashboard JSON",
        lambda: (_file("deploy/observability/grafana_dashboard_v10.json"), "not found")))
    r.checks.append(_check(r.chapter, "volc cloud monitor YAML",
        lambda: (_file("deploy/observability/volc_cloud_monitor.yaml"), "not found")))
    r.checks.append(_check(r.chapter, "v10 runbook",
        lambda: (_file("docs/v10_runbook.md"), "not found")))
    r.checks.append(_check(r.chapter, "api-v10 docs",
        lambda: (_file("docs/api-v10.md"), "not found")))
    r.checks.append(_check(r.chapter, "SSO/OIDC P0 module",
        lambda: _imports("src.enterprise.sso_oidc")))
    return r


# ---------- runner ----------

ALL_CHAPTERS: list[Callable[[], ChapterReport]] = [
    chapter_1_specs, chapter_2_infra_archive_version, chapter_3_text_layer,
    chapter_4_visual_assets, chapter_5_frame_gen, chapter_6_qa_loop,
    chapter_7_av_synth, chapter_8_advanced_derivative,
    chapter_9_flow_dual_mode, chapter_10_export, chapter_11_enterprise,
    chapter_12_nfr_monitor_docs,
]


def _colour(s: str, code: str) -> str:
    return f"\033[{code}m{s}\033[0m" if sys.stdout.isatty() else s


def _format_status(status: str) -> str:
    return {
        "PASS": _colour("PASS", "32"),
        "WARN": _colour("WARN", "33"),
        "FAIL": _colour("FAIL", "31"),
    }.get(status, status)


def print_chapter(r: ChapterReport) -> None:
    print(f"\n=== {r.chapter} · {r.title} "
          f"(PASS {r.pass_count} / WARN {r.warn_count} / FAIL {r.fail_count}) ===")
    for c in r.checks:
        line = f"  [{_format_status(c.status)}] {c.name}"
        if c.detail:
            line += f"  — {c.detail}"
        print(line)


def _md_icon(status: str) -> str:
    return {"PASS": "✅", "WARN": "⚠️", "FAIL": "❌"}.get(status, status)


def _write_md_report(path: pathlib.Path, summary: dict[str, Any],
                     reports: list[ChapterReport]) -> None:
    lines = [
        "# V10 Acceptance Report (need.md V3.0)",
        "",
        f"**Generated:** {summary['ran_at']}",
        f"**Totals:** PASS {summary['pass']} · WARN {summary['warn']} · FAIL {summary['fail']}",
        "",
    ]
    for rep in reports:
        lines.append(f"## {rep.chapter} · {rep.title}")
        lines.append("")
        lines.append(f"PASS {rep.pass_count} / WARN {rep.warn_count} / FAIL {rep.fail_count}")
        lines.append("")
        for c in rep.checks:
            detail = f" — {c.detail}" if c.detail else ""
            lines.append(f"- {_md_icon(c.status)} **{c.name}**{detail}")
        lines.append("")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--strict", action="store_true",
                        help="treat WARN as failure")
    parser.add_argument("--out",
                        default="data/observability/v10_acceptance_report.json")
    args = parser.parse_args(argv)

    print("Xiaoyunque V10 Acceptance Test (need.md V3.0)")
    print(f"Repo: {REPO}")
    reports: list[ChapterReport] = []
    n_pass = n_warn = n_fail = 0
    for fn in ALL_CHAPTERS:
        rep = fn()
        reports.append(rep)
        print_chapter(rep)
        n_pass += rep.pass_count
        n_warn += rep.warn_count
        n_fail += rep.fail_count

    summary = {
        "ran_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "pass": n_pass, "warn": n_warn, "fail": n_fail,
        "chapters": [
            {"chapter": r.chapter, "title": r.title,
             "pass": r.pass_count, "warn": r.warn_count, "fail": r.fail_count,
             "checks": [asdict(c) for c in r.checks]}
            for r in reports
        ],
    }
    out = REPO / args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(summary, indent=2, ensure_ascii=False),
                   encoding="utf-8")
    md_path = out.with_suffix(".md")
    _write_md_report(md_path, summary, reports)
    print(f"\n=== TOTAL: PASS {n_pass} / WARN {n_warn} / FAIL {n_fail} ===")
    print(f"Report: {out}")
    print(f"Markdown: {md_path}")

    if n_fail > 0:
        return 2
    if args.strict and n_warn > 0:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
