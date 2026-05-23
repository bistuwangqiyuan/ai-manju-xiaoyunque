# 国内无服务器（Serverless）部署 · 小云雀 AI 漫剧

> 全栈 **scale-to-zero** · 闲时 ¥0 · 按用量计费 · 无需购买/运维服务器
>
> **架构（全腾讯云一站式）：**
> ```
> 浏览器 → EdgeOne Pages (Next.js, CN 边缘 CDN, 闲时 ¥0)
>           ↓ /api/* rewrites
>         CloudBase 云托管 (FastAPI 容器, min=0 max=10, 按 CPU 秒计费)
>           ↓
>         PostgreSQL Serverless (scale-to-zero, ¥0.000xx/RCU·s)
>           ↑
>         SCF 定时函数 (每 60s 一次 tick, 唤醒云托管处理排队任务)
>           ↓
>         COS 对象存储 (视频/封面/字幕, ¥0.118/GB·月)
> ```

| 组件 | 平台 | 类型 | 闲时费用 | 满负载示例月度 |
|---|---|---|---|---|
| 前端 | 腾讯云 EdgeOne Pages | Edge serverless | **¥0** | ¥0-5 (前 100GB 流量免费) |
| 后端 API | 腾讯云 CloudBase 云托管 | 容器 serverless | **¥0** (min=0) | ¥5-30 (按 CPU 秒) |
| Worker | 腾讯云 SCF 定时函数 | FaaS | **¥0** (每月 100w 次免费) | ¥0-5 |
| 数据库 | 腾讯云 PostgreSQL Serverless | DB serverless | **¥0-3** (低保) | ¥10-50 |
| 对象存储 | 腾讯云 COS | 对象存储 | **¥0** | ¥3-20 |
| **合计** | | | **¥0-3 / 月** | **¥18-110 / 月** |

> 真正闲时 < ¥5/月。比起轻量服务器方案，**完全弹性、自动扩缩、无运维**。

---

## 0. 准备清单（10 分钟）

| 项 | 操作 | 链接 |
|---|---|---|
| ✅ 腾讯云账号 | 注册 + 实名认证（个人即可） | https://cloud.tencent.com/register |
| ✅ Node.js 18+ | 本机安装 | https://nodejs.org |
| ✅ Python 3.11+ | 已装 | — |
| ✅ GitHub 仓库 | 已 push（commit `43902fc`+） | — |
| ✅ 域名（可选） | 备案过的或香港域名 | — |

---

## 1. 第一步 · 开通 4 个腾讯云服务（5 分钟，全部点点点）

| 序 | 服务 | 入口 | 操作 | 关键产物 |
|---|---|---|---|---|
| ① | **CloudBase 云开发** | https://console.cloud.tencent.com/tcb | 创建 "按量计费" 环境 → 区域选**上海** | `ENV_ID`（形如 `xyq-prod-1g123ab456cd`） |
| ② | **PostgreSQL Serverless** | https://console.cloud.tencent.com/postgres | 购买 "Serverless 版" → 区域**上海** → 创建数据库 `xyq` + 用户 `xyq` | `DATABASE_URL` 内网地址 |
| ③ | **COS 对象存储** | https://console.cloud.tencent.com/cos | 创建存储桶 `xyq-prod-1300000000` → 区域**上海** → 权限**公共读私有写** | `COS_BUCKET` + `COS_SECRET_*` |
| ④ | **EdgeOne Pages** | https://console.cloud.tencent.com/edgeone/pages | "开始使用" 即可（不要创建项目，第 4 步再做） | — |

> 注：第 ② 步创建 Postgres 时，**记得把第 ① 步的 CloudBase 环境加入"内网 VPC 互通"**。
> CloudBase 控制台 → 环境 → 网络设置 → 添加 Postgres 所在 VPC。

### 申请 AccessKey（部署脚本要用）

入口：https://console.cloud.tencent.com/cam/capi → 新建密钥 →
保存 `TENCENT_SECRET_ID` + `TENCENT_SECRET_KEY`（**只显示一次**）。

---

## 2. 第二步 · 填写本地 `.env`（3 分钟）

```powershell
cd deploy/cn-serverless
Copy-Item .env.example .env
notepad .env       # 或用 VSCode/Cursor 打开
```

**必填 6 项**：

```env
TENCENT_SECRET_ID=AKID...
TENCENT_SECRET_KEY=...
ENV_ID=xyq-prod-1g123ab456cd
DATABASE_URL=postgresql+psycopg2://xyq:你的密码@gz-postgres-xxx.sql.tencentcdb.com:5432/xyq
JWT_SECRET=用 openssl rand -base64 48 生成
INTERNAL_API_SECRET=同上再生成一个
```

