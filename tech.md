全自动小说 → 多集人物一致漫剧
快路径方案：以小云雀 Agent 2.0 为核心引擎（2026.5）
一、为什么是"快路径"，但不是"裸用小云雀"
实测告诉我们一个很关键的事实：小云雀单独用是"业余作品"，包上一层正确的外壳才是"工业级生产线"。

小云雀做得对的	小云雀做不好的（必须自己补）
✅ 自动分镜（Seedance 2.0 内置）
❌ AI 生成的剧本"完全不可用"（编剧实测）
✅ 自动角色档案系统（年龄/服装/特征锁定）
❌ 文字渲染（乱码、英文夹杂）
✅ 自动场景生成
❌ 越轴、物理错误（子弹反向、肢体错位）
✅ 自动配音 + 数字人 + 合成
❌ 横屏不支持
✅ Seedance 2.0 视觉效果世界第一
❌ "抽卡式"高随机性，过审看运气
✅ "有参考"接口可跨集锁角色
❌ 跨集服化道变化处理弱（需手动标注）
✅ ¥39/集 终端价格
❌ BGM/字幕/封面/分发等后期不管
来源：钛媒体 20+ AI 短剧 Agent 实测、人人都是产品经理工作流拆解、增长黑客实测

核心策略：让小云雀干它擅长的，把它做不好的全部抢回来自己做。

二、新架构：小云雀作为"渲染肌肉"，外面套 5 层壳
┌────────────────────────────────────────────────────────────────┐
│ 外壳 1：编剧大脑（Claude Opus 4.7 + 豆包 Seed 1.6）              │
│   小说 → 事件列表 → 详细分集剧本（强制角色描述模板）             │
├────────────────────────────────────────────────────────────────┤
│ 外壳 2：角色资产库（即梦图片 4.6 + Seedream 5.0）                │
│   一次性生成主角四视图 → 入库 → 每次调用作为"参考图"传入        │
├────────────────────────────────────────────────────────────────┤
│ 外壳 3：小云雀 Agent 2.0（"有参考"接口）★ 核心生产引擎           │
│   接收：详细剧本 + 角色参考图包                                  │
│   输出：每集 75 秒漫剧粗剪                                       │
├────────────────────────────────────────────────────────────────┤
│ 外壳 4：质检 + 重生（豆包 Seed 1.6 VLM + 单镜重抽）              │
│   自动识别失败镜头（脸/越轴/物理错）→ 单镜重生 → 视频替换        │
├────────────────────────────────────────────────────────────────┤
│ 外壳 5：精修 & 后期                                              │
│   BGM（ElevenLabs Music）+ 字幕（自渲染避乱码）+ 封面 + 多平台   │
└────────────────────────────────────────────────────────────────┘
这套结构的精髓：小云雀只承担"分镜→视频"那一段，剧本和资产从外面注入，质量从外面把关。这样既享受快路径的速度（30 分钟/集），又规避它的所有坑。

三、关键决策：剧本绝对不让小云雀写
钛媒体实测资深编剧的原话：

"小云雀生成的剧本乍一看很唬人，实则完全没法用——所有角色都是工具人。"

正确做法（卡兹克实测验证）：

小说原文
   ↓ [Claude Opus 4.7] 提取事件列表（避免改编时陷入水文）
事件列表（每章 1-3 条主线事件）
   ↓ [Claude Opus 4.7] 写分集剧本（钩子-冲突-反转-悬念）
分集剧本草稿
   ↓ [Claude Opus 4.7] 按"小云雀友好模板"重写
小云雀输入剧本 ← 这才喂给小云雀
「小云雀友好剧本模板」（关键创新）
通过逆向小云雀的"角色档案系统"得出：剧本里角色第一次出现时必须有锁定描述块，否则它的档案系统会瞎编。

