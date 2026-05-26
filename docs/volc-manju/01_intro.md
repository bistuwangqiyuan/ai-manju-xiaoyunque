# 小云雀-短剧漫剧Agent — 产品介绍

> source: https://www.volcengine.com/docs/85621/2432754?lang=zh
> 抓取时间: 2026-05-26 (via browser MCP)

## 调用流程 (4 步)

调用 小云雀-短剧漫剧Agent 服务需要依次完成 4 个流程:

1. **剧本解析** (~4 min)
   - 调用 「小云雀-短剧漫剧Agent-剧本解析-接口文档」
   - 返回 `assets_id`、`thread_id`、`EpisodeID`,用于后续流程
2. **图片生成** (~10 min)
   - 调用 「小云雀-短剧漫剧Agent-图片生成-接口文档」
3. **单集分镜视频生成** (~7 min / 集)
   - 调用 「小云雀-短剧漫剧Agent-视频生成-Seedance 2.0 fast 720p-接口文档」
   - 单次调用只生成指定剧集的分镜视频,可分多次直至全部
4. **单集视频合成** (~1 min / 集, 不计费)
   - 调用 「小云雀-短剧漫剧Agent-视频合成-Seedance 2.0 fast 720p-接口文档」
   - 单次调用只合成指定剧集视频

## 开通服务

前往「控制台」开通 3 个子服务 (cn-beijing):

- 短剧漫剧Agent-剧本解析
- 短剧漫剧Agent-图片生成
- 短剧漫剧Agent-视频生成-Seedance 2.0 fast 720p
  (或 Seedance 2.0 720p 标准版)

## 模型版本

| 模型版本 | 接口文档 ID | 用途 |
|---|---|---|
| Seedance 2.0 **fast** 720p | 2389853 (视频生成), 2407085 (视频合成) | 默认推荐,速度优先 |
| Seedance 2.0 720p (标准) | 2389854 (视频生成), 2424562 (视频合成) | 备选,质量略高 |

## 关键 ID 链

```
novel.docx
  ↓ 剧本解析
[assets_id, thread_id, EpisodeID]
  ↓ 图片生成 (用 thread_id + EpisodeID)
[images_generated]
  ↓ 单集分镜视频生成 (用 thread_id + EpisodeID 循环每集)
[storyboard_videos]
  ↓ 单集视频合成 (用 thread_id + EpisodeID 循环每集)
[final_mp4_url]
```

## 关键能力 (官方亮点)

1. **行业独家**: 剧本全自动解析+连贯生成
2. **全局角色/场景管理**: 全剧集角色+场景一键直出,角色不同时空妆造精准映射
3. **生产自动化**: Agent 智能旁白改编,多画风,多剧集连发

## 5 个接口文档原始 URL

- 产品介绍: https://www.volcengine.com/docs/85621/2432754?lang=zh (此文件)
- 全流程示例: https://www.volcengine.com/docs/85621/2459788?lang=zh
- 剧本解析: https://www.volcengine.com/docs/85621/2389851?lang=zh
- 图片生成: https://www.volcengine.com/docs/85621/2389852?lang=zh
- 视频生成 fast 720p: https://www.volcengine.com/docs/85621/2389853?lang=zh
- 视频合成 fast 720p: https://www.volcengine.com/docs/85621/2407085?lang=zh
