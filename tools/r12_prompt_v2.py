"""R12 Prompt v2 — 用 Claude Opus 4.7 改写 3 集 prompt 以最大化 R13-R15 reroll 评分.

改写原则（工业级悬念剧规范）：
1. 前 1s：立即主角特写或强标志物（boost ArcFace within-ep + 即时建立人物）
2. 2-12s 中段：稳定追踪同一主体，少切镜（boost HSV color consistency）
3. 末 2-3s：强悬念视觉锚（暗影/不完整人影/极端逆光），引导观众"下集"期待
4. 通篇无字幕文字、无角色名说出（视觉叙事）
5. 强化 cyber-thriller 色板 (teal-orange teal-dominant)

输入：旧 prompts（EPISODE_PLAN 当前）
输出：R12 prompts 保存到 prompts/episodes/r12_v2.json + 新 storyboard.md
"""
from __future__ import annotations
import json
import os
import pathlib
import sys

os.environ.setdefault("PYTHONIOENCODING", "utf-8")
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
except (AttributeError, OSError):
    pass


# Episode 元信息 — 故事位置 + cliffhanger 设计（人工策划骨架）
EPISODE_SKELETONS = [
    {
        "ep_id": "ep01_zhengzha_wakes",
        "ep_title": "EP01 — 觉醒于钢铁车厢（无限恐怖 Ch.1 第一段）",
        "narrative_arc": "失忆觉醒 → 环境扫视 → 发现导师（黑衣青年）→ 末帧锚定其侧脸轮廓（悬念）",
        "protagonist": "24 岁亚裔男青年（短黑发、灰蓝色衬衫、深色西裤、瞳孔放大）",
        "setting": "高速行驶的工业金属车厢，红色应急灯频闪，水泥隧道窗外冷青光带",
        "cliffhanger_design": "末 2s 主角转头视线越过镜头落向画面右侧暗处，下一帧将切到一个未完全露脸的人影侧脸（仅看到下颌+疤痕的轮廓）",
        "ref_imagery": "Blade Runner 2049 拷打室冷青 + Black Mirror《白色圣诞》工业冷感 + 攻壳机动队车厢戏",
    },
    {
        "ep_id": "ep02_zhangjie_revolver",
        "ep_title": "EP02 — 烟雾中的导师（无限恐怖 Ch.1 第二段）",
        "narrative_arc": "烟雾慢推 → 抬眼大特写（脸部疤痕显现）→ 双手协同调试沙鹰枪 → 末帧凝视镜头（杀意外溢）",
        "protagonist": "24-25 岁亚裔男青年（黑色齐肩乱发、脸部多道斜向旧疤痕、深色高领+军绿外套）",
            "setting": "车厢内座椅，烟雾袅袅，应急灯红光冷青阴影",
        "cliffhanger_design": "末 1.5s 角色将沙漠之鹰横置膝盖，眼神锋利如刀直视镜头（破第四面墙），烟雾在镜头前飘过模糊一瞬，最末 0.3s 烟尾火星明灭",
        "ref_imagery": "约翰·威克武器调试 + 牯岭街少年杀人事件冷峻青年 + Drive 2011 沉默暴力美学",
    },
    {
        "ep_id": "ep03_train_arrives",
        "ep_title": "EP03 — 蜂房门前（无限恐怖 Ch.1 第三段）",
        "narrative_arc": "隧道减速 → 车厢内全员准备 → 巨型滑动门开启 → 末帧主角脚尖踏出门槛定格",
        "protagonist": "ensemble: 主角郑吒 + 导师 + 眼镜女孩 + 外籍雇佣兵群体",
        "setting": "地下钢制车站平台，巨型六角形封闭式大门，远处冷蓝 LED 状态灯",
        "cliffhanger_design": "末 2s 主角最后一个出车厢，画面定格在他脚尖刚踏出车厢门槛的瞬间，背景幽深走廊延伸（暗示进入未知）",
        "ref_imagery": "异形 1979 工业飞船走廊 + 生化危机 1 电影蜂房入口 + 黑客帝国矩阵车厢",
    },
]


