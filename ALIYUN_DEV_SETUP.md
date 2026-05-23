# 阿里云开发环境 · 一键配置 + 速查

> 已为你装好 **2 个 CLI + 5 个 MCP**，让你和 Cursor AI 直接用自然语言操作阿里云所有服务。
> 与已有的火山引擎 `VOLC_DEV_SETUP.md` 是同一套架构。

## 📦 已交付清单

### CLI 工具（命令行）
| 工具 | 路径 | 版本 | 作用 |
|---|---|---|---|
| `aliyun` | `~/.aliyun-tools/aliyun.exe` | 3.3.15 | 阿里云统一 CLI，覆盖 **数千个 OpenAPI**（ECS/OSS/RDS/FC/SLS/DashScope/…） |
| `ossutil` | `~/.aliyun-tools/ossutil.exe` | 2.3.0 | OSS 对象存储专用 CLI，批量上传/下载/同步 |

两者均已加入 USER PATH，**新开 PowerShell 直接可用**。

### Cursor MCP 服务器（让 AI 直接操作）
配置在 `.cursor/mcp.json`，**Reload Cursor 即生效**。

| MCP | 用途 | 实现 |
|---|---|---|
| **`aliyun-ops`** ★ | CloudOps 旗舰 — ECS/OSS/VPC/RDS/CloudMonitor/OOS 全管，可部署应用到 ECS | `uvx alibaba-cloud-ops-mcp-server` |
| **`aliyun-rds`** | RDS OpenAPI — MySQL / PG / SQLServer 实例管理 | `uvx alibabacloud-rds-openapi-mcp-server` |
| **`aliyun-fc`** | 函数计算 FC3.0 — serverless 函数 + 触发器（国内对标 AWS Lambda） | `uvx alibabacloud-fc-mcp-server` |
| **`aliyun-observability`** | SLS 日志 + CMS 云监控 — 排查线上问题 | `uvx alibabacloud-observability-mcp-server` |
| **`aliyun-bailian-websearch`** | 百炼联网搜索 — 给 AI 实时网络访问能力 | streamable-http (无需 AKSK，仅 DashScope key) |

