# 小云雀-短剧漫剧Agent - 单集视频合成 (Seedance 2.0 fast 720p)

> source: https://www.volcengine.com/docs/85621/2407085?lang=zh
> 注: 此接口不计费

## 接入说明 (同前)

接口地址: `https://visual.volcengineapi.com`, Region `cn-north-1`, Service `cv`,
Action `CVSync2AsyncSubmitTask` / `CVSync2AsyncGetResult`, Version `2022-08-31`

## 1. 提交任务

### Body 参数

| 参数 | 类型 | 必选 | 说明 |
|---|---|---|---|
| `req_key` | string | ✓ | 固定 `pippit_shortplay_cvtob_video_compose_fast720p` |
| `assets_id` | string | ✓ | 剧本解析返回 |
| `thread_id` | string | ✓ | 剧本解析返回 |
| `episode_id` | string | ✓ | 剧集 ID, 单次只合成 1 集 |

### 请求示例

```json
{
    "req_key": "pippit_shortplay_cvtob_video_compose_fast720p",
    "assets_id": "ark_1078230262796",
    "thread_id": "ark_4897354138488855440",
    "episode_id": "1"
}
```

返回: `data.task_id`

## 2. 查询任务

Body: `req_key` + `task_id`。返回 `data.status` + `resp_data` (JSON string)

## resp_data 字段

| 层级 | 名称 | 类型 | 说明 |
|---|---|---|---|
| 1 | `assets_id` | string | 资产 ID |
| 1 | `thread_id` | string | 会话 ID |
| 1 | `run_id` | string | 任务 ID |
| 1 | `storyboard_asset_id` | string | 分镜资产 ID |
| 1 | `status` | string | 状态 `Success` 等 |
| 1 | **`final_video_url`** | string | **合成后的单集视频 URL** |
| 1 | **`final_video_cover_url`** | string | **合成后的单集封面 URL** |

## resp_data 完整返回示例

```json
{
    "thread_id": "ark_6845974137674619680",
    "run_id": "8f0a167e618170be5b9db88acb5d3b80_stage41",
    "assets_id": "ark_1100991508748",
    "status": "Success",
    "storyboard_asset_id": "1101326621964",
    "final_video_url": "https://v26-default.365yg.com/xxxx.mp4",
    "final_video_cover_url": "https://p26-sign.douyinpic.com/xxxx"
}
```

## 前置依赖

视频合成前所有分镜 (`Shots[*].Status == 3` 且 `ShotStatusMap` 全部状态=3) 必须为成功
状态, 否则无法触发合成。

## 错误码 (同前)
