# 小云雀-短剧漫剧Agent - 图片生成接口

> source: https://www.volcengine.com/docs/85621/2389852?lang=zh

## 接入说明 (与剧本解析同)

| 项 | 值 |
|---|---|
| 接口地址 | `https://visual.volcengineapi.com` |
| Region | `cn-north-1` |
| Service | `cv` |
| Action | `CVSync2AsyncSubmitTask` / `CVSync2AsyncGetResult` |
| Version | `2022-08-31` |

## 1. 提交任务

### Body 参数

| 参数 | 类型 | 必选 | 说明 |
|---|---|---|---|
| `req_key` | string | ✓ | 固定值 `pippit_shortplay_cvtob_material_design` |
| `assets_id` | string | ✓ | 剧本解析返回的 assets_id |
| `thread_id` | string | ✓ | 剧本解析返回的 thread_id |
| `run_id` | string |  | 自定义幂等 ID,<32 位。相同 run_id 重复提交会查询时返回 50500 |

### 请求示例

```json
{
    "req_key": "pippit_shortplay_cvtob_material_design",
    "assets_id": "ark_1078230262796",
    "thread_id": "ark_4897354138488855440",
    "run_id": "run_id_xxxx"
}
```

返回: `data.task_id`

## 2. 查询任务

Body: `req_key` + `task_id`
返回 data.status (processing / in_queue / generating / done / not_found / expired) + `resp_data` (JSON string)

## resp_data 关键字段

| 层级 | 名称 | 类型 | 说明 |
|---|---|---|---|
| 1 | `assets_id` / `thread_id` / `status` | string | 透传 |
| 1 | `character_detail` | array | 角色资源详细 |
| 2 | `CharacterID` / `CharacterName` / `Alias` / `IsMainCharacter` / `IsMasses` / `Introduction` | - | 角色基础 |
| 2 | `TagInfos[].Name/Identity/Personality/Background/Gender/AgeGroup/IsCore` | - | 角色标签 |
| 2 | `AppearanceTree` | object | **角色形象树** (递归), 含 `BodyImageURL` / `BustPortraitURL` 全身图/半身图 URL |
| 2 | `ExpectRenderImageCount` / `ActualRenderImageCount` | int | 期望/实际渲染数 (用于检测失败) |
| 1 | `scene_detail` | array | 场景资源详细 |
| 2 | `SceneID` / `Name` | - | 场景基础 |
| 2 | `AppearanceDetails[].AppearanceID/Description/ImageURL/AssetID/Episodes/AppearanceName` | - | 场景视角 |
| 2 | `ExpectRenderImageCount` / `ActualRenderImageCount` | int | 期望/实际渲染数 |
| 1 | `image_count` | int | 计费 |

## 失败检测

遍历 `character_detail` 和 `scene_detail`,若任意 `ExpectRenderImageCount != ActualRenderImageCount` 表示该类型有图生成失败。失败图**不支持重传**。最常见失败原因: 审核未通过。

## 错误码 (与剧本解析同)