> 💡 **想加更多？** 阿里云 [MCP 广场](https://bailian.console.aliyun.com/?tab=mcp) + GitHub [aliyun org](https://github.com/aliyun?q=mcp) 还有：
> DMS / ADBPG / Tablestore / DataWorks / 云效 DevOps / 容器 ACK / API Gateway / ESA / OpenAPI 全量（`api.aliyun.com/mcp` 托管 SSE）。
> 都用同样的 `uvx <pkg>@latest` 调用模式。

---

## 🚀 一键配置（30 秒）

```powershell
# Windows
pwsh scripts/setup_aliyun_mcp.ps1
```
```bash
# macOS / Linux / Git-Bash
bash scripts/setup_aliyun_mcp.sh
```

脚本会：
1. **校验** `aliyun` / `ossutil` / `uv` 是否就位
2. **自动读取**项目里已有的 `.env` 中的：
   - `ALIBABA_CLOUD_ACCESS_KEY_ID` / `ALIYUN_ACCESS_KEY_ID`
   - `ALIBABA_CLOUD_ACCESS_KEY_SECRET` / `ALIYUN_ACCESS_KEY_SECRET`
   - `DASHSCOPE_API_KEY`
   - `OSS_BUCKET` / `OSS_ENDPOINT` / `OSS_REGION`
3. **填空补全** — 找不到就交互式让你粘贴
4. **写入** `.cursor/mcp.json` 的 5 个 MCP env / header
5. **配置** `aliyun configure set --profile default --mode AK`（你的"永久登录"）
6. **配置** `ossutil config -e ENDPOINT -i AK -k SK`

跑完后 **Cursor → Reload Window**，5 个 MCP 自动加载。

---

## 🔑 拿凭证（如果 .env 里还没填）

| 凭证 | 入口 | 形式 |
|---|---|---|
| **AccessKey + Secret** | https://ram.console.aliyun.com/manage/ak | AK: `LTAI...` 24 字符; SK: 30 字符 |
| **DashScope (百炼) Key** | https://bailian.console.aliyun.com/?tab=model#/api-key | `sk-xxx` UUID |
| **OSS 桶名** | https://oss.console.aliyun.com/bucket | 桶列表里复制 |

> ⚠️ **安全提示**: 推荐用 **RAM 子账号** 而非主账号 AK，并在 RAM 控制台为该子账号挂上最小权限策略（如 `AliyunECSFullAccess` / `AliyunOSSFullAccess` / `AliyunRDSReadOnlyAccess`）。

---

## 💬 Cursor 里这样调（实战示例）

Reload Cursor 后，对 AI 直接说：

### 计算 / 容器
- "用 aliyun-ops 列出杭州地域所有 ECS 实例"
- "用 aliyun-ops 创建一台 2c4g 的 ecs.t6 实例，跑 Ubuntu 22.04，放 vpc-xxx 里"
- "用 aliyun-ops 把 `master.mp4` 部署到 ECS i-bp1xxx 上跑（自动建应用组）"

### 存储
- "用 aliyun-ops 列出 `xyq-prod` 桶里今天上传的 mp4"
- "用 aliyun-ops 创建一个 cn-hangzhou 的 OSS 桶，开 CDN 加速"

### 数据库
- "用 aliyun-rds 列出我的 RDS MySQL 实例，按 CPU 排序"
- "用 aliyun-rds 重启 rm-bp1xxx 这个实例"

### Serverless
- "用 aliyun-fc 部署 worker_tick.py 为定时函数（每分钟跑一次）"
- "用 aliyun-fc 看 `xyq-worker` 函数最近 100 行日志"

### 监控 / 日志
- "用 aliyun-observability 查 SLS `xyq-logs` 项目 过去 1 小时所有 ERROR 级日志"
- "用 aliyun-observability 看 i-bp1xxx ECS 的 CPU 是否超过 80%"

### 百炼联网搜索
- "用 aliyun-bailian-websearch 帮我查最新的 AIGC 视频生成法规"

---

## ⌨️ 命令行速查（你刚要的"永久使用"路径）

### 1. `aliyun` CLI —— 数千个 OpenAPI 直调

```powershell
# 登录 / 配置（脚本已自动跑；手动方式）
aliyun configure set --profile default --mode AK --region cn-hangzhou `
                     --access-key-id LTAI... --access-key-secret xxx

# 看当前配置 / 切 profile
aliyun configure list
aliyun configure switch --profile prod    # 切到另一个 profile

# 通用格式: aliyun <product> <action> --key value
aliyun ecs DescribeRegions
aliyun ecs DescribeInstances --RegionId cn-hangzhou
aliyun rds DescribeDBInstances --RegionId cn-hangzhou
aliyun oss ls oss://xyq-prod
aliyun fc-open ListServices                      # FC 2.0
aliyun fc3 ListFunctions                         # FC 3.0
aliyun sls GetLogs --project xyq-logs --logstore app --topic "" --from <ts> --to <ts>
aliyun dashscope CreateCompletion --Model qwen-max --Input "你好"

# 看某个 product/action 的参数
aliyun ecs DescribeInstances help

# 自动补全
aliyun auto-completion           # 启用 bash 补全
```

### 2. `ossutil` —— OSS 专用，比 `aliyun oss` 更强

```powershell
# 看版本 / 帮助
ossutil version
ossutil --help

# 列桶
ossutil ls
ossutil ls oss://xyq-prod -d           # 目录形式

# 上传（断点续传 + 多线程）
ossutil cp data\runs\v2_smoke\06_final\master.mp4 oss://xyq-prod/episodes/ep01.mp4

# 批量同步（增量）
ossutil cp -r data/runs/ oss://xyq-prod/runs/ -u

# 下载
ossutil cp oss://xyq-prod/episodes/ep01.mp4 .\local.mp4

# 自动续传
ossutil cp largefile.zip oss://xyq-prod/ --checkpoint-dir .\cp

# 删
ossutil rm oss://xyq-prod/old/ -r -f

# 给文件签个临时分享 URL（24 小时）
ossutil sign oss://xyq-prod/master.mp4 --timeout 86400

# 测速
ossutil probe --upload-speed oss://xyq-prod/
ossutil probe --download-speed oss://xyq-prod/master.mp4
```

### 3. 项目里集成 OSS（已支持 S3-兼容 API）

`backend/app/storage_upload.py` 已用 boto3 调对象存储，OSS 改 `.env`：

```env
S3_BACKEND=oss
S3_ENDPOINT=https://oss-cn-hangzhou.aliyuncs.com
S3_REGION=cn-hangzhou
S3_BUCKET=xyq-prod
S3_ACCESS_KEY=LTAI...
S3_SECRET_KEY=xxx
S3_PUBLIC_BASE_URL=https://xyq-prod.oss-cn-hangzhou.aliyuncs.com
```

worker 渲完 mp4 会自动 PUT 到 OSS，URL 写回 DB。

---

## 🛠️ 故障排查

| 现象 | 解决 |
|---|---|
| `aliyun` 命令找不到 | 重开 PowerShell（USER PATH 仅新会话生效），或 `$env:Path += ";$env:USERPROFILE\.aliyun-tools"` |
| `aliyun configure list` 显示 Profile 空 | 重跑 setup 脚本；或手动 `aliyun configure set --profile default --mode AK ...` |
| MCP 在 Cursor 灰色 / 报红 | Reload Window；查 `.cursor/mcp.json` 合法 JSON；env 是否填了 AKSK |
| `uvx` 首次启动慢 | 拉源码 + 装依赖（~60s）；之后缓存到 `~\AppData\Local\uv\cache`，秒级 |
| `aliyun ecs ...` 报 403/forbidden | RAM 子账号缺权限；去控制台挂上对应策略（如 `AliyunECSFullAccess`） |
| `ossutil cp` 报 SignatureDoesNotMatch | endpoint 区域写错；用 `ossutil config --reset` 重配 |
| 百炼 MCP 在 Cursor 失败 | `Authorization: Bearer sk-xxx` 必须是 **百炼 API Key** 而非 ECS 控制台的 AccessKey |

---

## 🏛️ 项目中阿里云的最佳实践

| 场景 | 用法 |
|---|---|
| **视频/封面存储** | OSS 桶（已支持 S3 兼容）→ 推荐绑 CDN |
| **数据库** | RDS PG/MySQL Serverless 或 PolarDB Serverless |
| **Serverless worker** | FC3.0 函数 + EventBridge cron 触发（替代 deploy/cn-serverless 的腾讯 SCF） |
| **日志聚合** | SLS 接 stdout（FC 内置开关）；查询用 `aliyun-observability` MCP |
| **图像生成** | DashScope 接 Wan 2.2-Animate / 通义万相（项目 Phase 2 已接入） |
| **文本 LLM** | DashScope 通义 (qwen-max-latest) — Phase 2 LLM 后备链已含 |

---

## 📚 完整命令文档
- aliyun CLI: https://help.aliyun.com/zh/cli/
- ossutil: https://help.aliyun.com/zh/oss/developer-reference/ossutil-overview/
- 官方 MCP 列表: https://github.com/aliyun?q=mcp
- 百炼 MCP 广场: https://bailian.console.aliyun.com/?tab=mcp
- OpenAPI 全量 MCP 托管: https://api.aliyun.com/mcp
