# =============================================================================
# 小云雀 AI 漫剧 · 极简一键 Serverless 部署 (Windows PowerShell)
#
# 流程:
#   1. 校验 .env.simple 内 3 个必填字段
#   2. 校验 / 安装 @cloudbase/cli
#   3. tcb login --apiKeyId / apiKey
#   4. 自动生成 JWT_SECRET 和 INTERNAL_API_SECRET
#   5. tcb framework deploy 推 Dockerfile.allinone 到 CloudBase 云托管
#   6. 获取自动分配的 *.run.tcloudbase.com 域名
#   7. 烟雾测试 + 在浏览器打开
#
# 使用:
#   cd deploy\cn-serverless
#   Copy-Item .env.simple.example .env.simple
#   notepad .env.simple   # 填 3 个值
#   .\deploy_simple.ps1
# =============================================================================
$ErrorActionPreference = 'Stop'

$SlDir = Split-Path -Parent $PSCommandPath
$RootDir = (Resolve-Path "$SlDir\..\..").Path
Set-Location $SlDir

function HR { Write-Host ('=' * 60) -ForegroundColor DarkGray }
function Green ($m) { Write-Host $m -ForegroundColor Green }
function Blue  ($m) { Write-Host $m -ForegroundColor Cyan }
function Yellow($m) { Write-Host $m -ForegroundColor Yellow }
function Red   ($m) { Write-Host $m -ForegroundColor Red; throw $m }

# ---------- 0) 读 .env.simple ----------
$EnvFile = ".env.simple"
if (-not (Test-Path $EnvFile)) {
    Red "ERROR: 缺少 $EnvFile`n  请先: Copy-Item .env.simple.example .env.simple`n  然后用记事本填 3 个值"
}
Get-Content $EnvFile | ForEach-Object {
    if ($_ -match '^\s*([A-Z_][A-Z0-9_]*)=(.*)$') {
        $k = $matches[1].Trim()
        $v = $matches[2].Trim().Trim('"').Trim("'")
        if ($v) { Set-Item -Path "Env:$k" -Value $v }
    }
}

# ---------- 1) 校验 3 个必填 ----------
HR; Blue "[1/6] 校验必填字段..."
$missing = @()
if (-not $env:TENCENT_SECRET_ID) { $missing += 'TENCENT_SECRET_ID' }
if (-not $env:TENCENT_SECRET_KEY){ $missing += 'TENCENT_SECRET_KEY' }
if (-not $env:ENV_ID)            { $missing += 'ENV_ID' }
if ($missing.Count -gt 0) {
    Red "缺少必填字段: $($missing -join ', ')`n  请编辑 .env.simple"
}
if ($env:TENCENT_SECRET_ID -notmatch '^AKID') {
    Yellow "[警告] TENCENT_SECRET_ID 不以 AKID 开头, 请确认是否填反了 ID/KEY"
}
Green "  TENCENT_SECRET_ID = $($env:TENCENT_SECRET_ID.Substring(0,[Math]::Min(8,$env:TENCENT_SECRET_ID.Length)))...***"
Green "  ENV_ID            = $($env:ENV_ID)"

# ---------- 2) 安装 tcb CLI ----------
HR; Blue "[2/6] 检查 / 安装 @cloudbase/cli..."
if (-not (Get-Command tcb -ErrorAction SilentlyContinue)) {
    Yellow "  未检测到 tcb, 正在用 npm 安装..."
    npm i -g '@cloudbase/cli@latest' 2>&1 | Out-Null
}
$tcbVer = (tcb -v 2>&1) -join ' '
Green "  tcb: $tcbVer"

# ---------- 3) 登录 ----------
HR; Blue "[3/6] 登录腾讯云..."
& tcb logout 2>&1 | Out-Null
& tcb login --apiKeyId $env:TENCENT_SECRET_ID --apiKey $env:TENCENT_SECRET_KEY | Out-Null
Green "  登录成功"

# ---------- 4) 自动生成密钥 ----------
HR; Blue "[4/6] 生成 JWT_SECRET + INTERNAL_API_SECRET..."
function NewSecret {
    [Convert]::ToBase64String([System.Security.Cryptography.RandomNumberGenerator]::GetBytes(48))
}
if (-not $env:JWT_SECRET)          { $env:JWT_SECRET          = NewSecret }
if (-not $env:INTERNAL_API_SECRET) { $env:INTERNAL_API_SECRET = NewSecret }
$env:SITE_URL = "https://placeholder"   # 部署后真实回填
$env:MOCK_MODE = "0"
foreach ($k in 'VOLC_ARK_API_KEY','ANTHROPIC_API_KEY','DEEPSEEK_API_KEY','DOUBAO_API_KEY') {
    if (-not (Get-Item "Env:$k" -ErrorAction SilentlyContinue)) {
        Set-Item -Path "Env:$k" -Value ''
    }
}
Green "  Secrets 已生成 (运行时注入到容器)"

# ---------- 5) tcb framework deploy ----------
HR; Blue "[5/6] 推送 Dockerfile.allinone 到 CloudBase 云托管..."
Yellow "  首次构建约 5-10 分钟 (Next.js + Python + Caddy + ffmpeg 多阶段镜像)"
Set-Location $RootDir
& tcb framework deploy -e $env:ENV_ID --config-file deploy/cn-serverless/cloudbaserc.allinone.json

# ---------- 6) 获取 URL + 烟雾测试 ----------
HR; Blue "[6/6] 获取访问 URL + 烟雾测试..."
$ServiceJson = & tcb run service:list -e $env:ENV_ID --json 2>$null | Out-String
$url = $null
try {
    $svcs = $ServiceJson | ConvertFrom-Json
    $svc = $svcs | Where-Object { $_.name -eq 'xyq' } | Select-Object -First 1
    if ($svc -and $svc.url) { $url = $svc.url }
} catch {}

if ($url) {
    Green "`n  访问地址: $url"
    # 健康检查
    try {
        Start-Sleep -Seconds 10  # 等容器起 (Caddy + Next.js + uvicorn)
        $h = Invoke-RestMethod "$url/api/health" -TimeoutSec 30
        Green "  /api/health: $($h | ConvertTo-Json -Compress)"
    } catch {
        Yellow "  健康检查暂未通过 (容器还在启动, 30s 后再试 curl $url/api/health)"
    }
    # 自动打开浏览器
    try { Start-Process $url } catch {}
} else {
    Yellow "  自动获取 URL 失败. 请到 CloudBase 控制台查看:"
    Yellow "  https://console.cloud.tencent.com/tcb/service/index?envId=$($env:ENV_ID)"
}

HR
Green "========================================"
Green "  部署完成"
Green "========================================"
Green "  - 服务: 单容器 (FastAPI + Next.js + Caddy + SQLite)"
Green "  - 数据: SQLite 存于 /data (容器临时盘; 要持久化看下方提示)"
Green "  - 闲时: 自动缩到 0 instance, ¥0 / 小时"
Green "  - 满载: 自动扩到 5 instance, 按 CPU 秒计费"
Green ""
Green "  下一步 (按需):"
Green "  1) 持久化 SQLite (避免重启丢数据):"
Green "     控制台 → 云托管 → xyq → 配置 → 持久化存储 → 挂载 CFS 到 /data"
Green "  2) 绑定自定义域名 (备案后):"
Green "     控制台 → 云托管 → xyq → 自定义域名 → 添加"
Green "  3) 填真实 AI Keys:"
Green "     控制台 → 云托管 → xyq → 环境变量 → 编辑 VOLC_ARK_API_KEY 等"
HR
