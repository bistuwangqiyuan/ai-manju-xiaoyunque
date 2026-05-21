"""Shell 2: Seedream 5.0 Lite 生成 4 角色 × 8 张参考图.

为 Skylark Agent 2.0 提供 img_url_list:
- 郑吒 (24岁亚裔男青年, 黑色短碎发, 灰蓝衬衫)
- 张杰 (24-25 岁亚裔男青年, 黑发齐肩, 面部疤痕, 军绿外套)
- 戴眼镜女孩 (25岁亚裔女, 黑长直发, 金属边框眼镜, 灰白衬衫)
- 马修·艾迪森 (黑人雇佣兵队长, 战术装, MP5)

每角色 8 张 prompt-only 参考图（不同角度/表情/光照),共 32 张.

需要先有 TOS / 本地 HTTP 服务暴露 URL 给 Skylark。本脚本默认假设有 Volcengine TOS
或本地 ngrok 类公网穿透 — 若没有,可以将 base64 编码图像作为 fallback 但需 Skylark 支持。

调用前置: pip install volcengine-python-sdk
"""
from __future__ import annotations

import json
import os
import pathlib
import sys
import time
import uuid

_REPO = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO))


CHARACTER_PROMPTS: dict[str, list[str]] = {
    "zhengzha": [
        # 8 个角度 + 表情 + 光照
        "现代亚裔男青年24岁，黑色短碎发略乱，瞳孔放大，灰蓝色衬衫袖口卷至肘部，正面证件照式肩部以上中景，干净浅灰背景，电影级冷青暖橘 teal-orange 调色，写实细节。",
        "现代亚裔男青年24岁，黑色短碎发，灰蓝色衬衫，3/4 侧脸面向左侧，表情迷茫困惑，电影级 teal-orange 调色，柔光左上，浅灰背景。",
        "现代亚裔男青年24岁，黑色短碎发，灰蓝色衬衫，3/4 侧脸面向右侧，表情警惕戒备，电影级 teal-orange 调色，硬光右上，浅灰背景。",
        "现代亚裔男青年24岁，黑色短碎发，灰蓝色衬衫，正脸大特写，瞳孔放大充血，额头冷汗，红色应急灯反射在皮肤上，深青阴影写实电影质感。",
        "现代亚裔男青年24岁，黑色短碎发，灰蓝色衬衫，全身正面立姿，手心微颤，浅灰背景，电影级 teal-orange 调色。",
        "现代亚裔男青年24岁，黑色短碎发，灰蓝色衬衫，蹲姿手撑地面，3/4 侧面，光线从顶部洒下，电影级冷青阴影。",
        "现代亚裔男青年24岁，黑色短碎发，灰蓝色衬衫，背身回头特写，表情惊愕，温暖光从后方洒在头发上，深青阴影 teal-orange 调色。",
        "现代亚裔男青年24岁，黑色短碎发，灰蓝色衬衫，眉部+眼睛大特写（不显示嘴），瞳孔放大紧张，电影级冷青光，浅灰背景。",
    ],
    "zhangjie": [
        "现代亚裔男青年24-25岁，黑发齐肩稍乱半遮额，脸上多道由额到下颌斜向交错的旧疤痕（深暗红微突起），深色高领T恤外套军绿色机能外套，正面证件照式中景，浅灰背景，电影级 teal-orange 调色。",
        "现代亚裔男青年24-25岁，齐肩黑发，脸部疤痕，军绿机能外套，3/4 侧脸面向左侧，表情冷峻，二指夹着燃烧的香烟近脸位置，电影级 teal-orange。",
        "现代亚裔男青年24-25岁，齐肩黑发，脸部疤痕，3/4 侧脸面向右侧，嘴角冷笑，瞳孔泛冷光，电影级 teal-orange，硬光右上。",
        "现代亚裔男青年24-25岁，齐肩黑发，脸部疤痕，正脸大特写抬眼直视，瞳孔锋利，烟雾在前景模糊飘过，电影级 teal-orange 调色。",
        "现代亚裔男青年24-25岁，齐肩黑发，军绿机能外套，全身正面立姿，左手腰间别银黑色沙漠之鹰手枪，电影级 teal-orange 调色，浅灰背景。",
        "现代亚裔男青年24-25岁，齐肩黑发，脸部疤痕，双手部特写持握沙漠之鹰手枪 (Desert Eagle) 银黑色枪身，指关节略紧，金属拉丝表面反射，电影级 teal-orange。",
        "现代亚裔男青年24-25岁，齐肩黑发，脸部疤痕，坐姿膝盖横置沙漠之鹰，背靠金属座椅，电影级 teal-orange，深青阴影。",
        "现代亚裔男青年24-25岁，齐肩黑发，脸部疤痕，眉骨+眼睛大特写（不显示嘴），瞳孔锋利如刀，电影级 teal-orange，冷蓝光从侧面。",
    ],
    "glasses_girl": [
        "现代亚裔女青年25岁，黑长直发束在脑后，金属边框圆眼镜，灰白衬衫职业装袖口整齐，正面证件照式中景，浅灰背景，电影级 teal-orange 调色，冷静知性气质。",
        "现代亚裔女青年25岁，黑长直发，金属边框圆眼镜，灰白衬衫，3/4 侧脸面向左侧，表情思考冷静，电影级 teal-orange，柔光左上。",
        "现代亚裔女青年25岁，黑长直发，金属边框圆眼镜，灰白衬衫，3/4 侧脸面向右侧，眼神锐利分析，电影级 teal-orange，硬光右上。",
        "现代亚裔女青年25岁，黑长直发，金属边框圆眼镜，灰白衬衫，正脸大特写戴眼镜，眼镜反光中可见远处场景，电影级 teal-orange。",
        "现代亚裔女青年25岁，黑长直发，金属边框圆眼镜，灰白衬衫+深灰长裤，全身正面立姿，整理袖口，电影级 teal-orange，浅灰背景。",
        "现代亚裔女青年25岁，黑长直发，金属边框圆眼镜，灰白衬衫，侧坐手撑下颌沉思，电影级 teal-orange，深青阴影。",
        "现代亚裔女青年25岁，黑长直发，金属边框圆眼镜，灰白衬衫，背身回头看的中景，表情警觉，电影级 teal-orange。",
        "现代亚裔女青年25岁，金属边框眼镜+眼眸特写（不显示嘴），眼镜反光中可见冷青光，电影级 teal-orange，浅灰背景。",
    ],
    "mercenary_matthew": [
        "现代非裔男性35-40岁雇佣兵队长，平头黑发，黑色战术背心+战术腰带+军绿T恤，胸前挂 MP5 突击步枪带，正面证件照式中景，浅灰背景，电影级 teal-orange，硬朗冷峻气质。",
        "现代非裔男性雇佣兵队长，战术装备，3/4 侧脸面向左侧，戴夜视镜推上额头，表情指挥下属，电影级 teal-orange，硬光从上。",
        "现代非裔男性雇佣兵队长，战术装备，3/4 侧脸面向右侧，表情警觉巡视，电影级 teal-orange，深青阴影。",
        "现代非裔男性雇佣兵队长，战术装备，正脸大特写，瞳孔锐利，电影级 teal-orange，红色应急灯反射在皮肤。",
        "现代非裔男性雇佣兵队长，战术装备，全身正面立姿手持 MP5 突击步枪，电影级 teal-orange，浅灰背景。",
        "现代非裔男性雇佣兵队长，战术装备，半蹲姿势检查武器，手部特写枪机操作，电影级 teal-orange。",
        "现代非裔男性雇佣兵队长，战术装备，背身回头指示部署，电影级 teal-orange，深青阴影。",
        "现代非裔男性雇佣兵队长，眉部+眼睛大特写戴夜视镜推上额头，电影级 teal-orange，冷蓝光从侧面。",
    ],
}


