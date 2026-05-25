# 小云雀 AI 漫剧 — 火山引擎 veFaaS 一页 Runbook

> 目标：从零把整套系统部署到 **火山引擎 veFaaS + API 网关 + TOS + (可选) NAS**，5 步走完。
> 估时：**首次约 25 分钟**，后续迭代部署 **3 分钟**。

## 架构 (v9)

```
用户浏览器
    │   HTTPS
    ▼
API 网关 (veapig.volcengine.com)
    │   反代
    ▼
veFaaS 函数 (xyq-manju, 单容器 :8000)
    ├─ Caddy   :8000  反代
    ├─ FastAPI :8001  + embedded worker
    ├─ Next.js :3000  standalone
    └─ ffmpeg
    │
    ├──→ TOS  (xyq-prod 桶, 视频/封面/素材)
    ├──→ NAS  (/mnt/nas/xyq, SQLite + storage 兜底)
    │
    └──→ 火山 API (ARK / Seedream / Doubao TTS / 短剧漫剧 Agent)
         + 阿里 DashScope (Qwen / Wan-Animate)
         + LLM Fallback Chain (DeepSeek / GLM / 通义 ...)
```

## 你需要做的 4 步（一次性）

### 步骤 1 — 开通服务（5 分钟）

打开下面 3 个控制台，每个页面都会弹"一键授权"，点同意：

| 服务 | 控制台链接 | 用途 |
|---|---|---|
| **veFaaS** | https://console.volcengine.com/vefaas | 函数计算（部署目标） |
| **API 网关** | https://console.volcengine.com/veapig | 公网域名 + 路由 |
| **容器镜像仓库 CR** | https://console.volcengine.com/cr | docker push 目标 |
| **TOS** | https://console.volcengine.com/tos | 对象存储（主存储） |
| **NAS**（可选） | https://console.volcengine.com/nas | 文件存储（SQLite 持久化） |

### 步骤 2 — 创建 TOS bucket（2 分钟）

- 控制台 → TOS → 创建桶
- 名称：`xyq-prod-cn-beijing`（必须全局唯一，按需改）
- 区域：`华北 2（北京）`
- 访问权限：**私有**（推荐；或 `公共读` 如要直链）
- 复制 bucket 名字到 `.env`：`TOS_BUCKET=xyq-prod-cn-beijing`

> 也可以让脚本帮你建：`.\scripts\setup_volc_resources.ps1 -CreateBucket`

### 步骤 3 — 创建容器镜像仓库命名空间（1 分钟）

- 控制台 → 容器镜像仓库 → 创建实例（如无 → 选**免费版**）
- 创建命名空间：`xyq`
- 创建镜像仓库：`manju`（属于命名空间 `xyq`）
- 完整地址将是：`cr-cn-beijing.volces.com/xyq/manju`

### 步骤 4 — (可选) 创建 NAS 文件系统（3 分钟）

如果你想 **SQLite 数据库重启不丢**（推荐）：

- 控制台 → NAS → 创建文件系统
- 类型：**通用型** 或 **容量型**（容量型更便宜）
- 区域：`华北 2（北京）`（必须与 veFaaS 同区域）
- 协议：**NFS v3**
- 创建挂载点 → 复制 NAS ID 到 `config.yaml` 的 `nas_mounts[0].nas_id`

> 不挂 NAS 也能跑！SQLite 会写到容器临时盘，重启会丢，但 TOS 主存储不丢。
> 适合 PoC / 演示；正式生产强烈建议挂 NAS。

## 我（脚本）帮你做的 1 步

```powershell
# 在仓库根跑 (Windows)
.\deploy\cn-volc-vefaas\deploy.ps1
```

```bash
# macOS / Linux
./deploy/cn-volc-vefaas/deploy.sh
```

脚本会自动：

1. 从 Windows 全局存储读 25 个 API Key（`VOLC_ACCESS_KEY/SECRET_KEY/...`）
2. `docker build` → `docker push cr-cn-beijing.volces.com/xyq/manju:v9.xxx`
3. 调火山 OpenAPI `Action=CreateFunction&Version=2024-06-06` 创建函数
4. 调 `Action=CreateRelease` 发布版本
5. (若配了 API 网关) 调 `Action=CreateRoute` 拉公网域名
6. 输出 `https://<domain>/api/health`

## 验证部署成功

```powershell
# 替换为实际域名
$base = "https://xyq-manju-xxx.apigw-cn-beijing.volces.com"

curl "$base/api/health"           # 期望 {"status":"ok"}
curl "$base/api/version"          # 期望 {"version":"v9.x.x"}
curl "$base/api/runs" -X POST `
  -H "Content-Type: application/json" `
  -d '{"theme":"测试", "episodes":1, "mock":true}'   # mock 模式完整流水线
```

## 常见问题

### Q1: `docker push` 401 Unauthorized?

```powershell
docker login cr-cn-beijing.volces.com -u $env:VOLC_ACCESS_KEY -p $env:VOLC_SECRET_KEY
```

火山 CR 的临时 token 24h 过期；同一台机器一次登录就行。

### Q2: 函数启动卡在 "in_queue"?

- 检查镜像架构必须是 `linux/amd64`（Docker Desktop on M1/M2 默认 arm64！）
- veFaaS 默认 cold-start 8-15s；首次拉镜像可能 30-60s

### Q3: 公网访问 404?

- 确认 API 网关路由已创建：控制台 → API 网关 → 路由列表
- 确认上游（Upstream）指向你的 veFaaS 函数 ID
- Caddy 监听 8000 端口，必须与 OpenAPI `Port: 8000` 一致

### Q4: TOS 上传 403?

- 检查 `VOLC_ACCESS_KEY` 对应的 IAM 用户已授权 `TOSFullAccess`
- 检查 `TOS_BUCKET` 区域与 `TOS_ENDPOINT` 区域一致

### Q5: 想回滚到上一版?

```powershell
# 拉最近 5 个 release id
curl "https://open.volcengineapi.com/?Action=ListReleases&Version=2024-06-06&FunctionId=xyq-manju" `
  -H "Authorization: ..."

# 切流量到老版本 (控制台一键回滚最直观)
# 控制台 → veFaaS → 函数 → 版本管理 → 选老版本 → "切流量"
```

## 双轨保留

- `deploy/cn-serverless/` 是 **腾讯 CloudBase** 部署套件（保留作 fallback）
- `deploy/cn-volc-vefaas/` 是 **火山 veFaaS** 部署套件（主线，推荐）

两套互不冲突，可同时存在。
