# 小云雀 · AI 漫剧产线 v7 — 世界级多题材 SaaS · 聂小倩旗舰案例

> **世界最高水平 AI 漫剧产线 + SaaS 化对外服务**
> 多题材：古风 / 现代 / 甜宠 / 悬疑 / 玄幻；旗舰案例：聊斋·聂小倩（10 集 × 75-90s · 9:16 · 古风 3D 国漫）
> 架构：小云雀 Agent 2.0（有参考接口）+ 海外旗舰精修（Veo 3.1 / Sora 2 Pro / Runway Aleph / FLUX Kontext）
> 单集 ¥56-72 · 10 集 ¥866 · 7-10 天落地 · 跨集 ArcFace ≥ 0.80 · 每镜 7 维 VLM 评分 + 闭环自修复

完整方案：[final-plan.md](final-plan.md) · 部署指南：[DEPLOY.md](DEPLOY.md) · 选型调研：[research-2026-05.md](research-2026-05.md)

## v7 世界级升级（2026-05）

- **6 步流水线 v2**（`src/pipeline/orchestrator_v2.py`）：剧本分析 → 资产包 → 分镜 → 抽卡 → 粗剪 → 精剪审核，Shell4 + Shell5 全链路集成
- **7 维 VLM 每镜评分 + 闭环自修复**（`src/shell4_qa_repair/seven_dim_scorer.py`、`repair_router.repair_until_pass`）
- **多题材模板**（`config/genres/*.yaml`）：5 大题材随选随用
- **主题→小说自动生成**（Claude Opus 4.7 / DeepSeek V4-Pro），版权 LLM novelty check（10 大 IP 指纹库）
- **资产库**：6 表情、6 动作、6 服饰、可复用场景库 + 自动近/中/远景
- **批量转绘子系统**（`src/transcribe/`）：多文件上传 + 7 维 loop + zip 导出
- **多平台导出**：抖音 / 快手 / 视频号 / 小红书 / B站 / YouTube Shorts，自动水印 + AIGC 标识 + 营销文案
- **高级智能**：剧情续写、风格迁移（日系/国漫/写实/二次元）、角色互动图
- **多语言**：ElevenLabs Multilingual v3 + 双语字幕 + 前端 zh-CN/en
- **版本中心**：每次渲染快照 + 一键回滚 + 对比
- **24 项 mock-mode 测试** + GitHub Actions CI 全部绿

---

## 对外 SaaS 部署

- **前端**：[`web/`](web/) → Vercel（`vercel.json` rootDirectory = `web`）
- **后端**：[`backend/`](backend/) → Railway（`railway.toml` + 全量 `src/` 流水线）
- 详见 [`DEPLOY.md`](DEPLOY.md)

## 仓库结构

```
ai漫剧小云雀/
├── README.md                              本文件
├── web/                                   ★ 对外 SaaS 前端（主站）
├── backend/                               ★ FastAPI + 6 步 worker
├── webapp/                                演示版（已降级，非主站）
├── final-plan.md                          ★ v5 终极方案主交付
├── tech.md                                v4 历史基线
├── research-2026-05.md                    全球 SOTA 选型调研（69KB）
├── content_report.md                      聂小倩内容侧调研（82KB）
├── novel-聂小倩.md                         蒲松龄原著（公版）
├── .env / .env.example                    API Keys
├── requirements.txt                       Python 依赖
│
├── config/production.yaml                 v5 终极选型表（所有 model id / 阈值 / 权重）
│
├── src/
│   ├── common/                            V4 签名 + 存储 + 重试
│   ├── shell1_screenwriter/               编剧四模型流水线
│   ├── shell2_character_assets/           角色资产 + 三重 ID 锁
│   ├── shell3_skylark_engine/             ★ 小云雀 v2 有参考客户端
│   ├── shell4_qa_repair/                  质检 + 5 道修复
│   └── shell5_post_production/            TTS / BGM / 字幕 / 4K
│
├── prompts/
│   ├── style/ancient_3d_guoman.yaml       60/30/10 复合风格锚点
│   ├── characters/                        5 主角 YAML 锁定模板
│   ├── scenes/                            5 核心场景 YAML
│   └── episodes/ep01-ep10.yaml            10 集小云雀友好版分镜模板
│
├── pilot/episode_1_e2e.py                 第 1 集端到端 hello world
│
├── compliance/
│   ├── filing_template.md                 广电总局 2026/04/01 备案模板
│   └── aigc_label_checklist.md            AIGC 标识合规清单
│
└── data/                                  运行时产物（gitignore）
    ├── characters/                        14 张/角色 参考图入库
    ├── scenes/, style/, voices/
    ├── episodes/                          10 集成片
    └── covers/                            10 集封面
```

