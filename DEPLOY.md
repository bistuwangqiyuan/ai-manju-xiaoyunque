# 部署指南：Vercel + Railway

> 把 `web/` 部署到 Vercel（前端 + 静态托管），把 `backend/` 部署到 Railway（FastAPI + worker）。
> 完整链路打通后，全世界任何浏览器都能访问你的 SaaS。

## 当前生产状态 (2026-05-18)

| 组件 | 状态 | 地址 |
|---|---|---|
| 后端 Railway | ✅ 上线 | `https://ai-manju-xiaoyunque-production.up.railway.app` |
| 数据库 Neon | ✅ 已连 | Vercel 控制台 → Storage |
| 前端 Vercel | ⚠️ 需切换 | `https://yunque-manhua.vercel.app`（当前指向另一分支） |

**已交付的核心商业能力**（后端已生效，已端到端验证）：
- 多级用户：free / pro / studio / admin
- 配额：免费 3 集/天，每次 1 集；付费无限
- 计费：成本×1.10（base ¥65/集 → 售价 ¥71.5/集）
- 自动升级：首次任意金额充值，free → pro
- 并发：3 个 worker 同时渲染（SELECT...FOR UPDATE SKIP LOCKED 互斥）
- 质量：5 维评分，<90 自动重试最多 2 次
- 商用示例：landing 页 6 集预览画廊

---

## 如果你已有 Vercel 项目但指向错误的分支/目录

这是你现在的情况。你的 `yunque-manhua.vercel.app` 当前部署的是 `feat/wxkb-r10-r15-cinematic-iteration` 分支的 `webapp/` 目录（另一个 Claude 会话留下的平行实现）。要切到本会话写的 `main + web/`：

1. Vercel Dashboard → 进你的项目 → **Settings**
2. **General** → **Root Directory** → 改为 `web`（不是 `webapp`） → Save
3. **Git** → **Production Branch** → 改为 `main`（不是 feat/...） → Save
4. 顶部 **Deployments** tab → 最新 deploy 旁 **⋯** → **Redeploy** → 不要勾"Use existing Build Cache"
5. 等 1-2 分钟，新 deploy 完成后访问 `yunque-manhua.vercel.app`，应该看到顶部带"小云雀 · 漫剧产线"印章 logo + Free/Pro 徽章

完成后**唯一还要做的**：Vercel **Environment Variables** 加：
```
NEXT_PUBLIC_BACKEND_URL = https://ai-manju-xiaoyunque-production.up.railway.app
```
然后再 Redeploy 一次。

---

## 0. 架构总览

```
┌─────────────┐    HTTPS     ┌───────────────────┐
│  浏览器用户  │  ─────────▶  │  Vercel (web/)    │
└─────────────┘              │  Next.js 15       │
                             │  落地/定价/仪表盘  │
                             └─────────┬─────────┘
                                       │ fetch /api/*
                                       ▼
                             ┌───────────────────┐
                             │ Railway (backend/)│
                             │ FastAPI + worker  │
                             │ ┌───────────────┐ │
                             │ │ Postgres 插件  │ │
                             │ │ Volume 存视频  │ │
                             │ └───────────────┘ │
                             └─────────┬─────────┘
                                       │ (生产模式)
                                       ▼
                          外部 AI API (火山/Claude/...)
```

**为什么后端必须放 Railway 而不是 Vercel**：Vercel Functions 最长 900 秒，没有 ffmpeg/原生依赖，无持久存储。本流水线单次渲染要数分钟到数小时，且需要 ffmpeg。

---

## 1. 准备工作

- [x] GitHub 账号（代码托管）
- [x] Vercel 账号（前端，已就绪）
- [ ] Railway 账号 — https://railway.com 注册，绑卡走 $5/月起步包
- [ ] (可选) Stripe 账号 — 上线收款用，开发期不需要
- [ ] (可选) Cloudflare R2 / AWS S3 — 视频持久化，开发期可用本地

---

## 2. 把代码推到 GitHub

```powershell
# 在仓库根目录
git init        # 已经是 git 仓库就跳过
git add web backend DEPLOY.md
git commit -m "Add web frontend + FastAPI backend for SaaS deployment"

# 在 GitHub 上新建一个空仓库 xiaoyunque-saas，然后：
git remote add origin https://github.com/<你的用户名>/xiaoyunque-saas.git
git branch -M main
git push -u origin main
```

---

