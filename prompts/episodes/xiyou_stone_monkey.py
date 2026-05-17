"""西游记·石猴出世 Ch.1 三集 ~15s — R15 切换测试用例.

吴承恩《西游记》1592 公版IP,无版权风险。中国神话史诗最经典开场之一,
古风 3D 国漫审核宽松。

3 幕结构:
- ep01_immortal_stone:   花果山仙石 + 日月精华 + 仙石异变(铺垫)
- ep02_stone_cracks:     雷云汇聚 + 仙石爆裂 + 石蛋滚出(冲突)
- ep03_monkey_born:      石蛋碎裂 + 石猴诞生 + 金光冲霄 + 玉帝震惊(高潮+悬念)

每集 4-beat 节奏 (3-4s 一拍):
  Beat 1 (0-3s)  KICK    场景与异象钩子
  Beat 2 (3-7s)  TURN    戏剧推进
  Beat 3 (7-11s) PEAK    高潮揭示
  Beat 4 (11-15s) HOOK   悬念定格

工业级语言约束:
- 全集统一花果山(东胜神洲傲来国) + 仙石 + 石猴 视觉锚
- 古风3D国漫 (白蛇缘起60% + 哪吒之魔童降世30% + 大圣归来10%) 配方
- 中国神话美学:仙石青灰玉质感、日月金辉、雷电青蓝光、金光冲霄
- 悬念定格:每集末画面静止,留 0.5s 让观众预测下一集

CLIP-friendly bilingual: 开头 1-2 句英文电影感单帧描述 (CLIP encoder 99% 英文训练),
后接中文 4-beat 细节 (Skylark 中文理解力更好)。
"""