---

## 环境配置

### 1. Python 依赖

```bash
pip install -r requirements.txt
```

### 2. 系统依赖

- **Python 3.11+**
- **ffmpeg 6.0+**（PATH 中可用，验证 `ffmpeg -version`）
- **字体**：思源黑体 CN / 思源宋体 CN（Windows 已自带 msyh.ttc + simsun.ttc 作 fallback）
- **可选**：InsightFace（离线 ArcFace 检查 `pip install insightface onnxruntime`）

### 3. API Key 清单（写入 `.env`）

复制 `.env.example` 为 `.env`，按下表填入：

| 变量 | 用途 | 申请页面 |
|---|---|---|
| `VOLC_ACCESS_KEY` / `VOLC_SECRET_KEY` | 小云雀 / Seedream / Seedance / 即梦 | [火山方舟控制台](https://console.volcengine.com) |
| `VOLC_ARK_API_KEY` | 豆包 Seed 1.6 Vision / Thinking | 同上 |
| `DOUBAO_TTS_APPID` / `DOUBAO_TTS_TOKEN` | 豆包 Seed-TTS 2.0 + ICL | [火山语音技术](https://console.volcengine.com/speech) |
| `ANTHROPIC_API_KEY` | Claude Opus 4.7 主笔 | [console.anthropic.com](https://console.anthropic.com) |
| `DEEPSEEK_API_KEY` | DeepSeek V4-Pro 事件抽取 | [platform.deepseek.com](https://platform.deepseek.com) |
| `GEMINI_API_KEY` | Gemini 2.5 Pro schema 校验 | [aistudio.google.com](https://aistudio.google.com) |
| `ELEVENLABS_API_KEY` | ElevenLabs Music / SFX / Multilingual | [elevenlabs.io](https://elevenlabs.io) |
| `FAL_API_KEY` | InfiniteYou / Wan 2.7-FLF / FLUX Kontext / Hedra（备） | [fal.ai](https://fal.ai) |
| `REPLICATE_API_TOKEN` | PuLID 多角色锁 | [replicate.com](https://replicate.com) |
| `OPENAI_API_KEY` | Sora 2 Pro 1080P（ep09 仅用） | [platform.openai.com](https://platform.openai.com) |
| `GOOGLE_CLOUD_PROJECT` / `GOOGLE_ACCESS_TOKEN` | Veo 3.1 / Veo upscaler | [console.cloud.google.com](https://console.cloud.google.com) |
| `RUNWAY_API_KEY` | Runway Aleph V2V | [dev.runwayml.com](https://dev.runwayml.com) |
| `HEDRA_API_KEY` | Hedra Character-3 lip-sync | [hedra.com](https://www.hedra.com) |
| `MINIMAX_API_KEY` | MiniMax Speech 2.5 HD（情感张力） | [platform.minimax.io](https://platform.minimax.io) |
| `SUNO_API_KEY` | Suno v5.5 Premier 主题曲（可选） | [suno.com/api](https://suno.com) |

> ⚠️ **必备最低 6 个 Key**：VOLC_ACCESS_KEY/SECRET_KEY + VOLC_ARK_API_KEY + DOUBAO_TTS_* + ANTHROPIC_API_KEY + DEEPSEEK_API_KEY + GEMINI_API_KEY + ELEVENLABS_API_KEY + FAL_API_KEY。
> 海外旗舰（Veo / Sora / Runway / Hedra）只在高光集精修使用，可在 D7-D9 阶段再补。

---

## 跑通顺序（7-10 天）

### D1 — 烟雾测试 + 字段对齐

```powershell
# 0. 环境检查（必备 Key + ffmpeg）
python scripts/check_env.py

# 1. 合规扫描
python scripts/compliance_check.py --all

# 2. 小云雀有参考接口字段对齐（dry-run）
python pilot/episode_1_e2e.py --episode ep01 --dry-run

# 3. 真正跑一次 hello world（最低 ¥30 成本）
python pilot/episode_1_e2e.py --episode ep01 --skip-assets
# → 自动用 3 候选 req_key fallback；正确字段会缓存到 data/.skylark_req_key.json
```

### D2 — 编剧管线

```powershell
python -m src.shell1_screenwriter.run_pipeline --novel novel-聂小倩.md --output prompts/episodes/ep01-ep10.yaml
```

### D3 — 角色资产产线

```powershell
foreach ($c in @("ningcaichen","nie_xiaoqian","yan_chixia","popo_yaowu","ningmu_hengniang")) {
  python -m src.shell2_character_assets.build_asset --char-id $c
}
```

### D4 — 第 1 集完整端到端

```powershell
python pilot/episode_1_e2e.py --episode ep01
# → 输出 data/episodes/ep01/final.mp4
```

### D5 — 五道防线测试

```powershell
python -m src.shell4_qa_repair.run_qa --episode ep01
```

### D6 — Shell 5 后期

```powershell
python -m src.shell5_post_production.compose --episode ep01
```

### D7-D9 — 10 集批量 + 高光精修

```powershell
python scripts/batch_render.py --episodes ep02,ep03,ep05,ep06,ep07,ep10 --concurrency 8
python scripts/precision_render.py --episodes ep04,ep08 --tier veo-3.1-standard
python scripts/precision_render.py --episodes ep09 --tier sora-2-pro-1080p
```

### D10 — 备案 + 合规检查 + 上线

```powershell
python scripts/compliance_check.py --all
# 通过后按 compliance/filing_template.md 提交广电备案
```

---

## 关键设计决策

| 决策点 | 答案 | 来源 |
|---|---|---|
| 为什么以小云雀为核心？ | 唯一同时命中「中文古风 / 9:16 / 整集级 / 跨集人物锁定 / 商用绿灯」五要素的工业 API | research-2026-05 §1.1.4 |
| 为什么走「古风 3D 国漫」？ | 小云雀 + Seedance 一致性最强；工业感最足；契合聂小倩鬼魅气质 | content_report §B |
| 为什么是 10 集？ | 红果 / 听花岛节拍模板验证，10 集情感落点恰好 | content_report §A3 |
| 为什么必须 ASS 字幕？ | 小云雀 AI 字幕 ~25% 乱码率，硬性 bug | tech.md §10 |
| 为什么 ArcFace 0.78 阈值？ | 业内共识：低于此分跨集脸漂移人眼可辨 | research-2026-05 §3 |

---

## 字段对齐（已完成 ✅ 2026-05）

**官方文档已确认**，所有字段升级为"真值"：

| 字段 | 官方真值 |
|---|---|
| `req_key` | `pippit_iv2v_v20_cvtob_with_vinput`（单值，无 fallback） |
| 参考资源 | 扁平 `img_url_list[]` + `video_url_list[]`（合计 ≤ 50） |
| 比例 | `ratio` ∈ {16:9, 9:16, 4:3, 3:4} |
| 时长 | `duration` ∈ {"～15s", "～30s", "40～60s"} — **单次最长 60s** |
| 语言 | `language="Chinese"`（默认） |
| 明水印 | `enable_watermark=false`（商用关闭，本地自渲染） |
| video_url 有效期 | **1 小时**（必须立即转存） |
| task_id 有效期 | **12 小时** |
| 隐式水印 | 查询时 `req_json` 传 `aigc_meta` |

## ⚠️ 关键约束：单次 ≤ 60s → 90s 集自动分块

10 集计划中 **ep04 / ep08 / ep09 = 90s** 超过官方 60s 上限；所有 75-90s 集全部走
`render_chunked_episode(2 chunks + 0.25s crossfade)`：

```
chunk_a (40~60s, 前半: 钩子 + 铺垫 + 半高潮)
       ↓ 末帧 tail_a.jpg 作 chunk_b 第一张 img_url_list
chunk_b (~30s 或 40~60s, 后半: 反转 + 悬念)
       ↓ ffmpeg xfade 接缝
final.mp4 (75-90s)
```

成本影响：高光集 ¥27-40 → ¥54-80；10 集总成本仍 ≈ ¥866。

---

## 合规与法律

- **公版**：蒲松龄《聊斋志异》早已公版（1715 年卒，超 70 年）
- **避险**：必须刻意回避徐克 87 版独创元素 → 见 [compliance/filing_template.md](compliance/filing_template.md) §2.4
- **AIGC 标识**：所有成片必须显式 + 隐式双标识 → 见 [compliance/aigc_label_checklist.md](compliance/aigc_label_checklist.md)
- **广电备案**：2026/04/01 起强制先备案后上线 → 见 [compliance/filing_template.md](compliance/filing_template.md)

---

## 引用

如果本产线对你的项目有帮助，请引用：

```
@misc{nie_xiaoqian_2026,
  title  = "World-class AI 漫剧 Production Pipeline v5 (聂小倩 case study)",
  year   = 2026,
  note   = "Skylark Agent 2.0 + Veo 3.1 + Sora 2 Pro hybrid architecture"
}
```

---

## License

代码：MIT
内容（剧本 / 设计稿）：CC BY-NC-SA 4.0
原著《聊斋志异》：公版
