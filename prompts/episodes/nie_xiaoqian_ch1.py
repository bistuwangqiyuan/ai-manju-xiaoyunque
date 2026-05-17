"""聊斋·聂小倩 Ch.1 三集 ~15s — R13 切换测试用例.

公版IP(蒲松龄 1715),无版权风险。古风3D国漫，审核宽松,Skylark 历史验证 R3-R8 在
此类内容上稳定通过。

3 集结构:
- ep01_lanruosi_moon: 兰若寺月夜 + 宁采臣推门 + 聂小倩朱砂痣特写 + 铜镜空灵(15s)
- ep02_three_knocks:  三更叩门 + 黄金化尘 + 鬼气暴露 + 烛火忽暗(15s)
- ep03_yan_chixia:     燕赤霞登场 + 革囊苍白手影 + 青蓝剑光 + 收势余光(15s)

三大原创锁定符号 (跨集识别):
- 聂小倩眉间一点朱砂痣
- 革囊中前剑客之魂的苍白手(燕赤霞腰间)
- 月夜冷青 + 月白 + 朱砂红 色调
"""

EPISODES: list[dict] = [
    {
        "ep_id": "ep01_lanruosi_moon",
        "title": "兰若寺·月夜邂逅",
        "scene_summary": "宁采臣月夜推开兰若寺破门进入,廊柱后聂小倩白衣回眸,镜头大特写朱砂痣,铜镜前空灵倒影",
        "act": "Setup",
        "prompt": """A cinematic still frame from a Chinese ancient-style 3D animation: a young Asian scholar in pale gray-blue robe entering a moonlit abandoned temple, a beautiful young woman in white silk garment with a vermillion red dot between her eyebrows standing under moonlight, ethereal cool blue palette with warm temple-bell brass accents, photorealistic 35mm film grain, shallow depth of field, mystical mood. 古风3D国漫竖屏9:16,Unreal5路径追踪+cel-shading描边,冷青+月白+朱砂配色(白蛇缘起60%质感+狐妖月红仙气30%+雾山五行10%)。

【0-3s KICK】兰若寺荒废山门月夜,蝙蝠掠过破匾,月光透过断瓦洒下,竹影摇曳如鬼魅,神台空寂。镜头从山门外缓推。

【3-7s TURN】宁采臣(24岁亚裔男青年,浅灰青长袍+黑发束髻+背书箧+手持小灯笼)推开斑驳厚重木门入院,脚踏落叶碎瓦发出轻响,镜头跟拍其背影至殿前回身。

【7-11s PEAK】廊柱后白衣身影闪过,宁采臣举烛趋近一柱,回身时聂小倩(亚裔年轻女子,白衣襦裙浅粉缎带,黑长发披肩,眉间一点朱砂痣圆点直径3mm清晰可见,杏眼浅蓝灰微光,白玉镯半透)立于月光下缓缓回首微笑。镜头大特写朱砂痣。

【11-15s HOOK】聂小倩转身走向供桌铜镜,镜面只显空灵倒影(虚化),宁采臣怔在原地,烛火忽明忽暗,定格在镜中倒影与现实人物的不一致瞬间。

镜头语言: 山门慢推 → 中景跟拍宁采臣 → 廊柱大特写 → 朱砂痣极特写 → 铜镜倒影定格。
质感细节: 月光泛冷青蓝、白玉镯半透质感、烛火暖橘点缀、发丝月光散射、35mm 胶片颗粒、cel-shading 描边。
合规禁忌: 无任何字幕文字、无血腥/性暗示、无恐怖跳吓特写。""",
    },
    {
        "ep_id": "ep02_three_knocks",
        "title": "三更叩门·黄金化尘",
        "scene_summary": "宁采臣东侧回廊抄经,三更聂小倩叩门入,袖中黄金触桌化作光尘,烛火忽暗",
        "act": "Rising",
        "prompt": """A cinematic still frame from a Chinese ancient-style 3D animation: a young Asian scholar in pale robe writing at a wooden desk by candlelight, a young woman in white silk garment standing at the open temple door, gold dust dispersing softly in the air, ethereal cool blue palette with warm candlelight, photorealistic 35mm film grain, mysterious atmosphere. 古风3D国漫竖屏9:16,白蛇缘起质感60%+狐妖月红仙气30%+雾山撞色10%。

【0-3s KICK】兰若东侧回廊深夜烛火摇曳,宁采臣端坐木案前抄经,毛笔停在"鬼"字一捺,纸面墨痕未干,案旁砚台微泛光。

【3-7s TURN】三更钟声后木门轻叩,聂小倩(白衣襦裙+眉间朱砂痣+黑长发披肩)立于门外月光下,左肩袖口一缕淡淡灰白雾气(虚化烟雾,不写血腥)。宁采臣开门让入。

【7-11s PEAK】二人对坐烛光下,聂小倩袖中取出黄金一锭轻放案上,金锭表面浮雕花纹清晰可见,镜头特写金锭与白皙手指的对比。

【11-15s HOOK】黄金触桌瞬间化作柔和金色光尘四散飞舞(粒子特效,不写白骨特写),宁采臣震惊起身,烛火忽地一暗,画面定格在金尘飘散与二人惊愕表情的对比。

镜头语言: 中景烛火 → 门外正面 → 室内正反打 → 金锭特写 → 金尘飘散定格。
质感细节: 烛火暖橘 + 月光冷青、白衣丝绸质感、金尘粒子散射、35mm 胶片颗粒、cel-shading 描边。
合规禁忌: 无字幕文字、无血腥/性暗示、无白骨特写、定格为"灵异显现"而非"惊吓"。""",
    },
    {
        "ep_id": "ep03_yan_chixia",
        "title": "燕赤霞·青蓝剑光",
        "scene_summary": "客栈榻上友人昏迷,燕赤霞登场抚剑,夜空青蓝剑光掠过,远处院落剪影",
        "act": "Climax+Cliffhanger",
        "prompt": """A cinematic still frame from a Chinese ancient-style 3D animation: a serious Asian swordsman in dark navy Taoist robe with a leather pouch at his waist, blue-cyan sword light streaking across a night sky, a far silhouette of an ancient courtyard, cool teal-blue palette with warm candlelight and bright sword glow, photorealistic 35mm film grain, mystical action mood. 古风3D国漫竖屏9:16,雨后天青光与烛火暖橘对比,剑光青蓝。

【0-3s KICK】客栈房间内榻上友人(亚裔男青年,常服)昏迷的写意镜头(侧光剪影、不写血腥创口),榻边一盏油灯将熄。

【3-7s TURN】燕赤霞(35-40岁亚裔男,深墨色长道袍+暗红披风+黑发束髻+右眉骨浅疤+腰间褐色革囊与短剑鞘可见,革囊中隐约可见一只苍白手掌轮廓)缓步入室,缓缓抚剑鞘,目光凝重。

【7-11s PEAK】燕赤霞推窗而出,夜空一道青蓝剑光自高处划过,白练状阴影向远处方向飞去,镜头跟随剑光轨迹。

【11-15s HOOK】剑光远去方向露出远处院落黑色剪影,镜头切回燕赤霞剑收回鞘、眼角余光投向兰若方向、嘴角微动欲言又止的瞬间,定格于眼角大特写。

镜头语言: 中景榻上 → 中景燕赤霞入室 → 中景推窗 → 广角剑光夜空 → 剪影远景 → 眼角大特写定格。
质感细节: 夜空冷蓝深蓝、剑光青蓝高对比、油灯暖橘点缀、革囊苍白手轮廓影、35mm 胶片颗粒、cel-shading 描边。
合规禁忌: 无字幕文字、无血腥/性暗示、不写创口特写、剑光仅为道具效果。""",
    },
]