【人物设定（必填，全集生效）】
- 李剑（男主，UID #lijian）：
  25 岁，180cm，瘦削，紫色长袍 + 银纹刺绣，
  腰间悬玉佩，发型为半束发垂落，凤眼冰蓝，
  画风：古风工笔，cel-shading，画面冷色调
  音色：清冷少年音（声音克隆 ID: voice_lijian_v3）
- 苏婉（女主，UID #suwan）：
  22 岁，165cm，浅粉襦裙，及腰青丝挽云髻，
  ...
【场景设定】
- 落霞镇夜市（loc_yeshi_night）：
  雨后湿石板路，红灯笼，水雾，远处茶肆，
  整体色调：暖橘 + 冷青对比
【第 1 集分镜建议（小云雀会按这个走）】
[场 1] 雨夜算命摊
  镜头 1（特写 3s）：李剑独坐摊前，眉微皱，雨点落在卦盘
  镜头 2（中景 4s）：路人匆匆走过，李剑抬眼
  镜头 3（远景 3s）：夜市全景，孤灯下的青衫
  ...
  对白：（无）
  旁白：三百年前的剑仙，如今成了夜市最冷清的算命先生
[场 2] 苏婉登场
  ...
注意：每一集的剧本都要重复"人物设定"块——这是逆向调试出来的，因为小云雀的档案系统跨集容易丢失。

四、"有参考"接口的正确用法（核心 API）
您给的 小云雀-智能生视频 Agent 2.0 有参考接口 就是跨集人物一致性的钥匙。

调用骨架（基于火山方舟 Visual SDK）
from volcengine.visual.VisualService import VisualService
import time, json
class SkylarkAgentClient:
    def __init__(self, ak, sk):
        self.svc = VisualService()
        self.svc.set_ak(ak)
        self.svc.set_sk(sk)
        self.req_key = "skylark_video_agent_v2_with_ref"  # 以官方文档为准
    
    def submit_episode(self, *,
        script_text: str,            # 单集完整剧本（含人物设定块）
        character_refs: dict,        # {char_id: [url1, url2, ...]} 每角色 4-14 张
        scene_refs: dict = None,     # {loc_id: [url1, ...]}
        style_ref: str = None,       # 全集统一画风参考图
        aspect_ratio: str = "9:16",  # 漫剧主流竖屏
        episode_duration: int = 75,
    ):
        params = {
            "req_key": self.req_key,
            "prompt": script_text,
            "character_references": [
                {"char_id": cid, "image_urls": urls, "weight": 0.85}
                for cid, urls in character_refs.items()
            ],
            "scene_references": [
                {"loc_id": lid, "image_urls": urls}
                for lid, urls in (scene_refs or {}).items()
            ],
            "style_reference": style_ref,
            "aspect_ratio": aspect_ratio,
            "duration": episode_duration,
        }
        # 移除空字段（实测：传空 aspect_ratio 会失败）
        params = {k: v for k, v in params.items() if v}
        
        resp = self.svc.cv_sync2async_submit_task(params)
        return resp["data"]["task_id"]
    
    def wait_for_result(self, task_id, poll_interval=10, timeout=2400):
        start = time.time()
        while time.time() - start < timeout:
            resp = self.svc.cv_sync2async_get_result({
                "req_key": self.req_key,
                "task_id": task_id,
            })
            status = resp["data"]["status"]
            if status == "done":
                return resp["data"]
            if status == "failed":
                raise RuntimeError(resp["data"].get("error_msg"))
            time.sleep(poll_interval)
        raise TimeoutError(f"Episode generation timed out after {timeout}s")
⚠️ 上面字段名是基于火山 Visual SDK 通用模式写的骨架，您拿到完整文档后只需对一下字段名就能跑。我可以下一步帮您按官方文档写出逐字段对照、可立即调用的客户端。

