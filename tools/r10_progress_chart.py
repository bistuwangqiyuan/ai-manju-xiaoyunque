"""R10 — 生成 R1→R9 进度可视化（ASCII + matplotlib PNG）."""
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


def main() -> int:
    repo = pathlib.Path(__file__).resolve().parents[1]
    out_root = repo / "data" / "pilot_short_skylark"
    snap_dirs = sorted((repo / "data").glob("pilot_short_skylark_R10_FINAL_*"))
    snap_dir = snap_dirs[-1] if snap_dirs else out_root

    # --- collect round data ---
    rounds_data = []
    round_changes = {
        "R1": "Baseline (broken VLM)",
        "R2": "Rubric bug fix v1",
        "R3": "Multi-provider VLM cascade (real measure)",
        "R4": "Skylark 真接口生成 horror 内容",
        "R5": "Prompt extractor format-tolerant",
        "R6": "CLIP-EN + ArcFace within-ep + Motion sweet-spot",
        "R7": "4 thresholds rebalance",
        "R8": "HSV + ArcFace best-track 聚类",
        "R9": "Aesthetic VLM + palette teal-orange",
    }
    for r_idx in range(1, 10):
        p = out_root / f"round_R{r_idx}_score.json"
        r_id = f"R{r_idx}"
        if p.exists():
            d = json.loads(p.read_text(encoding="utf-8"))
            rounds_data.append({
                "round": r_id,
                "total": d["total_mean"],
                "tech": d["tech_mean"],
                "visual": d["visual_mean"],
                "narrative": d["narrative_mean"],
                "genre": d["genre_mean"],
                "label": round_changes.get(r_id, ""),
            })

    # --- ASCII bar chart ---
    lines = []
    lines.append("# AI 漫剧 — 无限恐怖 Ch.1 — R1→R9 进度可视化\n")
    lines.append("## 1. 总分演进（每格 = 2 分）\n")
    lines.append("```")
    lines.append(f"{'轮':<5} {'总分':>7}  {'演进 (0 ─────── 100)':<55}  关键改动")
    lines.append("-" * 110)
    for r in rounds_data:
        bar_len = int(round(r["total"] / 2))
        bar = "█" * bar_len + "·" * (50 - bar_len)
        lines.append(
            f"{r['round']:<5} {r['total']:>7.2f}  {bar}  {r['label']}"
        )
    lines.append("-" * 110)
    lines.append(f"{'目标':<5} {'99.00':>7}  " + "█" * 49 + "·" + "  ← 99 分世界顶级目标")
    lines.append("```\n")

    # --- 4-dim stacked chart ---
    lines.append("## 2. 四维度分解（Tech=40 Visual=30 Narrative=20 Genre=10）\n")
    lines.append("```")
    lines.append(f"{'轮':<5} {'Tech /40':>10} {'Visual /30':>12} {'Narrative /20':>15} {'Genre /10':>11}  Total")
    lines.append("-" * 80)
    for r in rounds_data:
        # Mini bars per dim
        t_bar = "█" * int(round(r['tech'] / 40 * 10)) + "·" * (10 - int(round(r['tech'] / 40 * 10)))
        v_bar = "█" * int(round(r['visual'] / 30 * 10)) + "·" * (10 - int(round(r['visual'] / 30 * 10)))
        n_bar = "█" * int(round(r['narrative'] / 20 * 10)) + "·" * (10 - int(round(r['narrative'] / 20 * 10)))
        g_bar = "█" * int(round(r['genre'] / 10 * 10)) + "·" * (10 - int(round(r['genre'] / 10 * 10)))
        lines.append(
            f"{r['round']:<5} {t_bar}  {v_bar}  {n_bar}  {g_bar}  {r['total']:>6.2f}"
        )
    lines.append("```\n")

    # --- delta table ---
    lines.append("## 3. 每轮增量（Δ from previous）\n")
    lines.append("| 轮 | Total | Δ | Tech | Visual | Narrative | Genre | 关键改动 |")
    lines.append("|---|---|---|---|---|---|---|---|")
    prev = None
    for r in rounds_data:
        delta = ""
        if prev is not None:
            d = r["total"] - prev["total"]
            delta = f"{d:+.2f}" if abs(d) >= 0.01 else "0"
        lines.append(
            f"| {r['round']} | {r['total']:.2f} | {delta} | "
            f"{r['tech']:.1f} | {r['visual']:.2f} | {r['narrative']:.2f} | "
            f"{r['genre']:.2f} | {r['label']} |"
        )
        prev = r
    lines.append("")

    # --- per-dim trajectory ASCII sparkline ---
    lines.append("## 4. 单维度趋势（sparkline 0 ─→ max）\n")
    lines.append("```")
    for dim, max_v in [("tech", 40), ("visual", 30), ("narrative", 20), ("genre", 10)]:
        chars = "▁▂▃▄▅▆▇█"
        vals = [r[dim] for r in rounds_data]
        spark = "".join(chars[min(len(chars) - 1, int(v / max_v * (len(chars) - 1)))] for v in vals)
        lines.append(f"  {dim:<10} /{max_v:>2}: {spark}  ({vals[0]:.1f} → {vals[-1]:.1f})")
    lines.append("```\n")

    # --- summary ---
    first = rounds_data[0]
    last = rounds_data[-1]
    pct = (last["total"] / first["total"] - 1) * 100
    lines.append("## 5. 进度总结\n")
    lines.append(f"- **起点 R1**: {first['total']:.2f}/100 (Tech {first['tech']:.1f}, Vis {first['visual']:.1f}, Nar {first['narrative']:.1f}, Gen {first['genre']:.1f})")
    lines.append(f"- **终点 R9**: {last['total']:.2f}/100 (Tech {last['tech']:.1f}, Vis {last['visual']:.1f}, Nar {last['narrative']:.1f}, Gen {last['genre']:.1f})")
    lines.append(f"- **总跃迁**: +{last['total'] - first['total']:.2f} 分（+{pct:.0f}%）")
    lines.append(f"- **9 轮平均增益**: +{(last['total'] - first['total']) / (len(rounds_data) - 1):.2f} 分/轮")
    lines.append(f"- **距 99 分目标**: 还差 **{99 - last['total']:.2f}** 分")
    lines.append("")

    # --- write text chart ---
    chart_text = "\n".join(lines)
    (out_root / "R10_PROGRESS_CHART.md").write_text(chart_text, encoding="utf-8")
    (snap_dir / "R10_PROGRESS_CHART.md").write_text(chart_text, encoding="utf-8")
    print(f"[chart] R10_PROGRESS_CHART.md ({len(chart_text)} chars)")

    # --- matplotlib PNG (optional) ---
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(11, 9), gridspec_kw={"height_ratios": [1, 1.3]})

        # Top: total score line + target line
        rounds = [r["round"] for r in rounds_data]
        totals = [r["total"] for r in rounds_data]
        ax1.plot(rounds, totals, "o-", color="#2563eb", linewidth=2.5, markersize=9, label="Total Score")
        ax1.axhline(99, color="#dc2626", linestyle="--", linewidth=1.5, alpha=0.75, label="Target 99")
        ax1.fill_between(rounds, totals, alpha=0.18, color="#2563eb")
        for i, (r, t) in enumerate(zip(rounds, totals)):
            ax1.annotate(f"{t:.1f}", xy=(i, t), xytext=(0, 10),
                        textcoords="offset points", ha="center", fontsize=9, color="#1e3a8a", fontweight="bold")
        ax1.set_ylim(40, 102)
        ax1.set_ylabel("Score / 100", fontsize=11, fontweight="bold")
        ax1.set_title("AI Manhua — Infinite Horror Ch.1 — R1→R9 Total Score Progression",
                     fontsize=13, fontweight="bold")
        ax1.legend(loc="lower right", fontsize=10)
        ax1.grid(True, alpha=0.3, linestyle=":")

        # Bottom: stacked 4-dim bars
        import numpy as np
        x = np.arange(len(rounds))
        tech_vals = [r["tech"] for r in rounds_data]
        vis_vals = [r["visual"] for r in rounds_data]
        nar_vals = [r["narrative"] for r in rounds_data]
        gen_vals = [r["genre"] for r in rounds_data]
        ax2.bar(x, tech_vals, label="Tech (max 40)", color="#0891b2", edgecolor="white")
        ax2.bar(x, vis_vals, bottom=tech_vals, label="Visual (max 30)", color="#7c3aed", edgecolor="white")
        ax2.bar(x, nar_vals, bottom=[a + b for a, b in zip(tech_vals, vis_vals)],
               label="Narrative (max 20)", color="#f59e0b", edgecolor="white")
        ax2.bar(x, gen_vals, bottom=[a + b + c for a, b, c in zip(tech_vals, vis_vals, nar_vals)],
               label="Genre (max 10)", color="#dc2626", edgecolor="white")
        ax2.set_xticks(x)
        ax2.set_xticklabels(rounds)
        ax2.set_ylabel("Sub-score breakdown", fontsize=11, fontweight="bold")
        ax2.set_xlabel("Iteration round", fontsize=11)
        ax2.set_title("4-Dimension Stacked Decomposition", fontsize=12, fontweight="bold")
        ax2.legend(loc="upper left", fontsize=9, ncol=4)
        ax2.set_ylim(0, 100)
        ax2.grid(True, axis="y", alpha=0.3, linestyle=":")

        plt.tight_layout()
        png_path = out_root / "R10_progress_chart.png"
        plt.savefig(png_path, dpi=130, bbox_inches="tight")
        plt.savefig(snap_dir / "R10_progress_chart.png", dpi=130, bbox_inches="tight")
        plt.close(fig)
        print(f"[chart] R10_progress_chart.png saved → out_root + snap_dir")
    except ImportError:
        print("[chart] matplotlib not available — PNG skipped, MD chart ok")
    except Exception as e:
        print(f"[chart] PNG failed: {type(e).__name__}: {e}")

    # --- print ASCII chart to console for immediate view ---
    print("\n" + "=" * 110)
    print(chart_text)
    print("=" * 110)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
