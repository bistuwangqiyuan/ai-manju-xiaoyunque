# 小云雀-短剧漫剧Agent - 剧本解析接口

> source: https://www.volcengine.com/docs/85621/2389851?lang=zh
> 抓取时间: 2026-05-26 (via browser MCP)

## 接入说明

| 项 | 值 |
|---|---|
| 接口地址 | `https://visual.volcengineapi.com` |
| 请求方式 | POST |
| Content-Type | application/json |
| Region | `cn-north-1` (固定) |
| Service | `cv` (固定) |

## 1. 提交任务 (CVSync2AsyncSubmitTask)

**URL**: `https://visual.volcengineapi.com?Action=CVSync2AsyncSubmitTask&Version=2022-08-31`

### Body 参数

| 参数 | 类型 | 必选 | 说明 |
|---|---|---|---|
| `req_key` | string | ✓ | 固定值 `pippit_shortplay_cvtob_script_analysis` |
| `visual_style` | string | ✓ | 视觉风格,可自定义。推荐值: `"2D, 国风, 平涂"` / `"3D, CG动画, 写实都市"` / `"真人写实, 电影风格, 冷色调"` / `"2D, 赛璐璐, 半厚涂"` / `"真人写实, 电视风格, 高清画质"` |
| `video_ratio` | string | ✓ | `"16:9"` 或 `"9:16"` |
| `file_url` | string | ✓ | 剧本文件URL (公网可访问),支持 `.txt` `.docx`, 最长 10 万字 |
| `file_type` | string | ✓ | `"txt"` 或 `"docx"` |
| `file_name` | string | ✓ | 含后缀, 如 `"xxx剧本.docx"` |
| `description` | string |  | 剧本文件描述 |
| `size` | int |  | 字节 |

### 请求示例

```json
{
    "req_key": "pippit_shortplay_cvtob_script_analysis",
    "visual_style": "2D, 国风, 平涂",
    "video_ratio": "16:9",
    "file_url": "https://xxxx.docx",
    "file_type": "docx",
    "file_name": "xxx剧本.docx"
}
```

### 返回示例

```json
{
    "code": 10000,
    "data": { "task_id": "7392616336519610409" },
    "message": "Success",
    "request_id": "20240720103939AF0029465CF6A74E51EC",
    "time_elapsed": "104.852309ms"
}
```

## 2. 查询任务 (CVSync2AsyncGetResult)

**URL**: `https://visual.volcengineapi.com?Action=CVSync2AsyncGetResult&Version=2022-08-31`

### Body 参数

| 参数 | 类型 | 必选 | 说明 |
|---|---|---|---|
| `req_key` | string | ✓ | `pippit_shortplay_cvtob_script_analysis` |
| `task_id` | string | ✓ | 提交接口返回的 task_id |

### 返回 data 字段

| 字段 | 类型 | 说明 |
|---|---|---|
| `status` | string | `processing` / `in_queue` / `generating` / `done` / `not_found` / `expired` |
| `resp_data` | JSON string | 剧本解析详细数据,序列化 JSON |

### resp_data 关键字段 (反序列化后)

| 层级 | 名称 | 类型 | 说明 |
|---|---|---|---|
| 1 | `assets_id` | string | **资产 ID,后续流程依赖** |
| 1 | `thread_id` | string | **会话 ID,后续流程依赖** |
| 1 | `status` | string | 状态说明 |
| 1 | `script_detail.CoreElement.MainCharacter` | string | 主角 |
| 1 | `script_detail.CoreElement.EpisodeCount` | string | 剧集数 |
| 1 | `script_detail.Settings.VisualStyle` | string | 视觉风格 (回显) |
| 1 | `script_detail.Settings.VideoRatio` | string | 视频比例 (回显) |
| 1 | `script_detail.CharacterAssets[].CharacterID/CharacterName/CharacterAssetID/AppearanceCount/IsMainCharacter` | - | 角色资产列表 |
| 1 | `script_detail.SceneAssets[].SceneAssetID` | - | 场景资产列表 |
| 1 | `script_detail.EpisodeAssets[].EpisodeID/EpisodeName/EpisodeTitle/EpisodeAssetID/StoryboardAssetID` | - | 剧集资产列表 (**EpisodeID 后续视频流程依赖**) |
| 1 | `script_detail.StoryboardBriefs[].EpisodeID/StoryboardAssetID` | - | 分镜资产列表 |
| 1 | `script_detail.StageStatusMap.script_overview_analysis.Status` | int | 0 未知 / 1 已初始化 / 2 生成中 / 3 已完成 / 4 失败 / 5 安全审核不通过 |
| 1 | `charge_count` | int | 计费统计 |

### 错误码

| HttpCode | code | 说明 | 可重试 |
|---|---|---|---|
| 200 | 10000 | 成功 | - |
| 400 | 50411 | Pre Img Risk Not Pass | ✗ |
| 400 | 50511 | Post Img Risk Not Pass | ✓ |
| 400 | 50412 | Text Risk Not Pass | ✗ |
| 400 | 50413 | Post Text Risk Not Pass (敏感词/版权词) | ✗ |
| 429 | 50429 | QPS 超限 | ✓ |
| 429 | 50430 | 并发超限 | ✓ |
| 500 | 50500 | Internal Error | ✓ |
| 500 | 50501 | Internal RPC Error | ✓ |

## 关键保存的 3 个 ID

`assets_id` + `thread_id` + `EpisodeID` (每个 episode 一个) → 后续 4 个接口全程透传
