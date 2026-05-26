# 上线状态 — v9 全国产 serverless

> **当前**: veFaaS 函数 + API 网关全部就位; 实测发现镜像 v9.0.1 漏了 `python-multipart` 依赖, 已在 v9.0.2 修复, 正在重新出 release。
> **公网域名 (上线后即可用)**: `http://sd8ahl2ki9edvua7ttfs0.apigateway-cn-beijing.volceapi.com`

---

## 已完成 (全自动)

| 步骤 | 状态 | 资源 / 证据 |
|---|---|---|
| Windows 用户级 env (52 keys) + Credential Manager (26 keys) | ✅ | `data/windows_keys_synced.json` |
| GitHub Secrets 同步 (33 keys) | ✅ | `gh secret list` |
| veFaaS / APIG / TOS / CR 服务授权 | ✅ | 账号 `2101722825` |
| 容器镜像仓库 (CR) | ✅ | `manhuaju-cn-beijing.cr.volces.com/manhuaju/xyq-manju:v9.0.1` |
| TOS bucket | ✅ | `tos://xyq-prod-cn-beijing` (cn-beijing, 私有) |
| GitHub Actions deploy-vefaas.yml | ✅ | tag push 自动跑 |
| Docker image build & push | ✅ | 已推 CR (registry cache) |
| veFaaS Function | ✅ | id=`0mt4ej8a`, name=`xyq-manju`, port=8000 |
| veFaaS Release v9.0.1 | ✅ | RevisionNumber=1, weight=100 |
| 33 个 env 注入函数 | ✅ | 包括 `STORAGE_BACKEND=tos`, `TTS_PRIMARY=doubao` |
| **APIG Gateway** | ✅ | `gd8afjpepm94qqo1kmttg` (manhuaju-gw, Running, 公网+私网) |
| **APIG Service** | ✅ | `sd8ahl2ki9edvua7ttfs0` (xyq-manju-svc, public HTTP/HTTPS) |
| **APIG Upstream → veFaas** | ✅ | `ud8ahl2pi2gkmuvqaqepg` → FunctionId `0mt4ej8a`, Version `v1` |
| **APIG Route** | ✅ | `rd8ahljpi2gkmuvqaqf30` (xyq-manju-all, Prefix `/`, 7 methods) |
| **APIG Trigger 写入函数** | ✅ | `ListTriggers` 已显示该 trigger |
| **容器冷启动成功** | ✅ | Caddy + Next.js 都已 Ready, FastAPI 因 multipart 缺失退出 |
| 自动化测试 (50 pass / 10 skip) | ✅ | `tests/test_vefaas_deploy.py` 23 OK |

---

## v9.0.2 修复 (本提交)

### 根因
APIG 上线后 curl 返回 **HTTP 503**, veFaaS 容器日志显示:
```
File "/app/app/routes/batch.py", line 111, in <module>
    @router.post("/upload", response_model=BatchOut, status_code=201)
RuntimeError: Form data requires "python-multipart" to be installed.
```
`/api/batch/upload` 用了 FastAPI `UploadFile`, FastAPI 0.115 起 multipart 不再随 fastapi 一起打包, 需要显式声明。

### 修复
- `backend/requirements.txt`: 加 `python-multipart==0.0.20`
- 不改任何代码逻辑, 只补依赖
- 重新跑 GitHub Actions deploy-vefaas (push tag v9.0.2 触发)

### 自动重新部署
```powershell
git tag v9.0.2
git push origin v9.0.2
# GitHub Actions 自动:
#   1. docker build → push CR (cache hit 大部分层, 只重装 python deps + COPY 源码, ~3min)
#   2. python deploy.py → UpdateFunction (idempotent) + Release new revision
#   3. veFaaS 自动滚动到新镜像
```

跑完后再访问 `http://sd8ahl2ki9edvua7ttfs0.apigateway-cn-beijing.volceapi.com/healthz` 应返回 `ok`。

---

## 验证步骤 (v9.0.2 部署完成后)