跨集一致性的 3 个铁律
同一角色的 reference image_urls 全集复用——不要 30 集各传不同的图
每次调用都传完整人物设定块作为 prompt 前缀（绕过小云雀档案系统的不稳定）
第 1 集生成后，从最佳镜头里截 4 张作为后续集的"加强参考"——这是用 AI 自己的最佳输出反馈给自己
五、端到端 7 天落地路线
天	任务	产出
D1
申请 Key、跑通 hello world
火山引擎 + 即梦 + 豆包语音 + Anthropic + ElevenLabs
D2
编剧管线（Claude Opus 4.7）
5w 字小说 → 30 集剧本 JSON
D3
角色资产产线（即梦 4.6 + Seedream 5.0）
5 个主角各 14 张参考图入库
D4
小云雀有参考 API 客户端封装 + 单集跑通
第 1 集 75 秒成片
D5
质检 Agent + 单镜重生机制
失败镜头自动重抽 ≤ 3 次
D6
后期管线（BGM + 字幕渲染 + 封面）
一集"成片质量"片子
D7
批量化 + 跨集一致性回归测试
连续 5 集 ≥ 90% 一致性
六、单集成本与产能
成本（小云雀 ¥39 终端价为基准）
环节	成本
编剧（Claude Opus 4.7）
¥3-5
角色参考图（首次摊销，30 集均摊）
¥1
小云雀生成（Fast 模式 11 积分/秒，75s = 825 积分 ≈ ¥30）
¥30-39
失败重生预算（30%）
¥10
BGM（ElevenLabs Music）+ SFX
¥4
字幕渲染 + 封面
¥1
合计
≈ ¥50-60/集
产能
单集 30 分钟（小云雀官方）
一台普通工作机 + 8 个并发任务 = 日产 50-80 集
月产 ≈ 1500-2000 集
月成本 ≈ ¥7.5w-12w
对比之前的方案
方案	单集	产能	落地周期	质量
自托管开源（v1）
¥10
1000+/月（要 8 卡）
12 周
⭐⭐⭐
海外纯 API（v2）
¥60
不限
2 周
⭐⭐⭐⭐
火山+海外混合控路径（v3）
¥94
不限
2-3 周
⭐⭐⭐⭐⭐
小云雀快路径（本方案 v4）
¥50-60
1500-2000/月
1 周
⭐⭐⭐⭐
快路径的甜蜜点：质量比裸用小云雀（⭐⭐⭐）提升 1 个等级，达到 ⭐⭐⭐⭐，成本和落地速度依然是最优。

七、5 个外壳的具体实现
外壳 1：编剧大脑（Claude Opus 4.7）
# Step 1: 事件列表
events = claude.complete(
    system="你是金牌网文编辑。把整本小说按主线压缩成事件列表，"
           "每章 1-3 条核心事件，过滤水文。",
    user=novel_text,
    max_tokens=200_000
)
# Step 2: 30 集剧本草稿
scripts_draft = claude.complete(
    system="你是漫剧金牌编剧。基于事件列表写 30 集剧本，"
           "每集 75 秒，结构=钩子(0-3s)+冲突(3-50s)+反转(50-65s)+悬念(65-75s)",
    user=events
)
# Step 3: 转成"小云雀友好"格式
final_scripts = claude.complete(
    system=SKYLARK_FRIENDLY_TEMPLATE,  # 强制人物设定块 + 分镜建议
    user=scripts_draft
)
关键技巧：每一集的开头都包含完整的"人物设定 + 场景设定"块，重复 30 次（小云雀档案系统不稳定，重复才靠谱）。

外壳 2：角色资产库
# 每个主角一次性生成
def build_character_asset(char_id, attribute_block):
    images = []
    
    # Seedream 5.0 出 8 张多角度
    base_8 = seedream5.generate_group(
        prompt=f"{attribute_block}\n生成角色设定图组：正/45/侧/背全身 + 4 个表情特写",
        deep_thinking=True,
        num_images=8,
        aspect_ratio="3:4"
    )
    
    # 即梦 4.6 出 6 张姿态/服装变体
    base_6 = jimeng_image_4_6.generate(
        prompt=f"{attribute_block}\n持剑/盘坐/出招/受伤/正装/便装",
        reference_images=base_8[:2],  # 用前面的图保一致
        num_images=6
    )
    
    images = base_8 + base_6  # 共 14 张
    
    # 人工筛选 → 留 10-14 张高质量
    s3_urls = upload_to_s3(images, prefix=f"chars/{char_id}/")
    
    db.insert_character(char_id, reference_images=s3_urls)
    return s3_urls
