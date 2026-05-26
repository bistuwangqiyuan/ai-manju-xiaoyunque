# 火山引擎「小云雀-短剧漫剧 Agent」官方接口规范

> **状态**: 文档已通过浏览器 MCP 抓取齐全 (2026-05-26), `manju_agent_client.py`
> 已实装真实 `req_key` + 4 阶段流水线, 全部 30 个单元测试通过.

## 已抓取的官方接口文档

| 文件 | 上游链接 | 接口名 / `req_key` |
|---|---|---|
| [`01_intro.md`](01_intro.md) | [产品介绍](https://www.volcengine.com/docs/85621/2432754?lang=zh) | (无, 是综述) |
| [`02_script_parse.md`](02_script_parse.md) | [剧本解析](https://www.volcengine.com/docs/85621/2389851?lang=zh) | `pippit_shortplay_cvtob_script_analysis` |
| [`03_image_gen.md`](03_image_gen.md) | [图片生成](https://www.volcengine.com/docs/85621/2389852?lang=zh) | `pippit_shortplay_cvtob_material_design` |
| [`04_video_gen.md`](04_video_gen.md) | [视频生成 Seedance 2.0 fast 720p](https://www.volcengine.com/docs/85621/2389853?lang=zh) | `pippit_shortplay_cvtob_video_generate_fast720p` |
| [`05_video_compose.md`](05_video_compose.md) | [视频合成 Seedance 2.0 fast 720p](https://www.volcengine.com/docs/85621/2407085?lang=zh) | `pippit_shortplay_cvtob_video_compose_fast720p` |
| [`06_full_workflow.md`](06_full_workflow.md) | [全流程调用示例](https://www.volcengine.com/docs/85621/2459788?lang=zh) | (4 个串行) |

## 共用 OpenAPI 入口

```
POST https://visual.volcengineapi.com/?Action=CVSync2AsyncSubmitTask&Version=2022-08-31
POST https://visual.volcengineapi.com/?Action=CVSync2AsyncGetResult&Version=2022-08-31
Region: cn-north-1
Service: cv
签名: V4-HMAC-SHA256 (见 src/common/volc_signer.py)
```

## 实装位置

- 客户端: [`src/shell3_skylark_engine/manju_agent_client.py`](../../src/shell3_skylark_engine/manju_agent_client.py)
- 编排器: [`src/pipeline/orchestrator_v2.py`](../../src/pipeline/orchestrator_v2.py) (`MANJU_AGENT_MODE=1` 启用)
- 测试: 30 个单元测试 (15 个旧 + 15 个新官方契约)
  - [`tests/test_manju_agent_client.py`](../../tests/test_manju_agent_client.py)
  - [`tests/test_manju_official_contract.py`](../../tests/test_manju_official_contract.py)

## 运行时配置

```bash
# 启用漫剧 Agent (推荐, 集成度最高)
export MANJU_AGENT_MODE=1
export FORCE_MOCK_MANJU_AGENT=0

# 视频生成模型选择 (fast vs std)
export MANJU_REQ_KEY=pippit_shortplay_cvtob_video_generate_fast720p   # 默认
# 或更高画质 (慢约 2x)
export MANJU_REQ_KEY=pippit_shortplay_cvtob_video_generate_720p

# 凭证 (V4 签名)
export VOLC_ACCESS_KEY=...
export VOLC_SECRET_KEY=...

# 剧本上传到 TOS (公网可读)
export STORAGE_BACKEND=tos
export TOS_BUCKET=xyq-prod-cn-beijing
export TOS_ENDPOINT=https://tos-cn-beijing.volces.com
```

## 调用方式 (Python 一行)

```python
from src.shell3_skylark_engine.manju_agent_client import ManjuAgentClient

client = ManjuAgentClient()
result = client.render_script(
    novel_text=open("script.txt", encoding="utf-8").read(),
    ep_id="job-001",
    style="real",          # 或 "2d" / "3d" / "2D, 国风, 平涂" 等官方推荐值
    ratio="9:16",
    file_type="txt",
)
for ep in result.episodes:
    print(ep.episode_no, ep.archived_path, ep.cover_url)
```

## 时间预算 (10 集)

| 阶段 | 单次耗时 | 10 集累计 |
|---|---|---|
| 剧本解析 | 4 min | 4 min |
| 图片生成 | 10 min | 10 min |
| 视频生成 (per ep) | 7 min | 70 min |
| 视频合成 (per ep) | 1 min | 10 min |
| **合计** | - | **~95 min** |

## 不破坏旧链路

旧通用接口 `pippit_iv2v_v20_cvtob_with_vinput` ([`client.py`](../../src/shell3_skylark_engine/client.py))
仍保留. 通过 `MANJU_AGENT_MODE=0` 可一键回退到旧 7 步编排.