## 3. 部署后端到 Railway

### 3.1 创建项目

1. https://railway.com → **New Project** → **Deploy from GitHub repo**
2. 选刚才推上去的仓库 `bistuwangqiyuan/ai-manju-xiaoyunque`，分支 `main`
3. **不用改 Root Directory**。仓库根目录已经有 `railway.toml`，Railway 会自动读取它，用 `backend/Dockerfile`（构建上下文 = 仓库根）构建，启动命令 / 健康探针 / 重启策略全配好了。
4. 如果 Railway 在第一次构建时报"找不到 Dockerfile"或别的，那是它老 UI 没读到配置——这时再去 service → Settings → Source 把 Branch 确认是 `main` 即可（Root Directory 留空）。

### 3.2 加 Postgres（推荐生产用）

1. 项目里 **+ New** → **Database** → **Add PostgreSQL**
2. Postgres 会自动注入 `DATABASE_URL` 到所有 service，**FastAPI 会直接读到**，无需手填

> 不加 Postgres 也能跑，会回落到 SQLite。但 SQLite 文件存在容器内，容器重启会丢，**不要在生产用 SQLite**。

### 3.3 配置环境变量

在 backend service → **Variables** 里加：

| 变量 | 值 | 备注 |
|---|---|---|
| `JWT_SECRET` | 32 位以上随机串 | `python -c "import secrets;print(secrets.token_urlsafe(48))"` 生成 |
| `CORS_ORIGINS` | `https://<your-app>.vercel.app` | 前端域名，逗号分隔多个 |
| `SITE_URL` | `https://<your-app>.vercel.app` | Stripe 回调用 |
| `SIGNUP_BONUS_CENTS` | `10000` | 注册赠 ¥100 |
| `LOG_LEVEL` | `INFO` | |

**渲染相关（暂时全留空 → mock 模式，能跑通全链路）**：
- `VOLC_ACCESS_KEY` / `VOLC_SECRET_KEY` / `VOLC_ARK_API_KEY`
- `ANTHROPIC_API_KEY` / `DEEPSEEK_API_KEY` / `GEMINI_API_KEY`
- `ELEVENLABS_API_KEY` / `FAL_API_KEY`

**Stripe 相关（暂时留空 → 直接 mock 充值）**：
- `STRIPE_SECRET_KEY` / `STRIPE_WEBHOOK_SECRET`

### 3.4 生成公网域名

service → **Settings** → **Networking** → **Generate Domain**，得到类似
`https://xiaoyunque-backend-production.up.railway.app`

### 3.5 验证后端

```powershell
curl https://xiaoyunque-backend-production.up.railway.app/api/health
# 应返回 {"status":"ok","mock_worker":true,"mock_billing":true}
```

### 3.6 (可选) Volume 持久化视频

Railway service → **Settings** → **Volumes** → 挂 `/app/storage`。这样容器重启视频不丢。
生产建议直接换 S3/R2，填 `S3_*` 环境变量即可（代码里有挂载点）。

---

## 4. 部署前端到 Vercel

### 4.1 创建项目

1. https://vercel.com/new
2. **Import Git Repository** → 选同一个仓库
3. **Configure Project**：
   - **Root Directory** → 改成 `web`
   - **Framework Preset** → 自动识别为 Next.js（保持）
   - **Build Command** → 保持默认（`next build`）

### 4.2 配置环境变量

在 Vercel 项目 → **Settings** → **Environment Variables** 加：

| 变量 | Production 值 |
|---|---|
| `NEXT_PUBLIC_BACKEND_URL` | `https://xiaoyunque-backend-production.up.railway.app` |
| `NEXT_PUBLIC_SITE_URL` | `https://<your-app>.vercel.app` |
| `NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY` | `pk_test_xxx`（暂时随便填，没用到前端） |

### 4.3 Deploy

点 **Deploy**，等 1-3 分钟。完成后你会得到 `https://xiaoyunque-saas-<hash>.vercel.app`。

### 4.4 把这个域名回填到 Railway CORS

回到 Railway backend service → Variables → 把 `CORS_ORIGINS` 和 `SITE_URL` 更新为 Vercel 的实际域名，然后 **Redeploy**。

---

## 5. 上线验证清单

打开 `https://<your-app>.vercel.app`：

