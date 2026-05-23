# =============================================================================
# 小云雀 AI 漫剧 · 无服务器一键部署 (Windows PowerShell)
#
# 前提:
#   - PowerShell 7+ (或 Windows PowerShell 5.1+)
#   - 已安装 node 18+
#   - 已 cp .env.example .env 并填好关键值
#
# 使用:
#   cd deploy/cn-serverless
#   Copy-Item .env.example .env  # 编辑填入真实值
#   .\deploy.ps1
# =============================================================================
$ErrorActionPreference = 'Stop'

$SlDir = Split-Path -Parent $PSCommandPath
$RootDir = (Resolve-Path "$SlDir\..\..").Path
Set-Location $SlDir

if (-not (Test-Path .env)) {
    Write-Host "ERROR: 缺少 .env，请先 Copy-Item .env.example .env 并填值" -ForegroundColor Red
    exit 1
}

# 读取 .env 到当前 process env vars
Get-Content .env | ForEach-Object {
    if ($_ -match '^\s*([^#=][^=]*)=(.*)$') {
        $k = $matches[1].Trim()
        $v = $matches[2].Trim().Trim('"').Trim("'")
        Set-Item -Path "Env:$k" -Value $v
    }
}

function HR { Write-Host ('-' * 60) }
function Green ($m) { Write-Host $m -ForegroundColor Green }
function Blue  ($m) { Write-Host $m -ForegroundColor Cyan }
function Yellow($m) { Write-Host $m -ForegroundColor Yellow }
function Red   ($m) { Write-Host $m -ForegroundColor Red }

# ---------- 1. 装 CLI ----------
HR; Blue "[1/5] 检查 / 安装 CLI..."
if (-not (Get-Command tcb -ErrorAction SilentlyContinue)) {
    npm i -g '@cloudbase/cli@latest'
}
if (-not (Get-Command scf -ErrorAction SilentlyContinue)) {
    npm i -g serverless@3
}
Green "tcb + scf-cli ready"

# ---------- 2. 登录 ----------
HR; Blue "[2/5] 登录腾讯云 (使用 AKSK)..."
& tcb login --apiKeyId $env:TENCENT_SECRET_ID --apiKey $env:TENCENT_SECRET_KEY

# ---------- 3. 部署 backend ----------
HR; Blue "[3/5] 部署 backend 到 CloudBase 云托管 envId=$env:ENV_ID..."
Set-Location $RootDir
& tcb framework deploy -e $env:ENV_ID --config-file deploy/cn-serverless/cloudbaserc.json

$BackendUrl = $env:BACKEND_URL
if ([string]::IsNullOrEmpty($BackendUrl) -or $BackendUrl -like '*xxxxx*') {
    Yellow "请到 CloudBase 控制台拿到真实的 backend URL,回填 .env 的 BACKEND_URL,再重跑本脚本"
} else {
    Green "Backend URL: $BackendUrl"
}

# ---------- 4. 部署 SCF ----------
HR; Blue "[4/5] 部署 SCF 定时 worker tick..."
if (-not [string]::IsNullOrEmpty($BackendUrl) -and $BackendUrl -notlike '*xxxxx*') {
    Set-Location "$SlDir\scf-worker-tick"
    $template = Get-Content template.yaml -Raw
    $template = $template.Replace('${BACKEND_URL}', $BackendUrl).Replace('${INTERNAL_API_SECRET}', $env:INTERNAL_API_SECRET)
    $template | Out-File template.deploy.yaml -Encoding utf8
    try {
        & scf deploy --template-file template.deploy.yaml -r $env:TENCENT_REGION
    } catch {
        Yellow "SCF 部署失败,请手动到控制台创建函数. 详见 RUNBOOK_CN_SERVERLESS.md 步骤 4"
    }
    Remove-Item template.deploy.yaml -ErrorAction SilentlyContinue
}

# ---------- 5. 烟雾测试 ----------
HR; Blue "[5/5] 烟雾测试..."
if (-not [string]::IsNullOrEmpty($BackendUrl) -and $BackendUrl -notlike '*xxxxx*') {
    try {
        $h = Invoke-RestMethod "$BackendUrl/api/health" -TimeoutSec 30
        Green "Health: $($h | ConvertTo-Json -Compress)"
    } catch { Red "Health 失败: $_" }

    try {
        $t = Invoke-RestMethod "$BackendUrl/api/internal/worker/tick" -Method Post `
            -Headers @{ 'X-Internal-Secret' = $env:INTERNAL_API_SECRET } `
            -ContentType 'application/json' -Body '{"max_jobs":1}' -TimeoutSec 60
        Green "Tick: $($t | ConvertTo-Json -Compress)"
    } catch { Red "Tick 失败: $_" }
}

HR
Green "=========================================="
Green "  Serverless 部署完成"
Green "=========================================="
Green "  下一步:"
Green "    1) 把 BACKEND_URL ($BackendUrl) 填到 EdgeOne Pages 项目的环境变量"
Green "    2) EdgeOne 控制台 - 导入 GitHub - 选 web/ 目录 - 部署"
Green "  EdgeOne: https://console.cloud.tencent.com/edgeone/pages"
HR
