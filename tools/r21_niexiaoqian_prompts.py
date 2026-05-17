"""R21 — Claude Opus 4.7 工业级聊斋·聂小倩 3 集 prompt 设计.

故事骨架（蒲松龄《聊斋志异·聂小倩》, 公版作品）：
- EP01 兰若投宿: 书生宁采臣月夜投宿荒废古寺，蝙蝠惊飞破匾，烛火忽明忽暗，铜镜悬念
- EP02 月下倩影: 白衣聂小倩月下回眸，眉间朱砂痣特写，黄金化光尘
- EP03 剑光悬念: 燕赤霞登场，青蓝剑光掠夜空，老姥姥剪影暗示更大恐怖

工业级悬念剧规范（R12 沉淀）：
1. 前 1-2s 主角特写锚定（ArcFace within-ep 锁）
2. 中段稳定追踪同一主体（HSV color consistency）
3. 末 2s 强悬念视觉钩子（freeze / silhouette / extreme backlight）
4. 通篇无字幕文字、无角色名说出
5. 古风冷青 + 月白 + 朱砂红 三调色板
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


EPISODE_SKELETONS = [
    {
        "ep_id": "ep01_nie_lanruosi",
        "ep_title": "EP01 — 兰若投宿（聊斋·聂小倩 公版第一段）",
        "narrative_arc": "古寺远景 → 书生宁采臣推门入院 → 烛火飘忽察觉异样 → 末帧铜镜倒影空缺（人在镜外，镜中无影）悬念",
        "protagonist": "宁采臣（24 岁书生，浅灰青长袍，背书箧，温润少年眉目，淡眉骨）",
        "setting": "兰若寺破败山门 + 月夜竹影 + 神台空寂 + 铜镜古朴",
        "cliffhanger_design": "末 2s 宁采臣点亮油灯走近供桌铜镜，镜面只显空灵倒影未现人影，他怔立不语，烛火忽地一暗（暗示阴司之物在场）",
        "ref_imagery": "白蛇缘起兰若寺意境 60% + 倩女幽魂 1987 古寺夜景 30% + 神探狄仁杰雾林月夜 10%",
        "lock_symbols": "供桌铜镜（每集都出现）",
    },
    {
        "ep_id": "ep02_nie_appears",
        "ep_title": "EP02 — 月下倩影（聊斋·聂小倩 公版第二段）",
        "narrative_arc": "三更梆子 → 回廊烛火 → 聂小倩月下回眸特写 → 朱砂痣大特写 → 末帧她递出黄金化作柔和光尘",
        "protagonist": "聂小倩（20 岁亚裔古风女鬼，白衣襦裙，浅粉缎带，眉间一点朱砂痣 #C5283D 直径 3mm，杏眼浅蓝灰微光，白玉镯半透）",
        "setting": "兰若东侧回廊 + 月光月白 + 烛火暖橘对比 + 黄金（古币）",
        "cliffhanger_design": "末 1.5s 她将一袋黄金（古币）递出，黄金接触桌面瞬间化作柔和光尘飘散（暗示其非人，光尘是阴司之物），她抬头一笑朱砂痣特写定格",
        "ref_imagery": "倩女幽魂王祖贤回眸经典 + 狐妖小红娘月红仙气 + 白蛇缘起白素贞水袖",
        "lock_symbols": "眉间朱砂痣 #C5283D （每镜可见率 ≥80%）+ 月光月白调",
    },
    {
        "ep_id": "ep03_yan_chixia",
        "ep_title": "EP03 — 剑光悬念（聊斋·聂小倩 公版第三段）",
        "narrative_arc": "雨后天青 → 客栈榻友人昏迷 → 燕赤霞推门登场（道袍 + 剑） → 末帧夜空青蓝剑光掠过 + 远处院落剪影中老姥姥影子",
        "protagonist": "燕赤霞（30 岁亚裔道士剑客，深墨色道袍 + 暗红披风，腰间褐色革囊与短剑鞘，右眉骨浅疤，刚毅沉稳）",
        "setting": "雨后天青清晨 + 客栈榻 + 远处兰若寺剪影",
        "cliffhanger_design": "末 2s 剑出鞘青蓝光辉一闪，镜头快摇至远处院落剪影，墙影中浮出一道老妪佝偻剪影（老姥姥，剧情中真正的妖王）— 暗示更大恐怖，画面定格",
        "ref_imagery": "倩女幽魂燕赤霞午马形象 + 镖人剑客武学 + 黑泽明《七武士》侧光剑客",
        "lock_symbols": "革囊（每镜可见）+ 剑光青蓝（仅末帧）+ 远景兰若轮廓",
    },
]


def design_prompt_via_opus(skeleton: dict) -> str:
    try:
        sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
        from multi_provider_vlm import ClaudeProvider  # type: ignore
    except Exception as e:
        print(f"  [fail] {e}")
        return ""

    cp = ClaudeProvider()
    client = cp._build_client()

    system = (
        "你是顶级影视摄影指导，为火山方舟「小云雀 Agent 2.0 = Seedance 2.0 fast 720p with reference」"
        "视频生成 API 设计 15 秒竖屏 9:16 中国古风幽怨美学短片 prompt。"
        "严格约束：\n"
        "1. 输出只能是 prompt 正文（简体中文），不带任何 markdown、解释、说明。\n"
        "2. 长度 500-700 字。\n"
        "3. 结构：5 段时间标签（如【0-2s 锚定】【2-6s 主体】【6-10s 深化】【10-13s 悬念铺】【13-15s 钩子定格】）。\n"
        "4. 前 1-2 秒必须主角面部超近特写锚定（用于 ArcFace 一致性锁）。\n"
        "5. 中间 8 秒稳定追踪同一主体，少切镜（保色板一致）。\n"
        "6. 末 2 秒必须强烈视觉悬念—frozen gesture / 倒影空缺 / 极端逆光 / 妖鬼剪影。无字幕文字。\n"
        "7. 色板：古风冷青 + 月白 + 朱砂红三调（不要 cyber teal-orange）。Unreal5 路径追踪 + cel-shading 描边。\n"
        "8. 每段标注具体镜头语言（广角 / 中景跟拍 / 大特写 / 浅景深推 / 慢摇）。\n"
        "9. 必须包含锁定符号（角色身份标志，跨集一致）。\n"
        "10. 禁止：血腥写实 / 性暗示构图 / 跳吓特写 / 任何字幕或文字图案入画。\n"
        "回复为 prompt 正文，无引号无前缀。"
    )
    user = (
        f"# 章节: {skeleton['ep_title']}\n\n"
        f"## 叙事弧\n{skeleton['narrative_arc']}\n\n"
        f"## 主角外观\n{skeleton['protagonist']}\n\n"
        f"## 场景\n{skeleton['setting']}\n\n"
        f"## 末帧悬念设计\n{skeleton['cliffhanger_design']}\n\n"
        f"## 视觉参考\n{skeleton['ref_imagery']}\n\n"
        f"## 锁定符号\n{skeleton['lock_symbols']}\n\n"
        "请基于以上骨架，写一段 500-700 字的中文 prompt。"
    )
    try:
        msg = client.messages.create(
            model=os.environ.get("ANTHROPIC_MODEL", "claude-opus-4-7"),
            max_tokens=2200,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        text = msg.content[0].text.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1] if "\n" in text else text
            if "```" in text:
                text = text.rsplit("```", 1)[0]
        return text.strip()
    except Exception as e:
        print(f"  [fail] Opus error: {e}")
        return ""


def main() -> int:
    repo = pathlib.Path(__file__).resolve().parents[1]
    try:
        sys.path.insert(0, str(repo))
        from pilot.run_three_short_episodes import load_env_file  # type: ignore
        load_env_file(repo / ".env")
    except Exception:
        pass

    results = []
    for sk in EPISODE_SKELETONS:
        print(f"\n=== Designing R21 prompt for {sk['ep_id']} ===")
        print(f"  cliffhanger: {sk['cliffhanger_design'][:80]}...")
        prompt = design_prompt_via_opus(sk)
        if not prompt or len(prompt) < 200:
            print(f"  [SKIP] empty or too short: {len(prompt)}")
            results.append({"ep_id": sk["ep_id"], "ok": False, "prompt": prompt})
            continue
        if len(prompt) > 2000:
            print(f"  [WARN] truncating {len(prompt)} → 2000")
            prompt = prompt[:2000]
        print(f"  [OK] len={len(prompt)}, preview: {prompt[:120]!r}...")
        results.append({"ep_id": sk["ep_id"], "ok": True, "prompt": prompt, "skeleton": sk})

    out_json = repo / "prompts" / "episodes" / "r21_niexiaoqian.json"
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n[saved] {out_json}")

    # Storyboard.md for rubric scoring
    sb = ["# 聊斋·聂小倩 3 集分镜本（R21 Claude Opus 4.7 工业级悬念版）\n"]
    for i, r in enumerate(results, 1):
        if not r.get("ok"):
            continue
        sb.append(f'## EP{i:02d} "{r["ep_id"]}"\n')
        sb.append("```")
        sb.append(r["prompt"])
        sb.append("```\n")
    (repo / "data" / "novel-聂小倩-storyboard.md").write_text("\n".join(sb), encoding="utf-8")
    print(f"[saved] storyboard.md updated")

    ok = sum(1 for r in results if r.get("ok"))
    print(f"\n[R21 DONE] {ok}/3 聂小倩 prompts generated by Opus 4.7")
    return 0 if ok == 3 else 1


if __name__ == "__main__":
    raise SystemExit(main())