**强烈推荐 6 项（COS 持久化）**：

```env
COS_REGION=ap-shanghai
COS_ENDPOINT=https://cos.ap-shanghai.myqcloud.com
COS_BUCKET=xyq-prod-1300000000
COS_SECRET_ID=AKID...
COS_SECRET_KEY=...
COS_PUBLIC_BASE_URL=https://xyq-prod-1300000000.cos.ap-shanghai.myqcloud.com
```

**Windows 生成随机密钥的命令**：

```powershell
# JWT_SECRET / INTERNAL_API_SECRET 各跑一次
[Convert]::ToBase64String([System.Security.Cryptography.RandomNumberGenerator]::GetBytes(48))
```

---

## 3. 第三步 · 一键部署 backend + SCF（5 分钟）

**Windows PowerShell**：
```powershell
cd deploy\cn-serverless
.\deploy.ps1
```

**macOS / Linux / Git-Bash**：
```bash
cd deploy/cn-serverless
bash deploy.sh
```

脚本会：
1. 自动安装 `@cloudbase/cli` + `serverless` 全局
2. 用 AKSK 登录腾讯云
3. 把 `Dockerfile.serverless` 推到 CloudBase 云托管，自动构建 + 部署（首次约 5 分钟）
4. 部署完成后打印 `BACKEND_URL`（形如 `https://xyq-backend-1234-1300000000.ap-shanghai.run.tcloudbase.com`）
5. 自动把 BACKEND_URL + INTERNAL_API_SECRET 注入 SCF，部署定时函数
6. 烟雾测试 `/api/health` 和 `/api/internal/worker/tick`

**首次部署完，回到 `.env` 把 `BACKEND_URL` 真实地址填上**，方便下次部署/调试。

---

## 4. 第四步 · 部署前端到 EdgeOne Pages（3 分钟，纯点点点）

EdgeOne CLI 当前不稳定，**控制台导入更省事**：

1. 入口：https://console.cloud.tencent.com/edgeone/pages
2. **新建项目** → **导入 Git 项目** → 选 GitHub → 授权后选 `bistuwangqiyuan/ai-manju-xiaoyunque`
3. 配置：
   | 字段 | 值 |
   |---|---|
   | 框架预设 | **Next.js** |
   | 根目录 | `web` |
   | 构建命令 | `npm run build` |
   | 输出目录 | `.next` |
   | 安装命令 | `npm install` |
4. **环境变量**：
   - `NEXT_PUBLIC_BACKEND_URL` = 第 3 步拿到的 `BACKEND_URL`
   - `NEXT_PUBLIC_DEFAULT_LOCALE` = `zh-CN`
5. **开始部署** → 1-2 分钟拿到 `*.edgeone.app` 域名

> ✨ EdgeOne 每次 GitHub `git push origin main` 都会自动重建发布，全自动 CI/CD。

---

## 5. 第五步 · 三件配置（让前后端联通）

### 5a. 把 EdgeOne 域名加到 backend CORS

进入 CloudBase 控制台 → 云托管 → `xyq-backend` 服务 → 配置 → 环境变量，
追加 / 修改：

```
CORS_ORIGINS=https://your-project.edgeone.app
SITE_URL=https://your-project.edgeone.app
```

点保存 → 自动重启（约 30s）。

### 5b. 域名解析（可选）

EdgeOne 控制台 → 项目 → 自定义域名 → 添加 `manju.example.com` → 复制 CNAME → 到域名厂商加 CNAME 解析。

### 5c. PostgreSQL 内网授权

PostgreSQL 控制台 → 实例 → 安全组 → 加白 CloudBase 出网段（控制台一键添加）。

---

## 6. 验证上线（1 分钟）

```powershell
# 后端 health
Invoke-RestMethod https://xyq-backend-xxxx.run.tcloudbase.com/api/health

# Worker tick (注意要传 X-Internal-Secret)
Invoke-RestMethod https://xyq-backend-xxxx.run.tcloudbase.com/api/internal/worker/tick `
  -Method Post -ContentType 'application/json' `
  -Headers @{'X-Internal-Secret'='你的 INTERNAL_API_SECRET'} `
  -Body '{"max_jobs":1}'