EPISODES: list[dict] = [
    {
        "ep_id": "ep01_immortal_stone",
        "title": "花果山·仙石异变",
        "scene_summary": "花果山顶仙石历日月精华亿万年,石面浮现金色纹路微震,大地灵气升腾,众小猴远观惊奇",
        "act": "Setup — Inciting incident",
        # R16 refine: 加强戏剧光照(golden hour rim light + lens flare)以提升 LAION+genre
        "prompt": """A breathtaking cinematic still frame from a Chinese mythological 3D animation: an ancient glowing immortal stone at the summit of a sacred mountain, dramatic golden-hour rim lighting with anamorphic lens flare, sun and moon trails leaving golden and silver ribbons across a time-lapse sky, swirling celestial mist, cool jade-green shadows with intense warm gold highlights, IMAX-grade composition, photorealistic 35mm film grain, mystical epic atmosphere. 古风3D国漫竖屏9:16,Unreal5路径追踪+cel-shading描边,中国神话史诗美学(白蛇缘起60%质感+哪吒之魔童降世30%+大圣归来10%)。

【0-3s KICK】东胜神洲傲来国花果山顶日出,云海翻涌金色霞光,顶峰一块巨型青玉色仙石(高约一丈半,圆形如蟠桃,表面布满古老纹路)静静矗立,周遭桃树梨树繁茂,几只灵猴在远处岩石上张望。镜头从云海低空缓推上山顶。

【3-7s TURN】时间快进:日月轮替光带横扫天空(金色日轨与银色月轨交替闪过,如时间长河凝缩),仙石周遭桃花谢了又开,梅花结实落霜,四季流转十数轮,镜头始终锁定仙石。

【7-11s PEAK】镜头慢推接近仙石,石面青玉表层浮现出蜿蜒金色纹路如脉络流动,纹路缓缓发出微光,大地灵气如薄雾从石脚升腾,周围空气微微扭曲。三只灵猴在画面前景剪影抬头张望。

【11-15s HOOK】仙石突然轻轻一震,石面金色纹路骤然亮起一格一格延伸如裂纹蛇行,远处天空隐有雷云汇聚的征兆。镜头定格在仙石表面金色纹路与背景蛛丝雷光的对比瞬间。

镜头语言: 云海低空慢推 → 时间流逝长镜 → 仙石近景金纹特写 → 仙石全景+雷云定格。
质感细节: 仙石青玉光泽、表面苔藓与古老风化纹理、日月光带的粒子流光、灵气薄雾散射、cel-shading 描边、35mm 胶片颗粒。
合规禁忌: 画面无任何字幕文字、无血腥/惊吓特写。""",
    },
    {
        "ep_id": "ep02_stone_cracks",
        "title": "雷云·仙石爆裂",
        "scene_summary": "雷云聚集天暗,巨雷劈中仙石,仙石轰然爆裂飞溅,一颗发光石蛋滚出,众猴惊散后回头张望",
        "act": "Rising — Conflict escalates",
        "prompt": """A cinematic still frame from a Chinese mythological 3D animation: lightning striking an ancient immortal stone at a mountain peak, the stone exploding with golden light shards flying outward, a glowing stone egg emerging from the debris, dark stormy sky with electric blue lightning and warm golden inner light, photorealistic 35mm film grain, epic dramatic moment. 古风3D国漫竖屏9:16,Unreal5路径追踪+实时光追+电影级冷蓝雷电+暖金内光对比,胶片颗粒。

【0-3s KICK】花果山顶雷云迅速汇聚,天空由金光转为铅灰再到深紫黑,远处雷光如蛇形游走云层间,风起卷动桃花花瓣狂舞。镜头从仙石仰拍天空。

【3-7s TURN】一道巨型青蓝雷电从云中直劈仙石,雷光与仙石金纹相撞瞬间发出耀眼白光,声波震散云层。镜头快剪:雷劈瞬间→白光→烟尘弥漫的仙石位置。

【7-11s PEAK】烟尘逐渐散开,镜头慢推:仙石中央崩裂成数块巨型碎片向外飞溅(慢动作,碎片旋转中带尾迹光),裸露出石芯里一颗如蟠桃大小、表面光滑的青玉色仙石蛋,蛋身散发柔和金光。

【11-15s HOOK】仙石蛋滚下山顶斜坡(慢速),停在一片青草地上,蛋身表面金色裂纹蛇行蔓延,周围十余只灵猴从树丛中探头张望,远处天边乌云开始散去露出一线金光。镜头定格在石蛋表面裂纹与众猴惊愕表情的画面对比。

镜头语言: 仰拍雷云汇聚 → 雷电劈中爆白 → 慢动作碎片飞溅 → 仙石蛋特写 → 群猴围观定格。
质感细节: 雷电青蓝高光、烟尘粒子散射、仙石碎片旋转拖尾、蛋面金纹流光、众猴毛发风动、cel-shading 描边、35mm 胶片颗粒。
合规禁忌: 无字幕文字、无血腥写实、雷电仅为戏剧效果不写惊吓特写。""",
    },
    {
        "ep_id": "ep03_monkey_born",
        "title": "石猴诞生·金光冲霄",
        "scene_summary": "石蛋彻底裂开,小石猴蜷缩睁眼,双目射出金光直冲云霄,惊动天庭,玉帝大殿震动惊视,众猴跪拜",
        "act": "Climax+Cliffhanger — Cosmic awakening",
        # R17 refine: 加 IMAX-grade composition + anamorphic flare + god rays 提升 LAION+CLIP
        "prompt": """A breathtaking IMAX-grade cinematic still frame from a Chinese mythological 3D animation epic: a newborn stone monkey emerging from a cracked celestial egg, two intense beams of golden god-ray light shooting straight from its eyes into the heavens piercing thick storm clouds, anamorphic lens flare and volumetric god rays, surrounding monkeys bowing in awe, distant celestial palace silhouette trembling in cosmic resonance, cool jade and intense gold cosmic palette, masterful composition, photorealistic 35mm film grain, divine awakening atmosphere, professional cinematography. 古风3D国漫竖屏9:16,中国神话史诗美学,Unreal5路径追踪+实时光追+电影级金光高对比+体积光,胶片颗粒。

【0-3s KICK】仙石蛋表面金色裂纹蔓延加速,蛋身轻轻颤动,众猴屏息观望。镜头特写裂纹一道道扩大,蛋壳碎屑零星掉落。

【3-7s TURN】仙石蛋"啪"地一声彻底裂开,蛋壳如莲花瓣向外翻开,内里露出一只蜷缩的小石猴(高约两尺,青灰玉色皮肤,毛发如石色细致雕刻,小小的脸庞紧闭双眼)。镜头慢推接近小石猴。

【7-11s PEAK】小石猴缓缓睁开双眼——双目瞬间射出两道刺目的金色光柱,直冲云霄,穿透云层,金光在天空划出两道笔直光柱,云层翻涌如惊涛,镜头跟随金光垂直上升至云端。

【11-15s HOOK】镜头切换至天庭凌霄宝殿(远景剪影,云海之上的金色宫殿群),殿内金阶之上玉帝(背影,黄龙袍剪影)猛然起身,大殿中明珠摇晃光影颤动。镜头切回花果山:小石猴稳稳站立在仙石碎片中央,金光渐收为眼中两点星辉,众猴在前景跪拜剪影,远处群山在金光中显出轮廓。画面定格在石猴目光与天庭剪影的视线对望瞬间。

镜头语言: 蛋壳裂纹特写 → 蛋开莲花瓣 → 石猴慢推中景 → 双目金光垂直上升 → 天庭剪影震动 → 石猴站立群猴跪拜定格。
质感细节: 仙石蛋壳碎屑、石猴青玉皮肤雕刻感、金光粒子高强对比、云海翻涌、凌霄宝殿金色宫殿群、众猴跪拜剪影、cel-shading 描边、35mm 胶片颗粒。
合规禁忌: 无字幕文字、无血腥/恐怖特写、玉帝剪影仅为戏剧悬念不写正面神像。""",
    },
]
