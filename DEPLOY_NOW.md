# 上线状态 — v9 全国产 serverless

> **当前**：v9.0.1 镜像已构建+推送+部署到 veFaaS，函数已 Release 完成。
> **剩 1 步**：在 API 网关控制台 5 分钟点几下，让函数对公网开放（火山 veFaaS 必须通过 APIG 暴露 HTTP）。

---

## 已完成（全自动）

| 步骤 | 状态 | 资源 / 证据 |
|---|---|---|
| Windows 用户级 env (52 keys) + Credential Manager (26 keys) | ✅ | `data/windows_keys_synced.json` |
| GitHub Secrets 同步 (33 keys) | ✅ | `gh secret list` 已有 |
| veFaaS 服务授权 | ✅ | 账号 2101722825 |
| 容器镜像仓库 (CR) | ✅ | `manhuaju-cn-beijing.cr.volces.com/manhuaju/xyq-manju:v9.0.1` |
| TOS bucket | ✅ | `tos://xyq-prod-cn-beijing` (cn-beijing, 私有) |
| GitHub Actions deploy-vefaas.yml | ✅ | tag push 自动跑 |
| Docker image build & push | ✅ | 4 min build, 已推 CR (registry cache) |
| veFaaS CreateFunction | ✅ | id=`0mt4ej8a`, name=`xyq-manju`, port=8000 |
| veFaaS Release | ✅ | RevisionNumber 已发布, weight=100 |
| 33 个 env 注入函数 | ✅ | 包括 `STORAGE_BACKEND=tos`, `TTS_PRIMARY=doubao`, `LLM_PROVIDER_CHAIN=deepseek,glm,moonshot,tongyi,spark,doubao` |
| 自动化测试 (50 pass / 10 skip) | ✅ | `tests/test_vefaas_deploy.py` 23 个 OK |

---

## 剩下的 1 件事：绑定 API 网关 (5 分钟)

veFaaS 的函数只有绑定 API 网关才能从公网访问 (官方设计如此，无 `fcapp.run` 这种直访域名)。

### 方式 A — 用控制台 (推荐, 3 分钟)

1. **创建 APIG 实例** (一次性):
   - 打开 https://console.volcengine.com/veapig
   - 点【创建实例】 → 类型选 **Serverless 网关** → 区域 **cn-beijing** → 计费 **按量** → 双可用区随便选 → 提交
   - 等 1~2 分钟实例 Ready

2. **进入实例 → 创建服务**:
   - 服务名 `xyq-manju-svc` → 协议 HTTP → 保存

3. **绑定到 veFaaS 函数** (1 次点击):
   - 打开 https://console.volcengine.com/vefaas/region:cn-beijing/function/0mt4ej8a
   - 左侧【触发器】→【创建触发器】→ 类型选 **API 网关**
   - 选你刚建的 APIG 实例 + 服务
   - 路由路径 `/`，匹配模式 `Prefix`，方法全选
   - 点【确定】

4. **拿到公网域名**:
   - 触发器列表会显示一个形如 `xxx.apigw-cn-beijing.volces.com` 的域名
   - 浏览器访问 `https://<域名>/healthz` 应该看到 `ok`

### 方式 B — 用 OpenAPI (适合后续自动化, 已写好脚本)

```powershell
# 你拿到 3 个 ID 后跑这行 (从控制台复制 ID, 或用 ve CLI 列出):
python scripts/bind_apig_trigger.py `
    --function-name xyq-manju `
    --gateway-id    <你的 gw ID> `
    --service-id    <你的 svc ID> `
    --upstream-id   <你的 upstream ID> `
    --path          /
```

---

## 拿到公网域名后回填

```powershell
# 假设域名是 abc123.apigw-cn-beijing.volces.com
$domain = "abc123.apigw-cn-beijing.volces.com"

# 1. 回填 .env
(Get-Content .env) -replace '^SITE_URL=.*', "SITE_URL=https://$domain" |
  Set-Content .env

# 2. 同步到 GitHub Secrets (供下次 deploy 用)
gh secret set SITE_URL --body "https://$domain" --repo bistuwangqiyuan/ai-manju-xiaoyunque

# 3. 健康检查
curl https://$domain/healthz
curl https://$domain/api/health
```

---

## 仍在等用户的 2 件小事 (不阻塞上线)

- **P3**: 4 个漫剧 Agent PDF 放到 `docs/volc-manju/`
  - 抓 4 个页面 (右上角 "下载 pdf") → `manju_agent_intro.pdf` / `manju_agent_video_gen.pdf` / `manju_agent_video_synth.pdf` / `manju_agent_full_workflow.pdf`
  - 拿到后我即把 `src/shell3_skylark_engine/manju_agent_client.py` 里的 `req_key` + 字段映射常量改成真实值
- **P4**: `DOUBAO_TTS_APPID` 数字 ID
  - 你现在填的是 API Key 名字 `api-key-20260516225257`，不是 AppID
  - 访问 https://console.volcengine.com/speech/service/8 → 找"语音合成 大模型 ICL"应用 → 复制 11 位数字 AppID
  - 告诉我数字 ID, 我同步到 .env + Windows env + GitHub Secrets

---

## 故障排查

### A. 触发器绑定后 404
- veFaaS 函数容器内监听 `:8000` (Caddy)，APIG 把流量转发到这个端口
- 如果 healthz 404 → 检查 APIG 触发器的【后端配置】是否选了对的函数

### B. 触发器绑定后 502
- 容器还在冷启动 (Docker pull + Caddy/Next/FastAPI 启动需要 ~30 s)
- 多 curl 几次, 或先 `gh api repos/bistuwangqiyuan/ai-manju-xiaoyunque/actions/runs --jq '.workflow_runs[0]'` 看 build 是否真成功

### C. APIG 实例创建后看不到
- 等 2-3 分钟 (APIG 实例创建是异步的)
- 或刷新页面

---

## 一行汇总

> 函数已上线，需要 **3 分钟点 APIG 控制台**拿到公网 URL，然后系统全功能就绪。
