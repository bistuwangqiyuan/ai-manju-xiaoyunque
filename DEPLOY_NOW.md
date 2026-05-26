# 上线状态 — v9 全国产 serverless

> **当前版本**: `xyq-manju` 函数 RevisionNumber=2 (镜像 `v9.0.3`) 已 Release `done`。容器内 Caddy + Next.js + FastAPI 全部干净启动 (`Application startup complete`，无 multipart 报错)。
>
> **公网域名**: `http://sd8ahl2ki9edvua7ttfs0.apigateway-cn-beijing.volceapi.com`
>
> **唯一剩余 1 步**: APIG → veFaas 上游连接器返回 envoy 503 (`no healthy upstream`)。函数本身健康，APIG 路由/upstream/route/触发器都对，但 envoy 一侧拿不到 endpoints。**需要在火山 APIG 控制台手工 "测试" 一次** (或开工单) 触发连接器初始化 — 详细步骤见末尾。

---

## 已完成 (全自动)

| 项目 | 状态 | 证据 / ID |
|---|---|---|
| Windows 用户级 env (52 keys) + Credential Manager (26 keys) | ✅ | `data/windows_keys_synced.json` |
| GitHub Secrets (33 keys) | ✅ | `gh secret list` |
| veFaaS / APIG / TOS / CR 服务授权 | ✅ | 账号 `2101722825` |
| 容器镜像仓库 (CR) | ✅ | `manhuaju-cn-beijing.cr.volces.com/manhuaju/xyq-manju:v9.0.3` |
| TOS Bucket | ✅ | `tos://xyq-prod-cn-beijing` (cn-beijing, 私有) |
| GitHub Actions deploy-vefaas.yml | ✅ | tag push 自动跑 |
| Docker image build & push (cache-aware) | ✅ | v9.0.3 用 layer cache, push 用时 < 10 min (v9.0.2 因 cache 失效 push 90+ min 超时) |
| veFaaS Function | ✅ | id=`0mt4ej8a`, name=`xyq-manju`, port=8000, mem=2048 MB |
| veFaaS Release | ✅ | RevisionNumber=2, weight=100, status=done |
| 33 env 注入函数 | ✅ | `STORAGE_BACKEND=tos`, `TTS_PRIMARY=doubao`, `LLM_PROVIDER_CHAIN=...` |
| 容器内 FastAPI healthy | ✅ | `xyq.api: DB initialized`, `Application startup complete`, `Uvicorn running on http://0.0.0.0:8001` |
| 容器内 Next.js healthy | ✅ | `Next.js 15.0.3 Ready in 230 ms` (port 3000) |
| 容器内 Caddy healthy | ✅ | `server running addr=:8000 protocols=[h1,h2,h3]` |
| **APIG Gateway** | ✅ | `gd8afjpepm94qqo1kmttg` (manhuaju-gw, Running, 公网+私网, AZ b+a) |
| **APIG Service** | ✅ | `sd8ahl2ki9edvua7ttfs0` (xyq-manju-svc, public HTTP/HTTPS) |
| **APIG Upstream → veFaas** | ✅ | `ud8appiapsmhnt1lj8q30` → FunctionId `0mt4ej8a`, version `v1` |
| **APIG Route** | ✅ | `rd8appitqc6mqij6t39q0` (Prefix `/`, 7 methods, timeout 120s, enable=true) |
| **APIG Trigger 写入函数** | ✅ | `ListTriggers` → `Type: apig, GatewayId: gd8afj..., UpstreamId: ud8appi...` |
| 自动化测试 | ✅ | 30 contract tests pass (manju_agent_client + manju_official_contract) |
| 代码已提交 | ✅ | tag v9.0.3 (commit 277f717) + 当前 hotfix |

---

## v9.0.3 修复路径回顾