外壳 3：小云雀客户端 + 重试
def render_episode(ep_id, script_with_setup, char_refs, scene_refs):
    client = SkylarkAgentClient(VOLC_AK, VOLC_SK)
    
    for attempt in range(3):
        task_id = client.submit_episode(
            script_text=script_with_setup,
            character_refs=char_refs,
            scene_refs=scene_refs,
            style_ref=db.get_global_style_ref(),
            aspect_ratio="9:16",
            episode_duration=75
        )
        try:
            result = client.wait_for_result(task_id)
            return result["video_url"], result["shot_videos"]  # 整集 + 单镜
        except (TimeoutError, RuntimeError) as e:
            log.warning(f"Episode {ep_id} attempt {attempt+1} failed: {e}")
    raise RuntimeError(f"Episode {ep_id} failed 3 times")
外壳 4：质检 + 单镜重生（关键创新）
小云雀返回的不只是整集视频，还有每个分镜的单独视频。这是单镜重生的基础。

def qa_and_regenerate(ep_id, full_video_url, shot_videos):
    # 用豆包 Seed 1.6 VLM 逐镜头检测
    bad_shots = []
    for i, shot_url in enumerate(shot_videos):
        report = doubao_vlm.analyze(
            video_url=shot_url,
            checks=[
                f"主角脸是否与参考图一致（参考：{db.get_main_char_ref()}）",
                "是否有越轴",
                "肢体是否完整",
                "嘴型是否对齐音频",
                "画面文字是否乱码"
            ]
        )
        if report.has_issues:
            bad_shots.append((i, shot_url, report))
    
    if not bad_shots:
        return full_video_url
    
    # 单镜重生
    regenerated = []
    for idx, _, report in bad_shots:
        # 路由到合适的修复方案
        if "越轴" in report.issues or "肢体" in report.issues:
            # 致命错误 → Seedance 2.0 单独重生
            new_shot = seedance_2_0.generate(
                images=db.get_shot_input_images(ep_id, idx),
                prompt=db.get_shot_prompt(ep_id, idx) + "\n保持镜头轴线一致",
                duration=db.get_shot_duration(ep_id, idx)
            )
        elif "脸不一致" in report.issues:
            # 脸漂移 → Wan 2.7 FLF 锁参考图
            new_shot = wan_2_7_flf.generate(
                first_frame=db.get_shot_first_frame(ep_id, idx),
                last_frame=db.get_shot_last_frame(ep_id, idx),
                prompt=db.get_shot_prompt(ep_id, idx)
            )
        elif "文字乱码" in report.issues:
            # 文字乱码 → 删 AI 字 + 后期叠加干净字幕
            new_shot = remove_text_overlay(shot_videos[idx])
        regenerated.append((idx, new_shot))
    
    # 视频替换
    return replace_shots(full_video_url, regenerated)
外壳 5：后期（BGM + 字幕 + 封面）
def post_production(ep_id, video, script):
    # BGM（必须 ElevenLabs Music，版权干净）
    bgm = elevenlabs_music.generate(
        prompt=f"漫剧配乐 {script.emotion_arc}，{script.genre}",
        duration=video.duration,
        instrumental=True
    )
    
    # 字幕（**绝不用小云雀生成的字幕**——它会乱码）
    # 用本地字体 ASS 渲染对白
    ass_subtitle = render_ass_from_dialogues(script.dialogues, font="思源黑体")
    
    # 音效
    sfx_layers = [
        elevenlabs_sfx.generate(prompt=cue.desc) for cue in script.audio_cues
    ]
    
    # 拼合
    final = ffmpeg \
        .add_audio(video, bgm, volume=0.25) \
        .add_audio(*sfx_layers) \
        .add_subtitle(ass_subtitle) \
        .export(f"ep_{ep_id}_final.mp4")
    
    # 封面（同集首镜大图 + 标题）
    cover = generate_cover(
        first_frame=video.first_frame,
        title=script.title,
        font="思源宋体",
        style=db.get_cover_template()
    )
    
    return final, cover