def design_prompt_via_opus(skeleton: dict) -> str:
    """让 Claude Opus 4.7 基于骨架写一段工业级 15s 视觉 prompt（绝对无字幕文字）."""
    try:
        sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
        from multi_provider_vlm import ClaudeProvider  # type: ignore
    except Exception as e:
        print(f"  [fail] cannot import ClaudeProvider: {e}")
        return ""

    cp = ClaudeProvider()
    client = cp._build_client()

    system = (
        "You are an industry-grade cinematographer designing a 15-second vertical 9:16 "
        "horror/cyber-thriller storyboard prompt for the Skylark Agent 2.0 (Seedance 2.0 "
        "fast 720p with reference) text-to-video API. "
        "STRICT CONSTRAINTS:\n"
        "1. Output is the PROMPT TEXT IN SIMPLIFIED CHINESE only — no extra prose.\n"
        "2. Length 400-600 Chinese characters.\n"
        "3. Structure: 5 timed shot segments (e.g. 【0-3s 锚定】... 【3-8s 主体】... "
        "【8-12s 深化】... 【12-14s 悬念铺】... 【14-15s 钩子定格】).\n"
        "4. FRONT-LOAD protagonist key-feature closeup in first 1-2 seconds (this is critical "
        "for facial recognition consistency lock).\n"
        "5. Middle 8 seconds: stable subject tracking, minimize cuts (cohesive palette).\n"
        "6. Final 2 seconds: STRONG visual cliffhanger — frozen gesture / cut-off silhouette "
        "/ extreme backlight / mysterious incomplete reveal. NO subtitles or text in frame.\n"
        "7. Color palette: cinematic teal-orange (Unreal5 path-traced, film grain, 35mm).\n"
        "8. Specify hue saturation contrast for both shadows (deep teal) and highlights (warm orange).\n"
        "9. Camera language: list 5 named shots in sequence (e.g. wide-tracking → mid-close → "
        "macro-detail → over-shoulder → freeze).\n"
        "10. Forbidden: any on-screen text/HUD/captions, any blood/violence detail, any "
        "sexual implication, any character names spoken aloud (visual storytelling only).\n"
        "Reply with the prompt text only, in fluent literary Chinese."
    )
    user = (
        f"# 章节: {skeleton['ep_title']}\n\n"
        f"## 叙事弧\n{skeleton['narrative_arc']}\n\n"
        f"## 主角外观（必须严格视觉一致）\n{skeleton['protagonist']}\n\n"
        f"## 场景\n{skeleton['setting']}\n\n"
        f"## 末帧 cliffhanger 设计\n{skeleton['cliffhanger_design']}\n\n"
        f"## 视觉参考\n{skeleton['ref_imagery']}\n\n"
        "请基于上述骨架，写一段 400-600 字的中文 Skylark 视频 prompt。"
    )
    try:
        msg = client.messages.create(
            model=os.environ.get("ANTHROPIC_MODEL", "claude-opus-4-7"),
            max_tokens=2000,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        text = msg.content[0].text.strip()
        # Strip markdown code fences if present
        if text.startswith("```"):
            text = text.split("\n", 1)[1] if "\n" in text else text
            if "```" in text:
                text = text.rsplit("```", 1)[0]
        return text.strip()
    except Exception as e:
        print(f"  [fail] Claude messages.create error: {e}")
        return ""


def main() -> int:
    repo = pathlib.Path(__file__).resolve().parents[1]

    # Load env
    try:
        sys.path.insert(0, str(repo))
        from pilot.run_three_short_episodes import load_env_file  # type: ignore
        load_env_file(repo / ".env")
    except Exception:
        pass

    results = []
    for sk in EPISODE_SKELETONS:
        print(f"\n=== Designing R12 prompt for {sk['ep_id']} ===")
        print(f"  cliffhanger: {sk['cliffhanger_design'][:80]}...")
        prompt = design_prompt_via_opus(sk)
        if not prompt or len(prompt) < 100:
            print(f"  [SKIP] Opus returned empty or too short: len={len(prompt)}")
            results.append({"ep_id": sk["ep_id"], "ok": False, "prompt": prompt})
            continue
        if len(prompt) > 2000:
            print(f"  [WARN] prompt {len(prompt)} > 2000 — truncating")
            prompt = prompt[:2000]
        print(f"  [OK] len={len(prompt)}, preview: {prompt[:120]!r}...")
        results.append({"ep_id": sk["ep_id"], "ok": True, "prompt": prompt,
                        "skeleton": sk})

    # Save
    out_json = repo / "prompts" / "episodes" / "r12_v2.json"
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(
        json.dumps(results, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"\n[saved] {out_json}")

    # Also write a storyboard.md for rubric scoring
    sb_lines = ["# 无限恐怖 Ch.1 三集分镜本 (R12 Opus v2 工业级悬念版)\n"]
    for i, r in enumerate(results, 1):
        if not r.get("ok"):
            continue
        sb_lines.append(f'## EP{i:02d} "{r["ep_id"]}"\n')
        sb_lines.append("```")
        sb_lines.append(r["prompt"])
        sb_lines.append("```\n")
    (repo / "data" / "novel-无限恐怖-ch01-storyboard.md").write_text(
        "\n".join(sb_lines), encoding="utf-8"
    )
    print(f"[saved] storyboard.md updated with R12 prompts")

    ok = sum(1 for r in results if r.get("ok"))
    print(f"\n[r12 DONE] {ok}/3 prompts generated by Claude Opus 4.7")
    return 0 if ok == 3 else 1


if __name__ == "__main__":
    raise SystemExit(main())
