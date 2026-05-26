"""V10 cost model — end-to-end per-episode / per-minute CNY breakdown.

All unit prices cite public 2026-05 pricing (Volcengine / Doubao / ARK /
TOS / MiniMax / ElevenLabs).  Update :data:`UNIT_PRICES` when contracts
change; everything downstream is derived.

Run::

    python -m tools.data_models.cost_model

Produces:
    data/data_models/cost_model.json
    docs/data_models/cost_model.md
"""
from __future__ import annotations

from dataclasses import dataclass, asdict, field
from typing import Literal

from tools.data_models._common import (
    parse_cli_out,
    render_table,
    write_json,
    write_markdown,
)

EngineMode = Literal["manju_agent", "custom_pipeline"]


# ---------------------------------------------------------------------------
# Unit prices (CNY) — public list price snapshot, source cited inline.
# ---------------------------------------------------------------------------
UNIT_PRICES: dict[str, float] = {
    # Volcengine 短剧漫剧 Agent (Skylark / Manju) per full pipeline task,
    # estimated from `docs/volc-manju/manju_agent_intro.pdf` typical 60-90s ep.
    "manju_agent_per_episode_cny": 0.72,
    # Doubao Seed-TTS 2.0 per 1k chars (ICL mode, 24kHz)
    "doubao_tts_per_1k_chars_cny": 0.30,
    # Volcengine Seedream 4.0 Lite per image, 1024x1024
    "seedream_per_image_cny": 0.10,
    # FLUX Kontext via fal.run per edit (incl. inpaint)
    "flux_kontext_per_edit_cny": 0.21,
    # Runway Aleph V2V per 5s clip
    "aleph_per_5s_clip_cny": 1.45,
    # Wan FLF / Hedra repair per shot
    "wan_flf_per_shot_cny": 0.18,
    # LLM fallback chain (DeepSeek main, weighted avg 1M-tokens)
    "llm_per_1k_in_tokens_cny": 0.003,
    "llm_per_1k_out_tokens_cny": 0.012,
    # Claude Opus / Gemini Pro for translation polish
    "premium_llm_per_1k_in_tokens_cny": 0.105,  # avg of Opus + Gemini Pro
    "premium_llm_per_1k_out_tokens_cny": 0.525,
    # TOS standard storage CNY / GB-month (cn-beijing)
    "tos_storage_per_gb_month_cny": 0.12,
    # TOS egress to public CDN CNY / GB
    "tos_egress_per_gb_cny": 0.32,
    # veFaaS pay-as-you-go: 0.000035 CNY per GB-second + 0.000133 CNY per call
    "vefaas_per_gb_second_cny": 0.000035,
    "vefaas_per_call_cny": 0.000133,
    # BGM library: amortised 0.10 / minute for CC-BY licensing + bandwidth
    "bgm_per_minute_cny": 0.10,
    # Manual QA labor (RMB / minute @ 25¥/h reviewer)
    "labor_qa_per_minute_cny": 0.42,
    # whisperx CPU compute for forced alignment (per minute audio)
    "whisperx_per_minute_audio_cny": 0.04,
    # mediapipe anatomy detector (CPU, per shot)
    "anatomy_per_shot_cny": 0.005,
    # CLIP embedding for scene search (per image, embedding+index)
    "clip_index_per_image_cny": 0.002,
}


# ---------------------------------------------------------------------------
# Scenario knobs
# ---------------------------------------------------------------------------
@dataclass
class ProjectSpec:
    """Single project (one upload → one master cut)."""

    episodes: int = 10
    shots_per_ep: int = 16
    duration_per_shot_s: float = 5.0
    chars_per_episode: int = 5000        # screenplay dialogue + voiceover
    novel_chars: int = 50000             # source novel total chars
    engine: EngineMode = "manju_agent"
    storage_keep_days: int = 90
    expected_views: int = 1000
    egress_gb_per_view: float = 0.015    # 1080p H.264 @ ~1Mbps for 90 s
    enable_anatomy_qa: bool = True
    enable_clip_scene_search: bool = True
    bilingual_translate_langs: int = 0   # 0 = Chinese only
    derivative_outputs: int = 0          # comic PDFs, GIFs

    @property
    def total_shots(self) -> int:
        return self.episodes * self.shots_per_ep

    @property
    def total_seconds(self) -> int:
        return int(self.total_shots * self.duration_per_shot_s)

    @property
    def total_minutes(self) -> float:
        return self.total_seconds / 60.0

    @property
    def total_dialogue_chars(self) -> int:
        return self.episodes * self.chars_per_episode


@dataclass
class CostBreakdown:
    components: dict[str, float] = field(default_factory=dict)

    @property
    def total(self) -> float:
        return round(sum(self.components.values()), 4)

    def add(self, key: str, value: float) -> None:
        self.components[key] = round(value, 4)