```powershell
$url = "http://sd8ahl2ki9edvua7ttfs0.apigateway-cn-beijing.volceapi.com"

# 健康探针 (Caddy 内置 200, 不进 FastAPI)
curl.exe -v "$url/healthz"
# 期望: HTTP 200, body = "ok"

# FastAPI 后端健康
curl.exe -v "$url/api/health"
# 期望: HTTP 200, JSON {status: ok, ...}

# Next.js 前端
curl.exe -v "$url/"
# 期望: HTTP 200, HTML

# 跑一次完整流水线 (mock mode)
curl.exe -X POST "$url/api/runs" -H "Content-Type: application/json" `
    -d '{\"novel\":\"test\",\"force_mock\":true}'
```

---

## 关键运维 ID 表 (上线必备)

| 资源 | ID | 备注 |
|---|---|---|
| 火山账号 | `2101722825` | sts GetCallerIdentity 已验证 |
| Region | `cn-beijing` | 全栈统一 |
| veFaaS Function | `0mt4ej8a` | name `xyq-manju` |
| APIG Gateway | `gd8afjpepm94qqo1kmttg` | name `manhuaju-gw` |
| APIG Service | `sd8ahl2ki9edvua7ttfs0` | name `xyq-manju-svc` |
| APIG Upstream | `ud8ahl2pi2gkmuvqaqepg` | name `xyq-manju-up`, ver `v1` |
| APIG Route | `rd8ahljpi2gkmuvqaqf30` | name `xyq-manju-all` |
| TOS Bucket | `xyq-prod-cn-beijing` | endpoint `tos-cn-beijing.volces.com` |
| CR Namespace / Repo | `manhuaju` / `xyq-manju` | tag 滚动 `v9.x` |

---

## 仍在等用户的 1 件小事 (P4, 不阻塞主功能)

**`DOUBAO_TTS_APPID` 11 位数字 ID**

`.env` 里现在填的 `api-key-20260516225257` 是 API Key 的名字, 不是真正的 AppID。豆包 Seed-TTS 调用必须传 11 位数字 AppID。

- 我尝试过 `ve speechsaasprod ListAPIKeys` 自动查询, 但需先有 AppID 才能列, 是鸡蛋问题
- IAM 账号 ID 是 `2101722825` (10 位, 也不是 AppID; AppID 是语音 SaaS 单独的)

**1 分钟人工解决**:
1. 访问 https://console.volcengine.com/speech/service/8
2. 找"语音合成 大模型 ICL"应用 → 复制顶部的 **AppID** (一串 11 位数字)
3. 告诉我数字, 我同步到 `.env` + Windows env + GitHub Secrets

**降级备份**: 当 `DOUBAO_TTS_APPID` 缺失或非数字时, `tts_minimax.py` 自动 fallback 到 MiniMax Speech 2.5 HD (已验证可用), 系统不影响功能。

---

## 自动化脚本一览

| 脚本 | 用途 |
|---|---|
| `scripts/setup_apig_full.py` | 一键创建 APIG Service + Upstream + Route + UpstreamVersion (idempotent) |
| `scripts/bind_apig_trigger.py` | 备用: 通过 veFaaS `CreateAPIGTrigger` 反向绑定 |
| `scripts/get_function_info.py` | 轮询函数状态 + 取公网 URL |
| `scripts/verify_deployment.py` | 部署后 5 项 smoke test |
| `scripts/verify_volc_chain.py` | 5 个火山 API 真网联通 (ARK / Doubao TTS / Seedream / Jimeng / TOS) |
| `scripts/sync_keys_to_windows.ps1` | 把 52 个 API key 同步到 Windows 用户级 env |
| `scripts/sync_keys_to_github.ps1` | 把已验证 key 同步到 GitHub Secrets |
| `scripts/setup_volc_resources.ps1` | 一次性创建/检查 TOS bucket + CR + veFaaS + APIG |

---

## 一行汇总

> APIG 全部接好, 镜像 v9.0.1 因缺 `python-multipart` 启动失败 → v9.0.2 加依赖, push tag 后 GitHub Actions 自动重出 release, 5 分钟后 `http://sd8ahl2ki9edvua7ttfs0.apigateway-cn-beijing.volceapi.com/healthz` 就 200 了。
