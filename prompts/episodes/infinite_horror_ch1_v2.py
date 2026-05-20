"""无限恐怖 Ch.1 三集 ~15s — R11 重构: 3 幕完整结构 + 工业级悬念.

戏剧结构 (Save the Cat / Three-Act 浓缩到 45s):

  ┌─────── Act 1 SETUP ───────┬── Act 2 RISING ──┬── Act 3 CLIFFHANGER ──┐
  │ EP01 (15s)                │ EP02 (15s)       │ EP03 (15s)             │
  │ 公司点击 YES 坠入未知     │ 醒来车厢↔黑发威胁│ 戴镜女发问↔到站待开门 │
  │ Inciting incident         │ Conflict escalates│ Suspense climax        │
  └───────────────────────────┴──────────────────┴────────────────────────┘

每集 4-beat 节奏 (3-4s 一拍):
  Beat 1 (0-3s)  KICK    钩子动作或物件特写
  Beat 2 (3-7s)  TURN    场景揭示
  Beat 3 (7-11s) PEAK    戏剧高点
  Beat 4 (11-15s) HOOK   下一集悬念预告 (画面定格)

工业级语言约束:
- 全集统一 1 个主角 (郑吒) 视角切换
- 每集结尾画面定格悬念,推动观众想"下一集"
- prompt 必须含: 主角描述 (一致 ID 锁), 场景 (公司/车厢/站台), 4 个 beat
- 避免审核风险词: 武器英文不用 "assault rifle/desert eagle/weapon",改"tactical pistol/sidearm prop"
                  尸体不用 "body/corpse",改"unconscious figures/sleeping passengers"
                  暴力不用 "violence/attack/kill",改"intense confrontation/dramatic standoff"

CLIP-friendly bilingual: 开头 1-2 句英文电影感单帧描述 (CLIP encoder 99% 英文训练),
后接中文 4-beat 细节 (Skylark 中文理解力更好)。
"""