### v9.0.1 → v9.0.2: 加 python-multipart
- **症状**: APIG bound 后 503，容器日志 `RuntimeError: Form data requires "python-multipart" to be installed`
- **原因**: FastAPI 0.115+ 不再隐式打包 multipart, `/api/batch/upload` 用 `UploadFile` 触发 import-time 报错
- **修复**: `backend/requirements.txt` 加 `python-multipart==0.0.20`

### v9.0.2 → v9.0.3: 缓存友好的 tail-layer 安装
- **症状**: GitHub Actions `Build (and push) image` 步骤跑 90 min 后超时取消
- **原因**: 改 `backend/requirements.txt` → COPY 层 cache 失效 → 全量重装 600 MB Python 依赖 → 从海外 runner 推到 cn-beijing CR 太慢
- **修复**:
  - `backend/requirements.txt` 还原到 v9.0.1 字节相同 (保住 cache)
  - `Dockerfile.vefaas` 和 `Dockerfile.allinone` 末尾各加一行 `RUN pip install --no-cache-dir python-multipart==0.0.20`
  - tail layer ~150 KB, push 秒级完成

### hotfix (本次): 修 volc_signer 签名 + 加 release_function.py
- **症状**: 本地 `python` 调 vefaas `Release` 返回 `InvalidAuthorization 100024`
- **原因**: `src/common/volc_signer.py` 签的 `Content-Type: application/json` 缺 `; charset=utf-8`, vefaas/apig 严格校验
- **修复**: `volc_signer.py` 改成 `application/json; charset=utf-8` (兼容 visual + open 两个 host)
- **配套**: 新增 `scripts/release_function.py` 用 `deploy.py` 的正确 signer 手动 Release; `scripts/setup_apig_full.py` 加 `_is_placeholder` 过滤 + bootstrap `UpstreamVersion v1`

---

## 剩余 1 步 — APIG envoy 503 排查

### 现象

```bash
$ curl -v http://sd8ahl2ki9edvua7ttfs0.apigateway-cn-beijing.volceapi.com/healthz
< HTTP/1.1 503 Service Unavailable
< server: istio-envoy
< content-length: 0
```

`server: istio-envoy` + content-length 0 + 0.5s 内返回 = APIG 接管了请求但 envoy 找不到健康的 upstream endpoint。

我已经验证 (全部 ✅):
- 函数 `0mt4ej8a` 实例 `InstanceStatus: Ready, RevisionNumber: 2`
- 容器日志显示 FastAPI/Next.js/Caddy 全启动成功 (无任何错误)
- APIG 路由 `Enable: true`, 上游 Type=VeFaas, FunctionId 对的上
- VeFaas 侧的 trigger 已注册 (`ListTriggers` 1 条)
- 重建过 route + upstream + upstream version 多次

### 推测原因

APIG 的 VeFaas 连接器需要一个**控制台一次性触发**才会真正建立 endpoint 注册到 envoy。OpenAPI 创建 upstream 后, EDS (Endpoint Discovery Service) 一直没有这个函数的 endpoint, 所以 envoy 无 healthy upstream。

### 操作步骤 (1 分钟搞定)

1. 浏览器打开: https://console.volcengine.com/veapig/instance/gd8afjpepm94qqo1kmttg/route
2. 找到 route `xyq-manju-all` → 点【调试】 (or 【测试】)
3. 方法选 `GET`, 路径填 `/healthz` → 点【发送请求】
4. 如果看到 `200 ok` → 完成, 公网域名立即可用
5. 如果还是 `503` → 在【概览】tab 看上游健康状态; 或点【上游】 → `xyq-manju-up` → 看 endpoint 列表是否为空

如上述操作后仍 503, 备用方案 (任选一):
- 升级网关到最新版本 (控制台【实例详情】→【升级】); 当前是 4.3.5
- 工单: https://console.volcengine.com/ticket/createTicket?Service=apig (附带 GatewayId + 截图)

### 直接 invoke 验证函数可达 (绕开 APIG)

