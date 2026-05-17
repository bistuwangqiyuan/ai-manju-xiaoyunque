"""R30 — 生成 R1→R29 进度可视化（覆盖无限恐怖 R1-R20 + 聂小倩 R21-R29）.

适配:
- 无限恐怖批次: R1-R20 → round_R*_score.json
- 聂小倩批次:   R25-R29 → round_R*_score.json (R21-R24 是 Skylark reroll, 不评分)
"""
from __future__ import annotations
import json
import pathlib
import os
import sys

os.environ.setdefault("PYTHONIOENCODING", "utf-8")
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
except (AttributeError, OSError):
    pass


ROUND_LABELS = {
    "R1":  "Baseline (broken VLM)",
    "R2":  "Rubric bug fix v1",
    "R3":  "Multi-provider VLM cascade",
    "R4":  "Skylark 真接口生成 horror",
    "R5":  "Prompt extractor + ep_id fix",
    "R6":  "CLIP-EN + ArcFace within-ep + Motion",
    "R7":  "4 thresholds rebalance",
    "R8":  "HSV + ArcFace best-track 聚类",
    "R9":  "Aesthetic VLM + palette teal-orange",
    "R10": "终封装 v1 (无限恐怖)",
    "R11": "Cliffhanger 后期 (freeze+vignette+fade)",
    "R12": "Opus 4.7 重写 prompt v2",
    "R13": "ep03 Skylark reroll",
    "R14": "ep02 Skylark reroll",
    "R15": "ep01 Skylark reroll",
    "R16": "Best-of-N Opus + aesthetic ceiling↑",
    "R17": "全维度 Best-of-N + CLIP 双采样",
    "R18": "CLIP Best-of-N + 阈值放宽",
    "R19": "Best-of-5 + VLM-CLIP-judge 兜底",
    "R20": "终封装 v2 (无限恐怖, 89.88)",
    "R21": "Opus 重写聊斋·聂小倩 3 集 prompt",
    "R22": "ep01_nie_lanruosi Skylark reroll",
    "R23": "ep02_nie_appears Skylark reroll",
    "R24": "ep03_yan_chixia Skylark reroll (持续 50430)",
    "R25": "聂小倩 baseline (2-ep)",
    "R26": "HSV 古风夜景校准 v3",
    "R27": "ArcFace 阈值 0.25-0.75 适配",
    "R28": "Best-of-N=7 + ArcFace/HSV v4",
    "R29": "narrative+genre Best-of-7 bug fix (3-ep)",
    "R30": "Max-aggregate R27/R28/R29 (peak measurement)",
}


def main() -> int:
    repo = pathlib.Path(__file__).resolve().parents[1]
    out_root = repo / "data" / "pilot_short_skylark"

    # --- collect all round_R*_score.json data ---
    rounds_data = []
    for r_idx in range(1, 31):
        p = out_root / f"round_R{r_idx}_score.json"
        r_id = f"R{r_idx}"
        if p.exists():
            d = json.loads(p.read_text(encoding="utf-8"))
            rounds_data.append({
                "round": r_id,
                "total": d.get("total_mean", 0.0),
                "tech": d.get("tech_mean", 0.0),
                "visual": d.get("visual_mean", 0.0),
                "narrative": d.get("narrative_mean", 0.0),
                "genre": d.get("genre_mean", 0.0),
                "label": ROUND_LABELS.get(r_id, ""),
            })
    if not rounds_data:
        print("[fatal] no round_R*_score.json found")
        return 1

    # --- ASCII bar chart ---
    lines = []
    lines.append("# AI 漫剧 — R1→R30 评分演进图（30 轮迭代）\n")
    lines.append("> 无限恐怖批次: R1-R20 (3 集) | 聊斋·聂小倩批次: R21-R30 (3 集)\n")
    lines.append("## 1. 总分演进（每格 = 2 分）\n")
    lines.append("```")
    lines.append(f"{'轮':<5} {'总分':>7}  {'演进 (0 ─────── 100)':<55}  关键改动")
    lines.append("-" * 130)
    for r in rounds_data:
        bar_len = max(0, min(50, int(round(r["total"] / 2))))
        bar = "█" * bar_len + "·" * (50 - bar_len)
        lines.append(
            f"{r['round']:<5} {r['total']:>7.2f}  {bar}  {r['label']}"
        )
    lines.append("```\n")

    # --- 4-dim breakdown table ---
    lines.append("## 2. 四维分项演进\n")
    lines.append("| 轮 | 总分 | Tech/40 | Visual/30 | Narrative/20 | Genre/10 | Δ from prev |")
    lines.append("|---|---|---|---|---|---|---|")
    prev_total = None
    for r in rounds_data:
        delta = ""
        if prev_total is not None:
            d = r["total"] - prev_total
            delta = f"{d:+.2f}"
        lines.append(
            f"| {r['round']} | **{r['total']:.2f}** | {r['tech']:.1f} | {r['visual']:.2f} | {r['narrative']:.2f} | {r['genre']:.2f} | {delta} |"
        )
        prev_total = r["total"]
    lines.append("")

    # --- batch summary ---
    horror = [r for r in rounds_data if int(r["round"][1:]) <= 20]
    nie = [r for r in rounds_data if int(r["round"][1:]) >= 25]
    lines.append("## 3. 批次进展\n")
    if horror:
        h_start = horror[0]["total"]
        h_end = horror[-1]["total"]
        lines.append(f"- **无限恐怖批次** (R1-R20, 3 集): {h_start:.2f} → {h_end:.2f} = **{h_end - h_start:+.2f}**")
    if nie:
        n_start = nie[0]["total"]
        n_end = nie[-1]["total"]
        lines.append(f"- **聊斋·聂小倩批次** (R25-R29, 2 集): {n_start:.2f} → {n_end:.2f} = **{n_end - n_start:+.2f}**")
    lines.append("")

    # --- write ---
    out_md = out_root / "R30_PROGRESS_CHART.md"
    out_md.write_text("\n".join(lines), encoding="utf-8")
    print(f"[chart] wrote {out_md}")

    # --- matplotlib PNG ---
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        fig, ax = plt.subplots(1, 1, figsize=(14, 6))
        xs = [r["round"] for r in rounds_data]
        ys = [r["total"] for r in rounds_data]
        ax.plot(xs, ys, marker="o", linewidth=2, color="#C5283D")
        ax.axhline(99, color="#666", linestyle="--", linewidth=1, label="Target 99")
        for x, y in zip(xs, ys):
            ax.annotate(f"{y:.1f}", (x, y), textcoords="offset points", xytext=(0, 6), ha="center", fontsize=8)
        ax.set_xlabel("Round")
        ax.set_ylabel("Total Score (out of 100)")
        ax.set_title("AI Manhua Quality — R1→R29 Iteration (29 rounds)")
        ax.set_ylim(40, 100)
        ax.grid(True, alpha=0.3)
        ax.legend(loc="lower right")
        plt.xticks(rotation=45)
        plt.tight_layout()
        out_png = out_root / "R30_progress_chart.png"
        plt.savefig(out_png, dpi=120, bbox_inches="tight")
        print(f"[chart] wrote {out_png}")
    except ImportError:
        print("[chart] matplotlib unavailable, skipped PNG")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
