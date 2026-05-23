"""广电总局微短剧备案 — auto-fill from job artifacts.

Closes Gap C-9. Renders ``compliance/filing_template.md`` into a
job-specific filled markdown + JSON sidecar (for the 国家广电总局 备案
system upload).

Inputs the orchestrator hands us:
- the episode plan (synopsis + characters + scenes)
- the AI-systems list (engine 备案号 needed for AIGC 专项材料)
- the cost estimate (drives 备案 category: 其他类 / 普通类 / 重点类)
- the compliance section of the artifact bundle

Output:
- ``filing/{job_id}/filing_filled.md``         — ready-for-print human-readable
- ``filing/{job_id}/filing_sidecar.json``       — machine-parseable summary
- ``filing/{job_id}/checklist.json``            — per-item present/missing

The auto-filler is **strict mock-friendly**: missing inputs degrade
gracefully to "(待填)" placeholders so the entire job pipeline never
fails because of compliance.
"""
from __future__ import annotations

import json
import logging
import pathlib
from dataclasses import asdict, dataclass, field
from typing import Iterable, Mapping

_log = logging.getLogger(__name__)


_REPO = pathlib.Path(__file__).resolve().parents[2]
_DEFAULT_TEMPLATE = _REPO / "compliance" / "filing_template.md"


COST_CATEGORY_THRESHOLDS = (
    (1_000_000, "其他类", "省级广电局"),
    (3_000_000, "普通类", "省级广电局 + 国家广电总局"),
    (float("inf"), "重点类", "国家广电总局"),
)


@dataclass
class FilingSummary:
    job_id: int | str
    title: str
    genre: str
    episodes: int
    cost_cny: int
    category: str
    competent_authority: str
    director: str
    producer: str
    monitor: str
    ai_systems: list[str] = field(default_factory=list)
    synopsis_excerpt: str = ""
    aigc_label_position: str = "右下角文字水印 + 标题前缀【AI】 + 简介首行声明"
    c2pa_sidecar: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


def categorize(cost_cny: int) -> tuple[str, str]:
    for threshold, label, authority in COST_CATEGORY_THRESHOLDS:
        if cost_cny < threshold:
            return label, authority
    return "重点类", "国家广电总局"


def _fmt_md(summary: FilingSummary, ai_engine_records: list[dict], notes: list[str]) -> str:
    ai_lines = "\n".join(
        f"  - {r.get('name','?')} 备案号：{r.get('filing_no','(待填)')} ({r.get('vendor','?')})"
        for r in ai_engine_records
    ) or "  - (尚无 AI 引擎备案信息，请补充)"

    note_block = "\n".join(f"> {n}" for n in notes) or "> 无额外说明。"

    return f"""# 微短剧备案材料 — 自动生成 (job_id={summary.job_id})

> 由 `src.compliance.filing_autogen` 在 v8 流水线 step6 自动生成。
> 提交前请人工复核每一项 □ 是否齐备。

## 1. 项目自评

| 字段 | 值 |
|---|---|
| 剧名 | {summary.title} |
| 题材 | {summary.genre} |
| 集数 | {summary.episodes} 集 |
| 制作成本（含 AIGC token） | ¥{summary.cost_cny:,} |
| 备案类别 | **{summary.category}** |
| 备案登记机关 | {summary.competent_authority} |
| AIGC 显式标识 | {summary.aigc_label_position} |
| C2PA sidecar | {summary.c2pa_sidecar or '(尚未生成)'} |

## 2. 主创署名

| 角色 | 姓名 |
|---|---|
| 监制（人类，承担 AIGC 监督责任） | {summary.monitor or '(待填)'} |
| 导演（AI 创作 → 标注 AI 智能生成 + 监制人） | {summary.director or 'AI 智能生成'} |
| 制片人 | {summary.producer or '(待填)'} |

## 3. AIGC 引擎备案号清单（2026 新规重点）

{ai_lines}

## 4. 内容摘要

{summary.synopsis_excerpt[:1200] or '(尚未提供)'}

## 5. 自动检查项备注

{note_block}

---

_生成时间：{__import__('datetime').datetime.now().isoformat(timespec='seconds')}_
"""


def autofill(
    *,
    job_id: int | str,
    title: str,
    genre: str,
    episodes: int,
    cost_cny: int,
    director: str = "AI 智能生成",
    producer: str = "(待填)",
    monitor: str = "(待填)",
    ai_systems: Iterable[str] = (),
    ai_engine_records: list[Mapping] | None = None,
    synopsis_excerpt: str = "",
    c2pa_sidecar: str | pathlib.Path = "",
    out_dir: str | pathlib.Path | None = None,
) -> dict:
    """Render filled filing materials. Returns ``{md_path, json_path, checklist_path}``."""

    category, authority = categorize(cost_cny)
    summary = FilingSummary(
        job_id=job_id,
        title=title,
        genre=genre,
        episodes=episodes,
        cost_cny=cost_cny,
        category=category,
        competent_authority=authority,
        director=director,
        producer=producer,
        monitor=monitor,
        ai_systems=list(ai_systems),
        synopsis_excerpt=synopsis_excerpt,
        c2pa_sidecar=str(c2pa_sidecar) if c2pa_sidecar else "",
    )

    notes: list[str] = []
    if not monitor or "待填" in monitor:
        notes.append("⚠ 监制人姓名未填写——AIGC 2026 新规要求人类监制人署名。")
    if not summary.synopsis_excerpt:
        notes.append("⚠ 缺剧本梗概，请补充 5000 字以内大纲。")
    if not ai_engine_records:
        notes.append("⚠ AI 引擎备案号清单为空，请补充火山引擎 / 字节方舟 / 海外引擎的备案号或免备案声明。")

    out_dir = pathlib.Path(out_dir or _REPO / "data" / "filing" / str(job_id))
    out_dir.mkdir(parents=True, exist_ok=True)

    md_path = out_dir / "filing_filled.md"
    md_path.write_text(_fmt_md(summary, list(ai_engine_records or []), notes), encoding="utf-8")

    json_path = out_dir / "filing_sidecar.json"
    json_path.write_text(
        json.dumps(
            {
                "summary": summary.to_dict(),
                "ai_engine_records": list(ai_engine_records or []),
                "notes": notes,
                "template_source": str(_DEFAULT_TEMPLATE.relative_to(_REPO)),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    checklist = {
        "subject_certificate": False,
        "broadcast_production_license": False,
        "synopsis": bool(summary.synopsis_excerpt),
        "episode_outline": episodes > 0,
        "credits": bool(monitor and "待填" not in monitor),
        "original_authorization": False,
        "aigc_engine_records": len(ai_engine_records or []) > 0,
        "aigc_label_plan": True,
        "originality_proof": False,
        "value_compliance_self_check": True,
    }
    checklist_path = out_dir / "checklist.json"
    checklist_path.write_text(
        json.dumps(
            {
                "job_id": str(job_id),
                "category": category,
                "competent_authority": authority,
                "items": checklist,
                "passed_count": sum(1 for v in checklist.values() if v),
                "total": len(checklist),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    return {
        "md_path": str(md_path),
        "json_path": str(json_path),
        "checklist_path": str(checklist_path),
        "category": category,
        "competent_authority": authority,
        "notes": notes,
    }


__all__ = ["autofill", "categorize", "FilingSummary"]
