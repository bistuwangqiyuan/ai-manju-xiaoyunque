# 小云雀-短剧漫剧Agent - 单集分镜视频生成 (Seedance 2.0 fast 720p)

> source: https://www.volcengine.com/docs/85621/2389853?lang=zh

## 接入说明 (同前)

接口地址: `https://visual.volcengineapi.com`, Region `cn-north-1`, Service `cv`,
Action `CVSync2AsyncSubmitTask` / `CVSync2AsyncGetResult`, Version `2022-08-31`

## 1. 提交任务

### Body 参数

| 参数 | 类型 | 必选 | 说明 |
|---|---|---|---|
| `req_key` | string | ✓ | 固定 `pippit_shortplay_cvtob_video_generate_fast720p` |
| `assets_id` | string | ✓ | 剧本解析返回 |
| `thread_id` | string | ✓ | 剧本解析返回 |
| `episode_id` | string | ✓ | **剧集 ID**, 剧本解析返回的 EpisodeID, 每集独立调用 |
| `run_id` | string |  | 幂等 ID, <32 位 |

### 请求示例

```json
{
    "req_key": "pippit_shortplay_cvtob_video_generate_fast720p",
    "assets_id": "ark_1078230262796",
    "thread_id": "ark_4897354138488855440",
    "episode_id": "1",
    "run_id": "run_id_xxxx"
}
```

返回: `data.task_id`

## 2. 查询任务

Body: `req_key` + `task_id`。
返回 data.status + `resp_data` (JSON string)

## resp_data 关键字段

| 层级 | 名称 | 类型 | 说明 |
|---|---|---|---|
| 1 | `assets_id` / `thread_id` / `status` | string | 透传 |
| 1 | `storyboard_detail` | array | 单集资源详情 |
| 2 | `EpisodeID` / `EpisodeAssetID` / `VisualStyle` | - | 剧集 |
| 2 | `RoleList[].RoleID/RoleName/VisualAttributes/VocalAttributes/MaterialID` | - | 分镜角色 |
| 2 | `LocationList[].LocationID/LocationName/Description/MaterialID` | - | 分镜场景 |
| 2 | `ScriptStatus` | int | 分镜脚本状态 (0..5,3=done) |
| 2 | `ShotStatusMap` | object | 各分镜状态映射 (S1, S2, ... 每个含 RunID + Status) |
| 2 | `Shots[]` | array | 分镜 shot 列表 |
| 3 | `ShotID` / `Description` / `Status` | - | 分镜基础 |
| 3 | **`VideoURL`** | string | **分镜视频 URL** |
| 3 | `Duration` / `Width` / `Height` / `Format` / `Size` / `VideoAssetID` | - | 视频元信息 |
| 3 | `ModelName` / `Version` | - | 模型版本 (生成时填入) |
| 3 | `ContentLength` | string | 分镜脚本字数 |
| 3 | `LocationIDList` | array | 关联场景 ID |
| 1 | `charge_count` | int | 计费 |

## Status 取值

`0` 未知 / `1` 已初始化 / `2` 生成中 / `3` 已完成 / `4` 失败 / `5` 安全审核失败

## 失败 fallback

遍历 `ShotStatusMap.*` 检查所有分镜 Status。若有失败分镜:
- **整集无法调用视频合成** (必须所有分镜=3 才能合成)
- 可保存 `Description` + 图片资源,前往第三方工具重生成失败分镜
- 下载成功分镜视频,用第三方工具拼接

## 错误码 (同前)