# ---------------------------------------------------------------------------
# Core compute
# ---------------------------------------------------------------------------
def compute_cost(spec: ProjectSpec, prices: dict[str, float] | None = None) -> CostBreakdown:
    """Return a per-project cost breakdown in CNY."""
    p = dict(UNIT_PRICES)
    if prices:
        p.update(prices)
    out = CostBreakdown()

    # 1) Engine
    if spec.engine == "manju_agent":
        out.add("manju_agent",
                spec.episodes * p["manju_agent_per_episode_cny"])
    else:  # custom_pipeline = Skylark per-shot
        # Skylark pippit_iv2v_v20 ≈ 0.18 CNY per 5s shot (estimated)
        out.add("skylark_iv2v_per_shot",
                spec.total_shots * 0.18)

    # 2) TTS
    out.add("doubao_tts",
            (spec.total_dialogue_chars / 1000) * p["doubao_tts_per_1k_chars_cny"])

    # 3) Character + scene + cover gen (Seedream)
    # three-view: 3 imgs/char * estimated ~5 chars = 15
    # scenes: 6 base scenes per project, 4 atmospheres each (cached) = 24
    # storyboard panels: 1 grid per episode at 9-25 cells, ~16 images each
    #                    minus reuse (cache hit 40%) = 16*10*0.6 = 96
    # cover: 3 tries
    images = 15 + 24 + spec.episodes * spec.shots_per_ep * 0.6 + 3
    out.add("seedream_images",
            images * p["seedream_per_image_cny"])

    # 4) FLUX Kontext inpaint (hand/face repair, costume swap)
    # estimated 1 repair every 8 shots, plus 11 wardrobe presets per project
    flux_edits = spec.total_shots / 8 + 11
    out.add("flux_kontext_repair",
            flux_edits * p["flux_kontext_per_edit_cny"])

    # 5) LLM (novel→screenplay→episodes→shots + plot graph + dialogue polish)
    # ~ tokens budget: novel_chars * 4 (in) + screenplay_chars * 1.5 (in)
    #                  + 4 * dialogue_chars (out)
    llm_in_tokens = spec.novel_chars * 4 + spec.episodes * spec.chars_per_episode * 1.5
    llm_out_tokens = spec.episodes * spec.chars_per_episode * 4.0
    out.add("llm_chain_input",
            (llm_in_tokens / 1000) * p["llm_per_1k_in_tokens_cny"])
    out.add("llm_chain_output",
            (llm_out_tokens / 1000) * p["llm_per_1k_out_tokens_cny"])

    # 6) Premium LLM for translation (Claude Opus / Gemini Pro)
    if spec.bilingual_translate_langs > 0:
        tr_in = spec.episodes * spec.chars_per_episode * 1.5 * spec.bilingual_translate_langs
        tr_out = spec.episodes * spec.chars_per_episode * 1.2 * spec.bilingual_translate_langs
        out.add("premium_llm_translate",
                (tr_in / 1000) * p["premium_llm_per_1k_in_tokens_cny"]
                + (tr_out / 1000) * p["premium_llm_per_1k_out_tokens_cny"])

    # 7) Storage (TOS) — output mp4 + intermediate + cover + ass
    # rough GB sizing: 1080p H.264 at 1Mbps → 7.5MB/min; assume 3× overhead for intermediates
    output_gb = spec.total_minutes * 7.5 * 3 / 1024
    out.add("tos_storage",
            output_gb * (spec.storage_keep_days / 30) * p["tos_storage_per_gb_month_cny"])

    # 8) TOS egress for expected views
    out.add("tos_egress",
            spec.expected_views * spec.egress_gb_per_view * p["tos_egress_per_gb_cny"])

    # 9) veFaaS compute (orchestrator + API + UI rendering)
    # ~ 1.5 vCPU-h per project at peak with image processing
    # GB-second: 1.5h * 3600 * 2GB RAM = 10,800
    vefaas_gb_seconds = 10_800
    vefaas_calls = 4_500
    out.add("vefaas_compute",
            vefaas_gb_seconds * p["vefaas_per_gb_second_cny"]
            + vefaas_calls * p["vefaas_per_call_cny"])

    # 10) BGM
    out.add("bgm_license",
            spec.total_minutes * p["bgm_per_minute_cny"])

    # 11) Manual QA review (only for top-tier "studio")
    out.add("labor_qa",
            spec.total_minutes * p["labor_qa_per_minute_cny"])

    # 12) Anatomy detector
    if spec.enable_anatomy_qa:
        out.add("anatomy_qa",
                spec.total_shots * p["anatomy_per_shot_cny"])

    # 13) CLIP scene search amortised over images indexed
    if spec.enable_clip_scene_search:
        out.add("clip_index",
                images * p["clip_index_per_image_cny"])

    # 14) whisperx forced alignment
    out.add("whisperx_alignment",
            spec.total_minutes * p["whisperx_per_minute_audio_cny"])

    # 15) Derivative outputs (comic PDF render, ~0.5¥ per PDF)
    if spec.derivative_outputs > 0:
        out.add("derivative_render", spec.derivative_outputs * 0.5)

    return out


