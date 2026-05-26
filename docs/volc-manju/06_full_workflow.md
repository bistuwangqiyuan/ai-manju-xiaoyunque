# 小云雀-短剧漫剧Agent - 全流程调用示例

> source: https://www.volcengine.com/docs/85621/2459788?lang=zh

## 4 阶段顺序总览

```
[1] 剧本解析  (pippit_shortplay_cvtob_script_analysis)
    ┌── submit  → task_id
    └── poll    → assets_id, thread_id, EpisodeID[]

[2] 图片生成  (pippit_shortplay_cvtob_material_design)        每个剧本一次
    ┌── submit (assets_id, thread_id, run_id) → task_id
    └── poll → character/scene image URLs

[3] 单集分镜视频生成  (pippit_shortplay_cvtob_video_generate_fast720p)  每集一次
    ┌── submit (assets_id, thread_id, episode_id, run_id) → task_id
    └── poll → 每个 Shot.VideoURL

[4] 单集视频合成  (pippit_shortplay_cvtob_video_compose_fast720p)  每集一次
    ┌── submit (assets_id, thread_id, episode_id) → task_id
    └── poll → final_video_url + final_video_cover_url
```

## 关键约束 (官方明示)

### 图片生成

- 遍历 `character_detail` 与 `scene_detail`,若任意 `ExpectRenderImageCount != ActualRenderImageCount` 即该资源有失败
- 失败的图**不支持重传**,需重新走整集流程
- 最常见失败原因: 审核未通过 (敏感身份/职业/不合规人物特征)

### 视频生成

- 必须遍历 `ShotStatusMap` 检查所有分镜 Status,**任意分镜未完成即无法调用视频合成接口**
- 部分分镜失败时的 fallback: 保存失败分镜 `Description` + 图片资源,前往第三方工具重生成失败片段,然后下载所有成功片段拼接

## 完整流水线伪代码 (Python)

```python
from src.shell3_skylark_engine.manju_agent_client import ManjuAgentClient

client = ManjuAgentClient()
# 高层 API: 一行搞定 (内部串行 4 阶段)
result = client.render_script(
    novel_text=open("script.txt", encoding="utf-8").read(),
    ep_id="job-001",
    style="real",           # 或 "2d" / "3d", 或自定义 "2D, 国风, 平涂"
    ratio="9:16",
    file_type="txt",
)
for ep in result.episodes:
    print(ep.episode_no, ep.archived_path, ep.cover_url)

# 低层 API: 分阶段控制 (适合测试/重试/特殊场景)
analysis = client.analyze_script(
    file_url="https://x.tos.com/script.docx",
    visual_style="2D, 国风, 平涂",
    video_ratio="9:16",
    file_type="docx",
)
client.generate_materials(analysis["assets_id"], analysis["thread_id"])
for ep_id in analysis["episode_ids"]:
    client.generate_episode_videos(
        analysis["assets_id"], analysis["thread_id"], ep_id, fast=True,
    )
    mp4 = client.compose_episode_video(
        analysis["assets_id"], analysis["thread_id"], ep_id, fast=True,
    )
    print(ep_id, mp4["final_video_url"])
```

## 时间预算

- 剧本解析: 4 min
- 图片生成: 10 min (无论几集都是 1 次)
- 视频生成: 7 min / 集
- 视频合成: 1 min / 集

10 集的全流程约 4 + 10 + 10×(7+1) = **约 95 分钟**

## 鉴权 (V4-HMAC-SHA256)

所有 4 个接口共用一套签名:

```
POST https://visual.volcengineapi.com/?Action=CVSync2AsyncSubmitTask&Version=2022-08-31
POST https://visual.volcengineapi.com/?Action=CVSync2AsyncGetResult&Version=2022-08-31

Header (V4 签名):
  Host: visual.volcengineapi.com
  X-Date: 20260526T093000Z
  Authorization: HMAC-SHA256 Credential=<AK>/20260526/cn-north-1/cv/request, SignedHeaders=..., Signature=...
  Content-Type: application/json
```

签名实现见 `src/common/volc_signer.py` 的 `sign_request()`.