def main() -> int:
    """生成所有角色参考图,落盘到 data/characters/<char_id>/ref_<n>.png

    注意: 本脚本调用 Volcengine Visual API Seedream 5.0 Lite (jimeng_t2i_v50_lite).
    需要 .env 含 VOLC_ACCESS_KEY + VOLC_SECRET_KEY.
    """

    out_root = _REPO / "data" / "characters"
    out_root.mkdir(parents=True, exist_ok=True)

    # ★ .env 强制覆盖：Claude Code 会注入 ANTHROPIC_BASE_URL=api.anthropic.com 屏蔽代理
    # 标准 python-dotenv 默认就是 override；与 pilot/run_three_short_episodes.py 保持一致
    for line in (pathlib.Path(_REPO / ".env")).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        v = v.split("#", 1)[0].strip()
        if k and v:
            os.environ[k.strip()] = v

    from src.shell2_character_assets.gen_seedream import SeedreamClient, SeedreamRequest

    client = SeedreamClient()
    total = 0
    for char_id, prompts in CHARACTER_PROMPTS.items():
        char_dir = out_root / char_id
        char_dir.mkdir(parents=True, exist_ok=True)
        urls: list[str] = []
        for i, prompt in enumerate(prompts):
            print(f"Generating {char_id} [{i+1}/{len(prompts)}] …")
            try:
                imgs = client.generate(
                    SeedreamRequest(prompt=prompt, num_images=1, aspect_ratio="3:4")
                )
                urls.extend(imgs)
                total += len(imgs)
            except Exception as e:
                print(f"  FAIL {char_id} #{i}: {e}")
        manifest = {
            "char_id": char_id,
            "reference_image_urls": urls,
            "canonical_image_url": urls[0] if urls else "",
        }
        (char_dir / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"  → {char_id}: {len(urls)} images")

    print(f"Done. Generated {total} reference URLs under {out_root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