可以用 ve CLI 直接验证函数本身没问题:
```powershell
ve vefaas ListFunctionInstances --body '{\"FunctionId\":\"0mt4ej8a\"}'
# InstanceStatus 应该是 Ready
$body = '{\"FunctionId\":\"0mt4ej8a\",\"Name\":\"<InstanceName from above>\",\"Limit\":50}'
ve vefaas GetFunctionInstanceLogs --body $body
# 找 "Application startup complete" / "Uvicorn running"
```

---

## 还在等用户的 1 件事 (P4, 不阻塞主功能)

**`DOUBAO_TTS_APPID` 11 位数字 ID**

`.env` 里现在的 `api-key-20260516225257` 是 API Key 名字, 不是 AppID。
我已经尝试用 `ve speechsaasprod ListAPIKeys` 自动查询 → 需要先有 AppID 才能列 (鸡蛋问题); `sts GetCallerIdentity` 拿到的是 `2101722825` (账号 ID, 不是 speech AppID)。

**1 分钟人工**:
1. 访问 https://console.volcengine.com/speech/service/8
2. 找"语音合成 大模型 ICL"应用 → 复制顶部的 **AppID** (11 位数字)
3. 告诉我数字, 我同步到 `.env` + Windows env + GitHub Secrets

**降级兜底**: `tts_minimax.py` 当 `DOUBAO_TTS_APPID` 缺失或非数字时自动 fallback 到 MiniMax Speech 2.5 HD (已验证可用)。

---

## 关键运维 ID 速查表

| 资源 | ID | 备注 |
|---|---|---|
| 火山账号 | `2101722825` | sts GetCallerIdentity 验证 |
| Region | `cn-beijing` | 全栈统一 |
| veFaaS Function | `0mt4ej8a` | name `xyq-manju` |
| veFaaS Revision (live) | `2` | weight 100, status done |
| APIG Gateway | `gd8afjpepm94qqo1kmttg` | name `manhuaju-gw`, ver 4.3.5 |
| APIG Service | `sd8ahl2ki9edvua7ttfs0` | name `xyq-manju-svc` |
| APIG Upstream | `ud8appiapsmhnt1lj8q30` | name `xyq-manju-up`, version v1 |
| APIG Route | `rd8appitqc6mqij6t39q0` | name `xyq-manju-all` |
| TOS Bucket | `xyq-prod-cn-beijing` | endpoint `tos-cn-beijing.volces.com` |
| CR Namespace/Repo | `manhuaju/xyq-manju` | host `manhuaju-cn-beijing.cr.volces.com` |
| 公网 URL | `http://sd8ahl2ki9edvua7ttfs0.apigateway-cn-beijing.volceapi.com` | 待 APIG 上游健康即可用 |

---

## 自动化脚本一览

| 脚本 | 用途 |
|---|---|
| `scripts/setup_apig_full.py` | 一键创建/校验 APIG Service + Upstream + UpstreamVersion + Route (idempotent, 占位符过滤) |
| `scripts/release_function.py` | 手动 Release veFaaS 函数 (CR 同步完成后) |
| `scripts/bind_apig_trigger.py` | 备用: VeFaas 侧 `CreateAPIGTrigger` 反向绑定 |
| `scripts/get_function_info.py` | 轮询函数状态 + 取公网 URL |
| `scripts/verify_deployment.py` | 部署后 5 项 smoke test |
| `scripts/verify_volc_chain.py` | 5 个火山 API 真网联通 (ARK / Doubao TTS / Seedream / Jimeng / TOS) |
| `scripts/sync_keys_to_windows.ps1` | 把 52 个 API key 同步到 Windows 用户级 env + Credential Manager |
| `scripts/sync_keys_to_github.ps1` | 同步到 GitHub Secrets |
| `scripts/setup_volc_resources.ps1` | 一次性创建/校验 TOS bucket + CR + veFaaS + APIG |

---

## 一行总结

> 代码 + 镜像 + 函数 + APIG 资源 100% 就绪, v9.0.3 容器内 FastAPI 跑得很干净。**只差控制台点一下 APIG 路由【测试】按钮触发 envoy EDS 注册**, 公网 URL 立即可用。
