# 🚀 极简 Serverless 部署 · 5 分钟上线

> **最简方案** · 无需 Postgres · 无需 COS · 无需 EdgeOne · 无需 SCF
>
> **只需 3 步：注册腾讯云 → 填 3 个字段 → 跑 1 个命令**
>
> 单容器 All-in-One · 闲时自动缩到 0 · 用量爆发 5 instance 自动扩容

---

## 架构（极简版）

```
浏览器
   ↓
*.run.tcloudbase.com (CloudBase 自动分配免备案 HTTPS 域名)
   ↓
┌─────────────────────────────────────────────────┐
│  CloudBase 云托管 · 单容器 (min=0, max=5)        │
│  ┌────────────────────────────────────────────┐ │
│  │ Caddy :8080                                │ │
│  │   ├─ /api/*     → FastAPI :8000 (内置 worker)│
│  │   ├─ /storage/* → FastAPI :8000             │ │
│  │   └─ /*         → Next.js :3000             │ │
│  ├────────────────────────────────────────────┤ │
│  │ SQLite (/data/xyq.db, CFS 持久化可选)       │ │
│  └────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────┘
```

**仅依赖一个腾讯云产品：CloudBase 云开发**。

| 月度成本 | 场景 |
|---|---|
| **¥0** | 闲时（无访问，自动缩到 0） |
| ¥10-30 | 日 100 个视频生成 |
| ¥50-100 | 日 1000 个视频生成 |

---

## 第 1 步 · 注册 + 开通（共 3 分钟）

### 1.1 注册腾讯云（如已注册跳过）
- 入口：https://cloud.tencent.com/register
- 用手机号注册，**完成个人实名认证**（约 1 分钟）

### 1.2 开通 CloudBase 云开发
- 入口：https://console.cloud.tencent.com/tcb
- 点 **"新建环境"** → 选 **"按量计费"** → 区域选 **"上海"** → 名称随便起（例：`xyq-prod`）
- **抄下"环境 ID"**（形如 `xyq-prod-1g123ab456cd`）

### 1.3 创建 API 密钥
- 入口：https://console.cloud.tencent.com/cam/capi
- 点 **"新建密钥"** → 弹出后立即**复制保存**：
  - `SecretId`（**以 `AKID` 开头**，36 字符）
  - `SecretKey`（32 字符随机串）
  > ⚠️ 注意区分：`SecretId` ≠ `AppID`（10 位数字）

---

## 第 2 步 · 填 3 个字段（30 秒）

```powershell
cd deploy\cn-serverless
Copy-Item .env.simple.example .env.simple
notepad .env.simple
```

把刚才的 3 个值填进去：

```env
TENCENT_SECRET_ID=AKIDxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TENCENT_SECRET_KEY=yyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyy
ENV_ID=xyq-prod-1g123ab456cd
```

**其它字段无需填**，脚本会自动生成 / 拼装。

---

## 第 3 步 · 一行命令部署（5-10 分钟）

**Windows PowerShell**：
```powershell
.\deploy_simple.ps1
```

**macOS / Linux / Git-Bash**：
```bash
bash deploy_simple.sh
```

脚本自动：

1. ✅ 校验 3 个必填字段（提示 ID/KEY 是否填反）
2. ✅ 安装 `@cloudbase/cli`（如未装）
3. ✅ 登录腾讯云
4. ✅ 生成 `JWT_SECRET` + `INTERNAL_API_SECRET`（48 字节随机）
5. ✅ 推送 `Dockerfile.allinone` 到 CloudBase（首次构建 5-10 分钟，含 Next.js + Python + Caddy + ffmpeg）
6. ✅ 获取自动分配的 `*.run.tcloudbase.com` 域名
7. ✅ 烟雾测试 `/api/health`
8. ✅ 浏览器自动打开

部署完成后，你会看到：
```
访问地址: https://xyq-xxxxx-1300000000.ap-shanghai.run.tcloudbase.com
/api/health: {"status":"ok","mock_worker":true,"mock_billing":true}
```

