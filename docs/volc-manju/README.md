# 火山引擎「小云雀-短剧漫剧 Agent」官方文档 (PDF)

把以下 4 个官方 PDF 放到本目录, 我会自动从中提取 req_key + 字段映射,
然后实装 `src/shell3_skylark_engine/manju_agent_client.py` 的真实调用细节.

## 必需 PDF

| PDF 文件名 | 来源链接 | 用途 |
|---|---|---|
| `manju_agent_intro.pdf` | https://www.volcengine.com/docs/85621/2432754?lang=zh | 产品介绍 (画风/画幅/旁白/时长选项) |
| `manju_agent_video_gen.pdf` | https://www.volcengine.com/docs/85621/2389853?lang=zh | 视频生成接口 (Seedance 2.0 fast 720p) |
| `manju_agent_video_gen_720p.pdf` | https://www.volcengine.com/docs/85621/2389854?lang=zh | 视频生成接口 (Seedance 2.0 720p) |
| `manju_agent_video_synth.pdf` | https://www.volcengine.com/docs/85621/2407085?lang=zh | 视频合成接口 |
| `manju_agent_full_workflow.pdf` | https://www.volcengine.com/docs/85621/2459788?lang=zh | 全流程调用示例 |

## 下载步骤

1. 打开上面任意链接
2. 页面右上角点 **"下载 pdf"** 按钮
3. 把下载的 PDF 重命名为对应文件名, 放到 `docs/volc-manju/` 下
4. 告诉我 PDF 就绪

## 我会从 PDF 提取什么

```yaml
# 我会自动从 PDF 提取这些字段并填到 manju_agent_client.py:
req_key:        "manju_agent_seedance_v20_fast_720p"   # 真实 key
api_action:     "CVSync2AsyncSubmitTask"               # submit
api_query:      "CVSync2AsyncGetResult"                # query
endpoint:       "visual.volcengineapi.com"
fields:
  script_text:        "..."   # 剧本字段名
  style:              "..."   # 画风字段名 (2D / 3D / 真人)
  ratio:              "..."   # 画幅 (16:9 / 9:16)
  enable_narration:   "..."   # 旁白
  episode_duration:   "..."   # 每集时长
constraints:
  max_script_chars:   ...
  max_episode_count:  ...
  output_resolution:  720
```

## 当前状态

- **PDF 未提供**: ManjuAgentClient 走 mock 骨架, FORCE_MOCK_MANJU_AGENT=1 默认开
- **PDF 提供后**: 我替换 req_key 常量 + 字段映射 + 真实 endpoint, 30 分钟内完成

## 不破坏现有

现有 `pippit_iv2v_v20_cvtob_with_vinput` 仍然可用 (旧通用 IV2V),
通过 `MANJU_AGENT_MODE=0/1` 开关在 Orchestrator V2 里双轨切换.
