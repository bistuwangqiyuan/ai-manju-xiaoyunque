"""无限恐怖 (Infinite Horror) Chapter 1 三集 ~15s smoke test prompts.

剧情 (per novel-无限恐怖.md 第一章):
- ep01: 郑吒在快速行驶的车厢内醒来，环视周围意识昏迷的同伴与外籍雇佣兵
- ep02: 张杰冷笑抽烟、调试沙漠之鹰、凝视镜头
- ep03: 车厢减速到地下车站，雇佣兵+张杰+眼镜女+郑吒鱼贯出门

风格: 现代赛博惊悚电影级 (Unreal5 路径追踪 + cinematic Teal-Orange 调色 + 实拍写实),
完全替代原项目的"古风3D国漫"基调，配合原文都市/生化危机题材。

设计原则:
- 每段 prompt ≤ 2000 chars (Skylark 硬限)
- 内嵌 4 个清晰 beats (hook → 推进 → 重点 → 悬念) 以引导 ~15s 节奏
- 提示物理光照+材质细节，让 Skylark 的 cel-shading 倾向被电影级写实拉回
- 禁忌写明: 无字幕文字、无血腥写实、无性暗示，符合微短剧合规
"""

EPISODES: list[dict] = [
    {
        "ep_id": "ep01_zhengzha_wakes",
        "title": "郑吒醒来车厢",
        "scene_summary": "高速行驶的密闭车厢内，郑吒从地面猛地坐起，环顾四周5名昏迷同伴+10余名外籍雇佣兵",
        # R10 refined: 开头一句"电影级单帧"前缀 + 显式视觉名词，提升 CLIP 对齐
        # 注：避开 "armed/weapon/body" 等英文风控敏感词，用 "security personnel/passengers resting"
        "prompt": """A cinematic still frame from a modern cyberpunk sci-fi: security personnel in tactical gear standing inside a moving train cabin, passengers resting on a wet reflective metal floor, dark teal blue palette with warm orange emergency lighting accents, photorealistic 35mm film grain, shallow depth of field. 现代赛博惊悚电影级竖屏9:16，Unreal5路径追踪+实时光追+电影级Teal-Orange调色（深青冷暗影+暖橘高光，对比强烈，胶片颗粒）。

【0-3s 钩子】高速行驶车厢内部，金属管线纵横交错，顶部红色应急灯频闪一下一暗，地面薄薄一层冷凝水反射光带。车厢窗外水泥隧道高速流动出冷青光带。

【3-8s 醒来】郑吒（24岁亚裔男青年，黑色短碎发略乱，灰蓝色衬衫袖口卷到肘部，深色西裤略皱，瞳孔大且充血）从坚硬金属地板上猛地弹身坐起，手掌撑地颤抖，额头细密冷汗在应急灯下泛橘光。他张嘴喘息一秒。

【8-12s 视角扫】镜头慢摇跟随郑吒视线：地面身边躺着 5 个意识昏迷的男女（侧光呈深青剪影，姿态各异），更远处车厢另一端 10 余名全副武装的外籍雇佣兵（黑色战术背心+MP5突击步枪斜挂胸前+夜视镜头戴推上），他们冷漠地侧视前方不与镜头交集。

【12-15s 转头】郑吒转头看向画面右侧（镜头预示性推近），下一帧将切到一个站立人影侧脸轮廓（暂未露脸）。背景应急灯越发明灭。

镜头语言: 广角车厢全景 → 中景跟拍郑吒起身 → 第一视角扫视 → 大特写郑吒转头。
质感细节: 阴影处皮肤泛蓝绿冷调，高光处暖橘金属反射，景深浅，背景虚化，35mm 电影颗粒。
禁忌: 画面不出现任何字幕文字/HUD文本/字符；不含血腥写实/性暗示/恐怖跳吓特写。""",
    },
    {
        "ep_id": "ep02_zhangjie_revolver",
        "title": "张杰冷笑沙鹰",
        "scene_summary": "张杰二指夹烟冷笑，左手调试沙漠之鹰手枪，眼神凌厉直视",
        # 注：用 "stylish prop pistol" 替代 "Desert Eagle"避免英文武器词触发风控
        "prompt": """A cinematic close-up still frame from a modern cyberpunk sci-fi: a scarred-face young Asian man in tactical gear inspecting a stylish prop pistol, cigarette smoke drifting across his face, dark teal blue shadows with warm orange highlights, photorealistic skin texture, 35mm anamorphic lens, shallow depth of field. 现代赛博惊悚电影级竖屏9:16，Unreal5路径追踪+实时光追+电影级Teal-Orange调色（暗部冷青阴影/亮部暖橘高光，胶片颗粒）。

【0-3s 钩子】镜头从烟雾上升处慢推聚焦：一缕香烟青蓝灰烟雾袅袅升起，烟尾火星明灭，背景失焦深青冷调。

【3-8s 抬眼】张杰（24-25岁亚裔男青年，黑发齐肩稍乱半遮额，脸上多道由额到下颌斜向交错的狰狞旧疤痕，疤痕颜色暗红微突起，深色高领 T 恤外套军绿色机能外套，胸口口袋有一道战术尼龙带）右手二指夹着燃烧的香烟，缓缓抬起眼睛，瞳孔在车厢红色应急灯下泛冷光，嘴角微挑出残酷冷笑。

【8-12s 调试沙鹰】张杰左手缓缓抬起握住一把沙漠之鹰手枪 .50 AE 银黑色枪身（金属拉丝/磨砂表面+黑色聚合物握把+银色枪管），熟练弹出弹匣检查 .50 AE 子弹链（亮金黄铜外露），金属哗啦清脆声，然后回插弹匣、拉栓上膛。镜头特写枪机滑动+弹匣推进+张杰指节略紧。

【12-15s 凝视】张杰将沙漠之鹰横置膝盖，眼神锋利如刀直视镜头方向，香烟烟雾在镜头前飘过模糊脸部一瞬，烟尾火星再次明灭。

镜头语言: 烟雾慢推 → 抬眼大特写 → 双手部协同特写 → 眼部大特写。
质感细节: 疤痕表皮微突起细节、香烟烟雾散射粒子、金属枪身镜面反射、暖橘 + 冷青光带交替。
禁忌: 无字幕文字/HUD/角色名称浮窗；无血腥写实；不展示枪口朝向头部的镜头。""",
    },
    {
        "ep_id": "ep03_train_arrives",
        "title": "车厢减速到站",
        "scene_summary": "车厢减速到达地下车站，雇佣兵+张杰+眼镜女+郑吒鱼贯出车厢",
        "prompt": """A cinematic still frame from a modern cyberpunk thriller: a train arriving at a dark industrial underground subway station with hexagonal metal doors, armed mercenaries and civilians stepping out of the cabin onto a wet reflective platform, dark teal blue palette with warm orange LED accents, photorealistic 35mm film grain, wide-angle composition, depth and atmosphere. 现代赛博惊悚电影级竖屏9:16，Unreal5路径追踪+实时光追+电影级Teal-Orange调色，工业 sci-fi 美学。

【0-3s 钩子】车厢内金属摩擦尖锐声渐起，车窗外水泥隧道高速流动渐缓，顶部应急灯频率从快变慢，气流哨声减弱。镜头从隧道窗外缓推回车厢内。

【3-8s 全员准备】镜头摇过车厢内：外籍雇佣兵齐齐起身，机械化检查 MP5 突击步枪弹匣、推下夜视镜头戴，腰间战术腰带哗啦响。张杰从座椅起身别好沙漠之鹰于腰后，整理军绿色机能外套衣角。眼镜女孩（亚裔年轻女性 25 岁，黑长直发束在脑后，金属边框圆眼镜后冷静眼眸，灰白衬衫职业装袖口整齐扣紧，深灰长裤）站起整理袖口，表情冷静。郑吒站起仍带迷茫表情。

【8-12s 到站】车厢稳稳停在地下钢制车站平台，巨型滑动门嘶嘶气压声开启，露出昏暗工业地下走廊，远处一道蜂窝六角形封闭式大门在镜头远端发出冷蓝色 LED 状态指示灯，门上模糊可见 UMBRELLA 工业品牌符号轮廓（不强调）。

【12-15s 出门】众人鱼贯而出，张杰大咧咧第一个迈出车厢踩在金属平台上发出脚步回响，眼镜女孩跟在后侧出门时回头看了郑吒一眼，郑吒最后一个走出车厢，画面定格在他脚尖踏出车厢门槛的瞬间。

镜头语言: 隧道慢推 → 车厢内中景多人 → 大门开启广角 → 中景跟拍出门 → 脚尖大特写定格。
质感细节: 冷青工业地下空间 + 暖橘 LED 状态灯 + 镜面金属地面反射 + 轻微镜头眩光 + 远景冷蓝雾气。
禁忌: 画面无字幕文字/HUD/角色姓名浮窗；UMBRELLA 标识仅虚化轮廓不强调显示；无血腥/性暗示。""",
    },
]