**完工！** 可以开始注册账号、提交漫剧任务了。

---

## 接下来你可能想做的事（全部可选）

### 持久化数据库（防止重启丢数据）

默认 SQLite 在容器 `/data` 临时盘，**重启会丢**。生产环境建议挂载 CFS：

1. 控制台 → 云托管 → `xyq` 服务 → **配置** → **持久化存储**
2. 点 **"添加 CFS"** → 创建文件系统 → 挂载路径填 `/data`
3. 触发一次重新部署 → SQLite 数据从此持久化

成本：CFS 通用型约 **¥0.35/GB·月**，1 GB 一年 ¥4.2。

### 绑定自定义域名

1. 你的域名先在腾讯云完成 **ICP 备案**（个人约 7-14 天）
2. 控制台 → 云托管 → `xyq` → **自定义域名** → 添加
3. 复制 CNAME → 到域名 DNS 商加 CNAME 记录
4. 等 1 分钟，HTTPS 证书自动签发

### 填真实 AI Keys

控制台 → 云托管 → `xyq` → **环境变量**，找到这些行并填值：

| Key | 申请入口 | 推荐 |
|---|---|---|
| `VOLC_ARK_API_KEY` | https://console.volcengine.com/ark | ⭐ 最便宜 ¥0.01/千 tokens |
| `ANTHROPIC_API_KEY` | https://console.anthropic.com 或国内中转 | 剧本质量最高 |
| `DEEPSEEK_API_KEY` | https://platform.deepseek.com | 国产，便宜 |
| `DOUBAO_API_KEY` | https://www.volcengine.com/product/doubao | 视觉评分 |

填完保存，服务自动重启（约 30 秒）。

### 升级到最新代码

```powershell
git pull
cd deploy\cn-serverless
.\deploy_simple.ps1
```

CloudBase 会重新构建 + 滚动部署，零停机。

---

## 故障排查

| 现象 | 解决 |
|---|---|
| `ERROR: 缺少 .env.simple` | 先 `Copy-Item .env.simple.example .env.simple` 再编辑 |
| `[警告] TENCENT_SECRET_ID 不以 AKID 开头` | 你把 ID/KEY 填反了；SecretId 形如 `AKIDxxxx` 36 字符，SecretKey 是 32 字符随机串 |
| `tcb: command not found` | `npm i -g @cloudbase/cli@latest`（脚本会自动装，如失败手动执行） |
| `tcb login` 报权限 | 子账号需 `QcloudCloudBaseFullAccess` 策略；最简：用主账号 AKSK |
| `tcb framework deploy` 卡在 build | CloudBase 控制台 → 云托管 → xyq → 版本管理 → 看构建日志（常见超时再重试一次） |
| `/api/health` 502 | min=0 冷启动需 10-20s；多刷几次。持续 502 看容器日志 |
| 重启后数据没了 | SQLite 在 `/data` 临时盘，按上面"持久化数据库"挂 CFS |

---

## 与原方案对照

| 项 | 极简版（本文档） | 分件版（`RUNBOOK_CN_SERVERLESS.md`） |
|---|---|---|
| 腾讯云服务 | **只 1 个**（CloudBase） | 4 个（CloudBase + Postgres + COS + EdgeOne） |
| 必填字段 | **3 个** | 6 个 |
| 部署命令 | `.\deploy_simple.ps1` | `.\deploy.ps1` + EdgeOne 控制台导入 |
| 总用时 | **5 分钟** | 15 分钟 |
| 单容器规格 | 1 CPU / 2GB | 0.5 CPU / 1GB |
| 闲时月费 | ¥0 | ¥0-3 |
| 数据持久化 | 默认临时盘（可挂 CFS） | 独立 Postgres（数据更安全） |
| 边缘 CDN | 没有 | EdgeOne 全国边缘 |
| 适合 | MVP / PoC / 小流量 | 中大流量 / 多区域 |

> 两套配置共存，按需切换。先用极简版上线验证业务，长期再迁分件版。
