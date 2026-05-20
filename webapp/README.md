# 云雀漫剧 Web — AI 国漫一键生成

> 基于火山方舟 Skylark Agent 2.0 (Seedance 2.0 fast 720p) 的 Vercel 部署版前端
>
> 输入提示词 → 约 5 分钟收到 1 段 15 秒 1080×1920 竖屏国漫短片。

## 架构

```
Browser ──┐
          │ POST /api/generate (~1-3s)         ┌─→ task_id
          │ GET  /api/status/[taskId] (~1-3s)  │
          │ GET  /api/proxy-video?url=...      │
          ▼                                    ▼
   Next.js 14 (Vercel Functions, runtime=nodejs)
          │
          │ HMAC-SHA256 V4 (Node crypto)
          ▼
   https://visual.volcengineapi.com (cn-north-1 / cv)
          │
          ▼
   Skylark Agent 2.0 = Pippit IV2V with vinput
   (pippit_iv2v_v20_cvtob_with_vinput)
```

为什么 Vercel-only 可行：
- Skylark 生成是**真异步**的：submit 返回 task_id (~1s)，客户端轮询 status (~1s)。**不需要 Vercel 函数等待 5 分钟。**
- video_url 由 Volcengine CDN 直接 serve，Vercel 只做 proxy/路由
- 无 ffmpeg、无 CLIP、无 ArcFace 依赖 — 仅 Node.js 内置 crypto

## 一键部署

[![Deploy with Vercel](https://vercel.com/button)](https://vercel.com/new/clone?repository-url=https%3A%2F%2Fgithub.com%2Fbistuwangqiyuan%2Fai-manju-xiaoyunque&root-directory=webapp&env=VOLC_ACCESS_KEY,VOLC_SECRET_KEY&envDescription=%E7%81%AB%E5%B1%B1%E6%96%B9%E8%88%9F%20IAM%20AK%2FSK&envLink=https%3A%2F%2Fconsole.volcengine.com%2Fiam)

## 手动部署

```bash
cd webapp
npm install
npm run dev      # http://localhost:3000
```

**生产部署**：

```bash
# 安装 Vercel CLI
npm i -g vercel

# 登录
vercel login

# 在 webapp/ 目录下
cd webapp
vercel link
vercel env add VOLC_ACCESS_KEY production
vercel env add VOLC_SECRET_KEY production

# 部署
vercel --prod
```

## 环境变量

| 变量 | 必填 | 说明 |
|---|---|---|
| `VOLC_ACCESS_KEY` | ✓ | 火山方舟 IAM Access Key (AK) |
| `VOLC_SECRET_KEY` | ✓ | 火山方舟 IAM Secret Key (SK) |
| `AIGC_CONTENT_PRODUCER` | × | AIGC 制作主体 ID（默认 `yunque-manhua`） |
| `AIGC_CONTENT_PROPAGATOR` | × | AIGC 传播主体 ID（默认 `yunque-web`） |
| `DAILY_GENERATION_LIMIT` | × | 每 IP 每日生成上限（默认无限） |
| `NEXT_PUBLIC_SITE_NAME` | × | 站点名 |

**如何获取 AK/SK**：登录 [火山引擎控制台](https://console.volcengine.com/iam) → 用户管理 → 创建用户 → 生成密钥。

## 文件结构

```
webapp/
├── app/
│   ├── api/
│   │   ├── generate/route.ts         POST 提交任务
│   │   ├── status/[taskId]/route.ts  GET 查询状态
│   │   └── proxy-video/route.ts      GET 视频流代理
│   ├── globals.css                   Apple-style + Tailwind base
│   ├── layout.tsx                    根布局（中文 SC）
│   └── page.tsx                      首页
├── components/
│   ├── GeneratorForm.tsx             主表单 + 轮询 + 视频展示
│   └── ExamplePrompts.tsx            R40 评分 96+ 示例 prompt
├── lib/
│   ├── volc-signer.ts                V4 HMAC-SHA256 签名 (TS port)
│   └── skylark.ts                    Skylark client (submit/query)
├── public/
├── package.json
├── tsconfig.json
├── tailwind.config.ts
├── next.config.mjs
├── postcss.config.mjs
├── vercel.json
└── .env.example
```

## API 限制

- Vercel Hobby tier serverless 单函数最长 10s，**不够用**
- Vercel Pro tier：60s，足够 submit + status 调用
- Skylark 提示词最长 2000 字符
- video_url 1 小时过期，需用户尽快下载

## 已知边界

- **概览 demo 用，不含 Shell 5 后期 + 评分**：完整 pipeline 在 Python 端（R1-R40），webapp 只跑 Skylark 原始输出
- **无用户系统**：API key 在服务端环境变量，所有请求共享同一个火山账号
- **简易内存限流**：`DAILY_GENERATION_LIMIT=N` 启用 per-IP per-day 上限，生产建议接 Upstash Redis
- **CDN URL 1h 过期**：用户必须在 1h 内下载

## 安全

- API 密钥仅在服务端使用，前端永远看不到
- Proxy video 路由有 host 白名单（仅 Volcengine CDN），防 SSRF
- HMAC 签名在每次请求时计算，不缓存

## 路线图（如需进一步开发）

- [ ] 接 Vercel Blob 持久化生成的 mp4
- [ ] Stripe 接付费用户系统
- [ ] 把 R30 / R40 已生成的样片放 demo 页静态展示
- [ ] 接 Supabase / Upstash 做分布式限流 + 历史记录