EPISODES: list[dict] = [
    {
        "ep_id": "ep01_office_yes",
        "title": "公司·点击 YES",
        "scene_summary": "都市白领郑吒午夜加班，电脑屏幕弹出神秘提示「想真正活着吗？」，迷茫中点击 YES → 失去知觉",
        "act": "Setup — Inciting incident (主角接受呼唤)",
        "beats": [
            "0-3s KICK  深夜空荡办公区，单一台式机屏幕亮起冷白光，键盘上摊开喝剩的咖啡纸杯",
            "3-7s TURN  屏幕弹出黑底白字对话框「想真正活着吗？」鼠标光标在 YES 按钮悬停",
            "7-11s PEAK 郑吒（24岁亚裔白领，黑色西装+灰蓝衬衫+黑短碎发）面部大特写，瞳孔放大失神",
            "11-15s HOOK 食指按下鼠标，画面快速 zoom-in 屏幕 → 暴白闪 → 镜头切黑/失重眩晕",
        ],
        "prompt": """A cinematic still frame from a modern psychological thriller: a young Asian office worker in a dark empty office at midnight, sitting before a glowing desktop monitor displaying a mysterious dialog box, dramatic cool blue tones with warm desk-lamp accent, photorealistic 35mm film grain, shallow depth of field, claustrophobic atmosphere. 现代心理惊悚电影级竖屏9:16，Unreal5路径追踪+实时光追+电影级Teal-Orange调色（深青冷暗影+暖橘高光，对比强烈，胶片颗粒）。

【0-3s KICK】深夜空荡的现代写字楼办公区，一格格隔间在背景陷入冷青阴影，只有一张工位上的台式电脑屏幕亮着冷白光投射在脸庞，桌面散落咖啡纸杯/笔记本/键盘，窗外是远景城市夜景虚化光点。镜头从屏幕侧后方慢推。

【3-7s TURN】电脑屏幕黑底白字弹出对话框：「Do you want to truly live? 想真正活着吗？」 中央两个按钮 YES 与 NO，鼠标光标缓慢悬停在 YES 上。镜头由屏幕切回桌前——郑吒（24 岁亚裔男青年，深灰短西装+灰蓝衬衫+黑色短碎发略乱+无框眼镜半遮眼帘，瞳孔扩张失神状），他静静凝视屏幕，背景虚化深青冷调办公空间。

【7-11s PEAK】镜头大特写郑吒右眼，瞳孔倒映出对话框 YES 字样，呼吸停顿一秒，喉结轻动一下，太阳穴一根青筋微跳。前景一缕台灯暖橘光斜照鼻梁。

【11-15s HOOK】食指缓缓按下鼠标左键，画面骤然 zoom-in 屏幕直至全白闪一帧，下一帧切到郑吒眼前一黑、身躯如失重般向后倾倒。最后一帧定格在他半睁瞳孔中残留的 YES 反光。

镜头语言: 慢推屏幕侧后 → 中近景对话框揭示 → 大特写眼神 → 第一视角白闪 → 大特写定格。
质感细节: 屏幕冷蓝白光+台灯暖橘光的混合冷暖对比、皮肤上微妙的鼻翼/嘴唇湿润高光、办公室浮尘飘动、35mm 胶片颗粒。
合规禁忌: 无任何字幕文字（除屏幕内对话框）、无血腥/性暗示、无屏幕外现实暴力。""",
    },
    {
        "ep_id": "ep02_cabin_threat",
        "title": "车厢·冷笑威胁",
        "scene_summary": "郑吒在高速行驶的密闭车厢醒来，被疤面冷笑黑发青年举着金属手枪威胁，旁边有 5 名昏迷者与外籍战术人员",
        "act": "Rising — Conflict escalates (主角直面危险)",
        "beats": [
            "0-3s KICK 高速车厢内部金属管道与冷凝水反射光带，郑吒从地板上猛弹身坐起",
            "3-7s TURN 镜头摇过郑吒视线：身边5名意识昏迷的乘客 + 远端外籍战术人员持长枪冷漠侧立",
            "7-11s PEAK 张杰（24-25岁亚裔男，黑发齐肩，脸部多道交错旧疤，军绿机能外套）冷笑抬眼、二指夹香烟",
            "11-15s HOOK 张杰瞬间弹起将一把银黑色金属道具手枪枪口塞入郑吒身旁小胖子嘴中，眼中杀意 frozen",
        ],
        "prompt": """A cinematic still frame from a modern cyberpunk thriller: a scarred-face young Asian man in tactical gear holding a stylish metallic sidearm prop, smoke drifting from his cigarette, inside a fast-moving train cabin, dark teal blue palette with warm red emergency lighting accents, photorealistic 35mm film grain, anamorphic lens, shallow depth of field, intense dramatic tension. 现代赛博惊悚电影级竖屏9:16，Unreal5路径追踪+实时光追+电影级Teal-Orange调色（深青冷暗影+暖橘/暖红高光，对比强烈，胶片颗粒）。

【0-3s KICK】高速行驶密闭车厢内部，金属管线纵横交错，顶部红色应急灯频闪一下一暗，地面薄薄一层冷凝水反射光带。车厢窗外水泥隧道高速流动冷青光带。

【3-7s TURN】郑吒（24 岁亚裔男青年，深灰西装略凌乱+灰蓝衬衫袖口卷到肘部+黑色短碎发，瞳孔大且充血，额头冷汗）从坚硬金属地板上猛地弹身坐起，环视四周——身边躺着 5 名意识昏迷男女，车厢另一端 10 余名外籍战术人员（黑色战术背心+长枪斜挂胸前+夜视镜推上额头）冷漠侧立，不与镜头交集。

【7-11s PEAK】镜头切对面座位，张杰（24-25 岁亚裔男青年，黑发齐肩稍乱半遮额，脸上多道由额到下颌斜向交错的狰狞暗红旧疤痕，深色高领+军绿色机能外套）右手二指夹着燃烧的香烟，缓缓抬起眼睛，瞳孔在应急红光下闪冷光，嘴角微挑出残酷冷笑。前景烟雾袅袅。

【11-15s HOOK】张杰像黑豹弹起，一只手按住身旁惊愕的小胖子（28 岁亚裔男，圆脸+灰运动外套），另一手将一把银黑色金属道具手枪枪口塞入小胖子嘴中——画面定格在张杰冷酷眼神与小胖子瞠目惊恐的瞬间，背景应急灯继续闪烁。

镜头语言: 车厢全景 → 中景跟拍郑吒坐起 → 第一视角扫视 → 张杰大特写抬眼 → 双人定格爆发瞬间。
质感细节: 冷青阴影 + 应急灯暖红补光，皮肤细节、疤痕表皮微突起、香烟散射粒子、金属道具枪身镜面反射。
合规禁忌: 画面不出现任何字幕文字/HUD/角色名浮窗；无血腥写实/性暗示；金属道具枪绝不展示朝头部开火或扣扳机；定格为戏剧"对峙"而非"伤害"。""",
    },
    {
        "ep_id": "ep03_arrive_door",
        "title": "到站·门将开启",
        "scene_summary": "戴眼镜女理性发问回去之路 → 马修·艾迪森短暂金光闪过被点名 → 车厢减速到站,巨型大门将开",
        "act": "Climax+Cliffhanger — Suspense before the unknown",
        "beats": [
            "0-3s KICK 车厢内戴眼镜女（25岁亚裔女，黑长直发束起+金属圆框镜+灰白衬衫）冷静推眼镜",
            "3-7s TURN 镜头切换到外籍战术队员中的非裔队长马修（35-40岁黑人，平头+战术装），全身被淡金色虚光环裹片刻",
            "7-11s PEAK 车厢减速金属摩擦声尖锐渐起，窗外水泥隧道流速变慢，应急灯频率慢下来",
            "11-15s HOOK 车厢稳停在工业地下站台，前方蜂窝六角金属大门冷蓝 LED 指示灯亮起，气压门嘶嘶将启",
        ],
        "prompt": """A cinematic still frame from a modern cyberpunk thriller: a dark industrial underground subway station with hexagonal metal door beginning to open, mercenary leader bathed in fading golden aura, professional Asian woman with round glasses adjusting them calmly inside a train cabin, dark teal blue palette with warm orange LED accents and a brief golden glow, photorealistic 35mm film grain, wide-angle composition, dense atmospheric depth, ominous anticipation. 现代赛博惊悚电影级竖屏9:16，Unreal5路径追踪+实时光追+电影级Teal-Orange调色，工业 sci-fi 美学。

【0-3s KICK】车厢内中近景，戴眼镜女孩（25 岁亚裔女青年，黑长直发束在脑后+金属边框圆眼镜+灰白衬衫袖口扣紧+深灰长裤）冷静抬手用中指轻推眼镜框，眼眸在冷青光下保持镇定光泽。她身旁的郑吒侧脸专注聆听。

【3-7s TURN】镜头快速摇向车厢另一端外籍战术队员中的非裔队长——马修·艾迪森（35-40 岁，平头黑发+黑色战术背心+战术腰带+军绿色 T 恤），他周身瞬间被一层淡金色微光环裹片刻，金光线条状从顶部向下流过他身体随即消散，他本人毫无察觉、面无表情仍冷峻地凝视前方。

【7-11s PEAK】车厢内金属摩擦发出尖锐渐起的减速声，车窗外水泥隧道高速流光带逐渐变慢，顶部应急灯频率从快变慢，气流哨声减弱。镜头从窗外缓推回车厢内地板上的金属感倒影。

【11-15s HOOK】车厢稳稳停在地下工业风钢制站台，巨型滑动门嘶嘶气压声开启一道缝，露出昏暗的工业地下走廊——远处一道蜂窝六角形封闭式大门在镜头远端发出冷蓝 LED 状态指示灯，门上 UMBRELLA 工业品牌符号轮廓虚化可见。画面定格在门缝那一线冷蓝光中。

镜头语言: 中近景眼镜女 → 快速摇向马修金光 → 隧道慢推 → 站台大景 → 大门冷蓝光定格。
质感细节: 冷青工业地下空间 + 暖橘 LED 状态灯 + 金光环短暂高光、金属地面镜面反射、轻微镜头眩光、远景冷蓝雾气、35mm 胶片颗粒。
合规禁忌: 画面无字幕文字/HUD/角色姓名浮窗；UMBRELLA 标识仅虚化轮廓；无血腥/性暗示。""",
    },
]