- [ ] 落地页正常显示（不要有控制台 CORS 报错）
- [ ] `/signup` 注册一个测试账号，跳转到 `/dashboard`，余额显示 ¥100
- [ ] `/dashboard/new` 提交一个 1 集任务，扣 ¥99，跳转到任务详情
- [ ] 任务详情页每 2.5s 自动刷新进度，约 60-90 秒后状态变为 `succeeded`
- [ ] 视频播放器出现 BigBuckBunny 示例视频（mock 模式产物）
- [ ] 点"下载 MP4"能下载
- [ ] `/pricing` 点购买跳到 `/billing/success`（mock 计费），余额增加

通过以上检查，**全世界用户都能用了**。

---

## 6. 后续上真实模式

### 6.1 接入真实视频流水线

1. 把 `src/shell1_*` ~ `src/shell5_*` 这些 Python 模块也复制进 `backend/` 里（或在 Dockerfile 里 `COPY ../src ./src`）
2. 编辑 `backend/app/worker.py` 的 `_run_real_pipeline()`：

```python
from src.shell1_screenwriter.run_pipeline import run as run_screenwriter
from src.shell2_character_assets.build_asset import build_all
from src.shell3_skylark_engine.client import render_episode_chunked
# ... 其它 shell

async def _run_real_pipeline(db, job):
    # 1) shell1 编剧
    _log(db, job, "INFO", "shell1: 编剧管线启动")
    episodes_yaml = await asyncio.to_thread(run_screenwriter, job.novel_excerpt)
    _set_progress(db, job, 15)

    # 2) shell2 角色资产
    # ...
    # 3) shell3 小云雀渲染（最耗时）
    # 4) shell4 质检
    # 5) shell5 后期合成

    # 上传到 S3，写 job.result_url
    job.result_url = f"https://{settings.S3_PUBLIC_BASE_URL}/{job.id}.mp4"
    db.commit()
```

3. 在 Railway 配置真实 API Keys（`VOLC_ACCESS_KEY` 等），rebuild

### 6.2 接入 Stripe 真实收款

1. https://stripe.com 注册商户
2. Dashboard → API Keys → 拿 `Secret key`
3. Railway 变量加 `STRIPE_SECRET_KEY=sk_live_xxx`
4. Dashboard → Webhooks → 加 endpoint `https://<railway>/api/billing/webhook`，选 `checkout.session.completed` 事件
5. 拿到 webhook secret，填 `STRIPE_WEBHOOK_SECRET`
6. Redeploy。`use_mock_billing` 会自动变 False，走真实 Checkout 流程

### 6.3 切对象存储

Railway 加变量：
```
S3_ENDPOINT=https://<account>.r2.cloudflarestorage.com
S3_BUCKET=xiaoyunque
S3_ACCESS_KEY=...
S3_SECRET_KEY=...
S3_PUBLIC_BASE_URL=https://pub-xxxxx.r2.dev
```

然后在 `worker.py` 渲染完成后用 `boto3` 上传，把 URL 写进 `job.result_url`。

---

## 7. 成本估算（参考）

| 项目 | 月度成本 |
|---|---|
| Vercel Hobby | 免费（个人项目够用） |
| Vercel Pro | $20/月（生产推荐） |
| Railway Hobby | $5/月起，按用量 |
| Railway Postgres | 已含在 Hobby 里 |
| Cloudflare R2 | $0.015/GB/月 + 出口免费 |
| Stripe | 按交易额 2.9% + 0.3刀 |
| **AI API** | **每集 ¥56-72，按实际调用量** |

**重要**：AI API 费用是大头。**务必在 `worker.py` 渲染前再做一次"用户余额 ≥ 估算成本"校验**，避免被刷爆。

---

## 8. 故障排查

| 症状 | 原因 | 处理 |
|---|---|---|
| 前端登录 401 | CORS 没配对 | Railway 的 `CORS_ORIGINS` 必须包含 Vercel 域名 |
| 前端拿不到 token | LocalStorage 在 SSR 不可用 | 代码已用 `'use client'` 隔离 |
| Railway 容器 OOM | 单容器跑 web+worker 内存撑不住 | 升级 Plan 或把 worker 拆独立 service |
| 任务一直 queued | worker 没启动 | `railway logs` 看 `Worker loop started` 是否出现 |
| 视频下载 404 | result_url 是临时外链 | 接入 S3/R2 持久化 |
| Stripe 测试卡 | 4242 4242 4242 4242 任意未来日期/CVV | |

---

完工。问题列出来一起解决。
