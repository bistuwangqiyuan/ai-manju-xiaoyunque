# 火山引擎开发环境 · 一键配置 + 速查

> 已为你装好 **2 个 CLI + 6 个 MCP**，让你和 Cursor AI 直接用自然语言操作火山引擎所有服务。

## 📦 已交付清单

### CLI 工具（命令行）
| 工具 | 路径 | 版本 | 作用 |
|---|---|---|---|
| `ve` | `~/.volc-tools/ve.exe` | 1.0.43 | 火山引擎统一 CLI，覆盖 100+ 云服务（ECS、TOS、Ark、CDN、…） |
| `tosutil` | `~/.volc-tools/tosutil.exe` | 4.1.7 | 对象存储专用 CLI，批量上传/下载/同步 |

两者均已加入 USER PATH，**新打开的 PowerShell 直接可用**。

### Cursor MCP 服务器（让 AI 直接操作）
配置在 `.cursor/mcp.json`，**Reload Cursor 即生效**。

| MCP | 用途 | 项目场景 |
|---|---|---|
| `volc-tos` | TOS 对象存储 | 列/上传/下载/搬迁视频、封面、字幕 |
| `volc-vefaas` | 函数计算 + 触发器 | 管理 serverless worker 函数生命周期 |
| `volc-cdn` | CDN 智能分析 | 看带宽、缓存命中、热点 URL |
| `volc-imagex` | 智能图片 | 封面压缩、水印、AIGC 标识 |
| `volc-seedream` | Doubao Seedream 4.5 文生图 | 角色立绘、分镜参考图 |
| `volc-jimeng` | 即梦 4.0 文生图（方舟直连） | 高质量素材生成 |

