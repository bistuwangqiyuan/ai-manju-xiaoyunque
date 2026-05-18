# 用户系统 E2E 测试报告

> 部署: https://yunque-manhua.vercel.app
> Database: Neon (Vercel-integrated, Hobby tier)
> 日期: 2026-05-18

## 已交付功能

1. **邮箱密码注册/登录** — bcrypt 哈希 + jose JWT HS256 (7天 cookie)
2. **三级用户体系**
   - 匿名访问者：可看主页，不能生成
   - **免费注册用户：每天 1 条生成额度**
   - **付费 Pro 用户：每天 100 条生成额度**
3. **额度强制**：UTC 日历日为窗口，自动 00:00 重置
4. **/account 中心**：查看额度、邮箱、Pro 有效期、申请升级（mailto）
5. **Admin 升 Pro 端点**：`POST /api/admin/set-tier` (Bearer ADMIN_TOKEN)

## 测试结果汇总

| # | 测试 | 状态 |
|---|---|---|
| 1 | POST /api/auth/register 邮箱密码 | ✅ 200 + cookie |
| 2 | GET /api/me 带 cookie 返回用户信息+额度 | ✅ tier:free, 1/day |
| 3 | POST /api/generate (1st) 消耗免费额度 | ✅ 200 + taskId |
| 4 | POST /api/generate (2nd) 拒绝（429 quota） | ✅ "今日额度已用完" |
| 5 | POST /api/generate 未登录 | ✅ 401 |
| 6 | POST /api/auth/register 重复邮箱 | ✅ 409 |
| 7 | POST /api/auth/login 错误密码 | ✅ 401 |
| 8 | POST /api/auth/login 正确凭据 | ✅ 200 + cookie |
| 9 | POST /api/auth/logout 清 cookie | ✅ 200 |
| 10 | POST /api/admin/set-tier 升 Pro | ✅ 200 |
| 11 | Pro 用户 /api/me 显示 100/day | ✅ tier:pro, dailyLimit:100 |
| 12 | Pro 用户 2nd 提交 (was 429) | ✅ 200 + taskId |
| 13 | Admin 端点不带 Bearer 拒绝 | ✅ 401 |
| 14 | GET /api/status 未登录拒绝 | ✅ 401 |

## 已修复的 bug

| # | Bug | 原因 | 修复 |
|---|---|---|---|
| 1 | Migrate 失败 "username NOT NULL" | Neon 自带 sample users 表 | 在 migrate 中加 DROP TABLE CASCADE 重建 |
| 2 | 注册后 cookie 解码失败 | PG BIGINT 在 Neon 返回字符串, JWT uid 是字符串而 verifySession 只接受 number | signSession 用 Number() 强转, verifySession 接受 string/number 并 coerce |
| 3 | 提交后 /api/me 显示 usedToday=0 | 用 v_user_quota_today 视图含 correlated subquery, 在 WHERE 过滤下 PG 优化器异常返回 0 | getQuota 改为内联 SELECT (绕开 view) |
| 4 | Pro 升级后 /api/me 仍 tier:free | Vercel-Neon **pooled URL** (pgbouncer) 在跨请求时返回过时 snapshot | db.ts 改用 `POSTGRES_URL_NON_POOLING` 直连 |
| 5 | bigint 类型在 JSON 中显示为 string "1" 干扰前端比较 | Neon driver 默认行为 | /api/me 和 generate 显式 `Number()` 强转 |

## 数据库 schema

3 张表 / 1 个视图 (`db/schema.sql`)：
- `users (id, email, password_hash, tier ∈ {free,pro}, pro_until, daily_limit_override, created_at, last_login_at)`
- `generations (id, user_id FK, task_id, prompt, ratio, duration, status, video_url, created_at)`
- `v_user_quota_today` 视图（保留作 admin 查询用, 内部 getQuota 不走视图）

## 关键 API

| 路由 | Method | Auth | 说明 |
|---|---|---|---|
| /api/auth/register | POST | – | 注册 + 自动登录 |
| /api/auth/login | POST | – | 密码登录 |
| /api/auth/logout | POST | – | 清 cookie |
| /api/me | GET | Cookie | 用户信息 + 配额 |
| /api/generate | POST | Cookie | 生成（强制额度） |
| /api/status/[taskId] | GET | Cookie | 任务状态 |
| /api/admin/migrate | POST | – (幂等) | 初始化 schema |
| /api/admin/set-tier | POST | Bearer ADMIN_TOKEN | 手工升 Pro |
| /api/admin/debug | GET | – | 读 DB 全表 (debug) |
| /api/proxy-video | GET | – | Volcengine CDN 代理 (host 白名单) |

## 环境变量

| 变量 | 必填 | 说明 |
|---|---|---|
| VOLC_ACCESS_KEY | ✓ | 火山方舟 IAM AK |
| VOLC_SECRET_KEY | ✓ | 火山方舟 IAM SK |
| AUTH_SECRET | ✓ | JWT HMAC 秘钥 (≥32 字节) |
| DATABASE_URL | ✓ (自动) | Vercel-Neon 注入 |
| POSTGRES_URL_NON_POOLING | ✓ (自动) | Vercel-Neon 注入 |
| ADMIN_TOKEN | × | 手工升 Pro 必需 |
| AIGC_CONTENT_PRODUCER | × | AIGC 制作主体 |

## 注：付费集成尚未接入

当前 /account 页面 "升级 Pro" 按钮跳到 `mailto:hello@yunque-manhua.com`。
Admin 收到邮件 → 手动调用 `POST /api/admin/set-tier` 升级用户。

未来接 Stripe Checkout / Alipay 即可一键完成。
