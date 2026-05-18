# 小云雀 · 前端 Web

Next.js 15 (App Router) + TypeScript + Tailwind。设计为部署到 Vercel。

## 本地开发

```powershell
cd web
pnpm install
Copy-Item .env.example .env.local
# 编辑 .env.local，把 NEXT_PUBLIC_BACKEND_URL 指向你本地或远程的后端
pnpm dev
```

打开 http://localhost:3000。

## 关键约定

- 所有 API 调用走 `lib/api.ts`，通过 `Authorization: Bearer <token>` 鉴权
- Token 存 `localStorage`，刷新页面后从 `/api/auth/me` 反查用户
- 后端 URL 由 `NEXT_PUBLIC_BACKEND_URL` 环境变量决定
- Stripe Checkout 成功后 backend 回调到 `/billing/success`，前端再调 `/me` 刷新余额

## 部署到 Vercel

仓库根目录已有 `vercel.json` + 本子目录已经 self-contained。

### 新建 Vercel 项目（首次）
1. https://vercel.com/new → 选 GitHub repo `bistuwangqiyuan/ai-manju-xiaoyunque`
2. **Root Directory** = `web`
3. **Production Branch** = `main`
4. **Environment Variables** 加 `NEXT_PUBLIC_BACKEND_URL=https://ai-manju-xiaoyunque-production.up.railway.app`
5. Deploy

### 已有 Vercel 项目但指错地方（你现在的状态）
1. Settings → **General** → Root Directory 改为 `web` → Save
2. Settings → **Git** → Production Branch 改为 `main` → Save
3. Settings → **Environment Variables** 加 `NEXT_PUBLIC_BACKEND_URL=...`
4. Deployments → 最新一次 → Redeploy（不要用 cache）

## 部署

完整指引见根目录 [DEPLOY.md](../DEPLOY.md)。