> 💡 **想加更多？** 火山引擎 [MCP Marketplace](https://www.volcengine.com/mcp-marketplace) 还有 100+ MCP（RDS、Redis、MongoDB、VKE 等），都用同一种 `uvx --from git+...#subdirectory=server/mcp_server_xxx` 方式装。

---

## 🚀 一键配置（30 秒）

```powershell
# Windows
pwsh scripts/setup_volc_mcp.ps1
```
```bash
# macOS / Linux / Git-Bash
bash scripts/setup_volc_mcp.sh
```

脚本会：
1. **校验** `ve` / `tosutil` / `uv` / `npx` 是否就位
2. **自动读取**项目里已有的 `.env` / `backend/.env` / `deploy/cn-serverless/.env*` 中的：
   - `VOLC_ACCESS_KEY` / `VOLC_AK`
   - `VOLC_SECRET_KEY` / `VOLC_SK`
   - `VOLC_ARK_API_KEY` / `ARK_API_KEY`
   - `S3_BUCKET` / `TOS_BUCKET`
3. **填空补全** — 找不到就交互式让你粘贴
4. **写入** `.cursor/mcp.json` 的 6 个 MCP 的 env 字段
5. **配置** `ve` CLI（profile=default, region=cn-beijing）
6. **配置** `tosutil`（endpoint=tos-cn-beijing.volces.com）

跑完后 **Cursor → 右上角 Reload Window**，6 个 MCP 自动加载。

---

## 🔑 拿凭证（如果 .env 里还没填）

| 凭证 | 入口 | 形式 |
|---|---|---|
| AccessKey + SecretKey | https://console.volcengine.com/iam/keymanage | AK: `AKLT...` 24 字符; SK: 40 字符 |
| 方舟 ARK API Key | https://console.volcengine.com/ark/region:ark+cn-beijing/apiKey | UUID |
| TOS 桶名 | https://console.volcengine.com/tos | 桶列表里复制 |

---

## 💬 Cursor 里这样调（实战示例）

Reload 后，直接对 Cursor AI 说：

### TOS 对象存储
- "用 volc-tos 列出 `xyq-prod` 桶里所有 `.mp4`"
- "把本地 `data/runs/v2_smoke/06_final/master.mp4` 用 volc-tos 上传到 `xyq-prod/episodes/ep01.mp4`，并返回访问 URL"
- "用 volc-tos 把过期 30 天的 mp4 全部删掉"

### 函数服务
- "用 volc-vefaas 列出我所有的函数"
- "用 volc-vefaas 查看 `xyq-worker-tick` 函数最近 100 行日志"
- "用 volc-vefaas 把 `xyq-worker-tick` 的内存改到 256MB"

### CDN
- "用 volc-cdn 查 `xyq.example.com` 过去 24 小时的带宽峰值"
- "用 volc-cdn 列出缓存命中率低于 90% 的 URL"

### 智能图片
- "用 volc-imagex 把 `episodes/ep01.mp4` 的第 1 帧抽出来生成 720x1280 封面 webp"

### Seedream / 即梦 文生图
- "用 volc-seedream 生成一张古风女子立绘，白衣，朱砂痣，4K"
- "用 volc-jimeng 一次出 5 张分镜参考图：洞穴入口 + 桃花林 + 月下小桥"

---

## ⌨️ 命令行速查

### 1. `ve` —— 火山引擎统一 CLI（最常用）

```powershell
# 通用格式
ve <service> <action> [--params ...]

# 列服务
ve --help                          # 看所有支持的服务
ve ark --help                      # 方舟 (Doubao/Skylark) 子命令
ve tos --help                      # TOS 子命令
ve vefaas --help                   # 函数服务

# 实战
ve tos list-buckets                # 列所有 TOS 桶
ve ark list-models                 # 列方舟可用模型
ve vefaas list-functions           # 列函数

# 切换 profile / region
ve configure list                  # 看当前配置
ve configure set --profile prod --ak XXX --sk YYY --region cn-shanghai
```

### 2. `tosutil` —— 对象存储专用，比 ve tos 更强

```powershell
# 配置（脚本已自动做; 手动配置参考）
tosutil config -i AK -k SK -e tos-cn-beijing.volces.com -re cn-beijing

# 列桶
tosutil ls tos://

# 列桶内对象
tosutil ls tos://xyq-prod -d

# 上传单文件
tosutil cp data\runs\v2_smoke\06_final\master.mp4 tos://xyq-prod/episodes/ep01.mp4

# 批量同步整个目录（增量）
tosutil cp -r data/runs/ tos://xyq-prod/runs/ -u

# 下载
tosutil cp tos://xyq-prod/episodes/ep01.mp4 .\local.mp4

# 测网速（自己测一下国内→TOS 带宽）
tosutil probe                       # 上传
tosutil probe -pt download          # 下载

# 计算大小
tosutil du tos://xyq-prod
```

### 3. 项目里集成 TOS（已支持）

`backend/app/storage_upload.py` 已用 **S3 兼容 API**（boto3）调 TOS，
只要在 `.env` 填：

```env
S3_ENDPOINT=https://tos-cn-beijing.volces.com
S3_REGION=cn-beijing
S3_BUCKET=xyq-prod
S3_ACCESS_KEY=AKLT...
S3_SECRET_KEY=xxx
S3_PUBLIC_BASE_URL=https://xyq-prod.tos-cn-beijing.volces.com
```

worker 渲染完 mp4 会自动上传到 TOS，并把 URL 写回 DB。

---

## 🛠️ 故障排查

| 现象 | 解决 |
|---|---|
| `ve` 命令找不到 | 关闭 PowerShell 重新打开（USER PATH 仅新会话生效），或手动 `$env:Path += ";$env:USERPROFILE\.volc-tools"` |
| `ve --version` 报 0/缺少 | 老版本，下载 https://github.com/volcengine/volcengine-cli/releases 最新 win amd64 |
| MCP 在 Cursor 里灰色 / 报红 | Reload Window；检查 `.cursor/mcp.json` 是否合法 JSON；env 是否真有 AKSK |
| `uvx` 首次启动慢 | 走 GitHub 拉源码 + 编译依赖；之后会缓存在 `~\AppData\Local\uv\cache`，秒级 |
| 即梦/Seedream MCP 报 "ARK_KEY 无效" | 必须开通方舟服务 + 在控制台开启对应模型；普通账号默认未开 |
| tosutil 上传 403 | 桶 ACL 是私有的；要么改桶策略，要么用 `-acl public-read` |

---

## 📊 国内 MCP 完整目录（参考）

```
volc-marketplace 全部 100+ MCP 都用同一种调用：

uvx --from "git+https://github.com/volcengine/mcp-server#subdirectory=server/mcp_server_<NAME>" <ENTRY>

# 已为你预装的:
mcp_server_tos        →  TOS                   (volc-tos)       ✅
mcp_server_vefaas_function → veFaaS            (volc-vefaas)    ✅
mcp_server_cdn        →  CDN                   (volc-cdn)       ✅
mcp_server_veimagex   →  ImageX                (volc-imagex)    ✅

# 项目可按需追加的:
mcp_server_ark        →  方舟管理              ve ark 已能用
mcp_server_ecs        →  云服务器
mcp_server_rds_mysql  →  RDS MySQL
mcp_server_mongodb    →  MongoDB
mcp_server_redis      →  Redis
mcp_server_vke        →  K8s
mcp_server_vod        →  视频点播 (剪辑)
mcp_server_live       →  直播
mcp_server_tls        →  日志服务
mcp_server_apmplus    →  APM
mcp_server_billing    →  账单
mcp_server_iam        →  访问控制
mcp_server_certificate_center → 证书
mcp_server_domain_service → 域名
# 完整 100+ 列表: https://github.com/volcengine/mcp-server
```

加新 MCP 只需在 `.cursor/mcp.json` 复制一个块 + 改包名即可。

---

## 🎯 与项目集成的最佳实践

1. **生成视频后自动上传 TOS** → `backend/app/worker.py` 调 `storage_upload.upload_if_configured()`（已支持）
2. **VOD 智能剪辑** → 装 `volc-vod` MCP，对 AI 说 "用 vod 把 ep01.mp4 截 30 秒精彩片段做营销素材"
3. **Serverless 部署用 veFaaS** → 已配 MCP，可直接用 AI 对话部署 SCF 函数（不用 console）
4. **图片资产生成用 Seedream/即梦** → AI 直接出图，再用 ImageX MCP 后处理水印

---

完整命令文档：
- ve CLI: https://www.volcengine.com/docs/83927
- tosutil: https://www.volcengine.com/docs/6349/152742
- MCP 广场: https://www.volcengine.com/mcp-marketplace