# 前端
Start-Process https://your-project.edgeone.app
```

注册一个测试账号，点 "创建漫剧" → 等约 60s（SCF 下次 tick 触发）→ 在 "我的作品" 看到任务推进到 100%，即上线成功 🎉

---

## 7. 日常运维

### 看日志
- **Backend (CloudBase)**：控制台 → 云托管 → xyq-backend → 日志（实时流）
- **SCF**：控制台 → 云函数 → xyqWorkerTick → 日志
- **Postgres**：控制台 → PostgreSQL → 实例 → 慢日志

### 升级
GitHub `git push origin main` → EdgeOne 自动重建前端
后端要重新跑 `deploy.ps1` / `deploy.sh`，或：

```bash
tcb framework deploy -e $ENV_ID --config-file deploy/cn-serverless/cloudbaserc.json
```

### 关停（省钱模式）
- CloudBase 云托管：`minNum` 已是 0，闲时自动缩到 0，**无需操作**
- SCF：控制台 → 禁用定时触发器（避免 1 元/月的极低基础费）
- Postgres Serverless：设置 "5 分钟无连接自动暂停"（控制台 → 实例 → 参数）

### 备份
- Postgres 自动每日快照保留 7 天（控制台 → 备份恢复）
- COS 自动多副本，无需操心

---

## 8. 故障排查

| 现象 | 解决 |
|---|---|
| `tcb framework deploy` 报权限不足 | 子账号需要 `QcloudCloudBaseFullAccess` + `QcloudCAMFullAccess` 策略，或直接用主账号 AKSK |
| backend 容器卡在 building | CloudBase 控制台 → 服务 → 版本管理 → 看构建日志，常见是 pip 拉超时（已配清华源仍超时就重试一次） |
| `/api/health` 返回 502 | min=0 冷启动需 5-10s，刷新一下；持续 502 看 CloudBase 日志 |
| Worker tick 报 403 | `INTERNAL_API_SECRET` 没注入或不一致，CloudBase 环境变量和 SCF 环境变量必须**完全相同** |
| 任务一直 queued 不动 | SCF 定时触发器没开启 / 没填正确 BACKEND_URL；到 SCF 控制台手动 "测试" 一次看返回 |
| 前端 cors 报错 | `CORS_ORIGINS` 没加 EdgeOne 真实域名，按 5a 修改 |
| postgres 连接慢 | 5 分钟无连接自动暂停后第一次连接需要约 5s 唤醒，正常现象 |

---

## 9. 成本控制（关键调优）

| 旋钮 | 默认 | 省钱模式 | 性能模式 |
|---|---|---|---|
| CloudBase minNum | 0 | 0 | 1（永远热，¥7.2/天） |
| CloudBase maxNum | 10 | 3 | 50 |
| CloudBase cpu | 0.5 | 0.25 | 1 |
| CloudBase mem | 1 GB | 0.5 GB | 2 GB |
| SCF cron | 60s | 120s | 30s |
| Postgres 最小 CCU | 0.25 | 0 | 1 |
| Postgres 闲时自动暂停 | 5 min | 1 min | 永不 |

---

## 10. 与其它方案对照

| 维度 | 无服务器（本文档） | 轻量服务器（`RUNBOOK_CN.md`） | Railway/Vercel（`RUNBOOK.md`） |
|---|---|---|---|
| 国内访问速度 | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐ |
| 闲时月成本 | ¥0-3 | ¥9-24 (固定) | $0 |
| 满载月成本 | ¥20-110 (随用量) | ¥9-24 (封顶) | $5-20 (随用量) |
| 弹性扩缩 | 自动 (0→10 instance) | 手动 (改配置) | 自动 |
| 部署难度 | 1 个脚本 + 4 次点击 | 1 行命令 | 3 次点击 |
| 冷启动 | 5-10s (第一次/低频) | 无 | 1-2s |
| 数据归属 | 腾讯云 | 完全自主 | Railway+Neon |
| 需要服务器运维 | ❌ 完全无 | ✅ Docker 基础 | ❌ |
| 需要备案 | 用 EdgeOne 自带域名免备案；自定义域名需备案 | 香港节点免备案 | 不需要 |
| 适合 | 国内 ToC、用量波动大、想 PoC | 国内 ToC、稳定高并发 | 海外、个人 demo |

> 三套方案代码完全共享，按需切换。

---

## 附录 A：免备案上线（用 EdgeOne 自带二级域名）

1. EdgeOne 创建项目后自动分配 `xxx.edgeone.app`，**直接可用，无需备案**
2. CloudBase 云托管的 `*.run.tcloudbase.com` 也是免备案
3. 全套不绑自定义域名，**今天买账号今天就能上线**

## 附录 B：备案后绑自定义域名

1. 域名先在腾讯云完成 ICP 备案（约 7-14 天）
2. EdgeOne 项目 → 自定义域名 → 添加 `manju.example.com` → 拿 CNAME → 域名厂商解析
3. EdgeOne 自动签发 SSL 证书（约 1 分钟）