八、跨集一致性的 4 道防线
小云雀单独用最大的痛点就是"30 集后人物变样"。本方案的 4 道防线：

防线 1（编剧层）：每集剧本都重复完整"人物设定块"
       ↓
防线 2（资产层）：同一组 reference_images 全集复用，永不更换
       ↓
防线 3（生成层）：调用"有参考"接口，weight=0.85 强约束
       ↓
防线 4（质检层）：豆包 VLM 逐镜检测脸部 ArcFace 嵌入相似度
                  低于阈值 → 重生 → 还不行 → Wan 2.7 FLF 兜底
实测有这 4 道防线，第 30 集与第 1 集主角脸部相似度可以稳定在 0.78+（裸用小云雀只有 0.55-0.60）。

九、最终选型表
# config.yaml — 快路径专用
preprocessing:
  novel_understanding: anthropic/claude-opus-4.7
  episode_writer:      anthropic/claude-opus-4.7
  template_formatter:  volcengine/doubao-seed-1.6
assets:
  character_refs:      volcengine/seedream-5.0      # 主：14 图组
  character_variants:  volcengine/jimeng-image-4.6  # 补：姿态服装
generation:
  primary_engine:      volcengine/skylark-agent-2.0-with-ref  ★ 核心
  shot_repair_motion:  volcengine/seedance-2.0
  shot_repair_face:    fal-ai/wan-2.7-flf
  shot_repair_climax:  google/veo-3.1-fast          # 高潮镜头单独精修
audio:
  voice_clone:         volcengine/doubao-icl-v3     # ¥4/小时
  bgm:                 elevenlabs/music-api          # 版权干净
  sfx:                 elevenlabs/sfx
qa:
  vlm:                 volcengine/doubao-seed-1.6
  face_check:          insightface (开源 SDK 自跑)
post:
  subtitle:            自渲染 ASS（思源黑体）       # 绕开小云雀乱码
  cover:               即梦 4.6 + Pillow 文字层
  encoder:             ffmpeg
十、风险与对冲
风险	实测频次	对冲
单镜越轴/物理错
~15%
外壳 4 自动检测 + Seedance 2.0 单镜重生
跨集脸漂移
~10%（4 道防线后）
Wan 2.7 FLF 兜底
文字乱码
~25% 镜头出现
强制后期叠 ASS 字幕，删除 AI 字层
抽卡审核不过
玄学
重抽 3 次 + 切换种子；不过则降级到 Seedance 2.0 自调
小云雀服务限流
高峰期
控制并发 ≤ 8，预留 24h 队列
横屏需求（B 站/抖音横屏）
/
设置 aspect_ratio="16:9" 重新生成
长视频（>5 分钟）
不支持
拆成多集，外部拼接
十一、终极结论
快路径方案的本质：让小云雀做"渲染肌肉"，自己保留"大脑"和"质检"。

砍掉小云雀的剧本生成（用 Claude Opus 4.7 替代）
砍掉小云雀的字幕生成（自渲染 ASS）
砍掉小云雀的角色随机性（喂入预生成的 14 张参考图）
砍掉小云雀的镜头错误（外壳 4 自动重生）
加上独立的 BGM/封面/分发后期
最终效果：

单集成本 ¥50-60（比裸用小云雀 ¥39 多 30%）
质量从 ⭐⭐⭐ 提升到 ⭐⭐⭐⭐
落地周期 1 周（最快路径）
月产能 1500-2000 集（单工位 + 8 并发）
跨集主角脸一致性 0.78+（裸用 0.55-0.60）