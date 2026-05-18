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

## 部署

见根目录 [DEPLOY.md](../DEPLOY.md)。