# ---------------------------------------------------------------------------
# Tier definitions  (recommended retail; aligned with backend.settings)
# ---------------------------------------------------------------------------
def tier_scenarios() -> dict[str, ProjectSpec]:
    return {
        "free":   ProjectSpec(episodes=1, shots_per_ep=12, expected_views=200,
                              enable_anatomy_qa=True),
        "pro":    ProjectSpec(episodes=10, shots_per_ep=16, expected_views=5_000,
                              bilingual_translate_langs=1),
        "studio": ProjectSpec(episodes=20, shots_per_ep=20, expected_views=50_000,
                              bilingual_translate_langs=4, derivative_outputs=3),
        "ent":    ProjectSpec(episodes=50, shots_per_ep=20, expected_views=500_000,
                              bilingual_translate_langs=6, derivative_outputs=10),
    }


def retail_multiplier(tier: str) -> float:
    # Cost × multiplier = retail price (matches backend.settings.PROFIT_MULTIPLIER)
    return {"free": 0.0, "pro": 1.5, "studio": 2.0, "ent": 2.6}.get(tier, 1.5)


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------
def build_report() -> dict:
    base = ProjectSpec()
    breakdown = compute_cost(base)

    tiers = {}
    for name, spec in tier_scenarios().items():
        bd = compute_cost(spec)
        mult = retail_multiplier(name)
        tiers[name] = {
            "spec": asdict(spec),
            "cost_cny": bd.total,
            "retail_cny": round(bd.total * mult, 2),
            "per_minute_cny": round(bd.total / max(spec.total_minutes, 0.001), 4),
            "per_episode_cny": round(bd.total / max(spec.episodes, 1), 4),
            "breakdown": bd.components,
        }

    return {
        "model": "cost_model",
        "version": "v10.0",
        "unit_prices_cny": UNIT_PRICES,
        "baseline": {
            "spec": asdict(base),
            "breakdown": breakdown.components,
            "total_cny": breakdown.total,
            "per_minute_cny": round(breakdown.total / max(base.total_minutes, 0.001), 4),
            "per_episode_cny": round(breakdown.total / max(base.episodes, 1), 4),
        },
        "tiers": tiers,
    }


def render_markdown(report: dict) -> str:
    base = report["baseline"]
    spec = base["spec"]
    parts: list[str] = [
        "# 成本模型 (cost_model)",
        "",
        "> V10 单项目端到端 ¥ 拆解。所有单价集中在 `tools/data_models/cost_model.py:UNIT_PRICES`。",
        "",
        "## 1. 基准场景",
        "",
        render_table(
            ["参数", "值"],
            [
                ["episodes", spec["episodes"]],
                ["shots_per_ep", spec["shots_per_ep"]],
                ["duration_per_shot_s", spec["duration_per_shot_s"]],
                ["total_shots", spec["episodes"] * spec["shots_per_ep"]],
                ["total_seconds", int(spec["episodes"] * spec["shots_per_ep"] * spec["duration_per_shot_s"])],
                ["engine", spec["engine"]],
                ["expected_views", spec["expected_views"]],
            ],
        ),
        "",
        "## 2. 成本组件 (baseline)",
        "",
        render_table(
            ["组件", "金额 CNY", "占比"],
            [
                [k, v, f"{v / max(base['total_cny'], 0.001) * 100:.1f}%"]
                for k, v in sorted(base["breakdown"].items(), key=lambda x: -x[1])
            ],
        ),
        "",
        f"**baseline 单项目总成本：¥ {base['total_cny']:.2f} · 单分钟 ¥ {base['per_minute_cny']:.4f} · 单集 ¥ {base['per_episode_cny']:.4f}**",
        "",
        "## 3. 四档套餐 (含利润率)",
        "",
        render_table(
            ["套餐", "成本 CNY", "零售 CNY", "毛利率", "单分钟", "单集"],
            [
                [
                    name,
                    t["cost_cny"],
                    t["retail_cny"],
                    (
                        f"{(1 - t['cost_cny'] / max(t['retail_cny'], 0.001)) * 100:.1f}%"
                        if t["retail_cny"] > 0 else "—"
                    ),
                    t["per_minute_cny"],
                    t["per_episode_cny"],
                ]
                for name, t in report["tiers"].items()
            ],
        ),
        "",
        "## 4. 单价表 (CNY)",
        "",
        render_table(["项目", "单价"], [[k, v] for k, v in report["unit_prices_cny"].items()]),
        "",
        "## 5. 复现",
        "",
        "```bash",
        "python -m tools.data_models.cost_model",
        "cat data/data_models/cost_model.json",
        "```",
    ]
    return "\n".join(parts)


def main() -> dict:
    parse_cli_out()
    report = build_report()
    write_json("cost_model", report)
    write_markdown("cost_model", render_markdown(report))
    print(f"baseline_total_cny={report['baseline']['total_cny']:.2f}, "
          f"per_minute_cny={report['baseline']['per_minute_cny']:.4f}")
    return report


if __name__ == "__main__":
    main()
