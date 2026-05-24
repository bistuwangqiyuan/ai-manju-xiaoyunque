# =============================================================================
# 阿里云 开发环境 一键配置 (Windows PowerShell)
#
# 做 5 件事:
#   1. 校验 aliyun.exe / ossutil.exe / uv 是否就位 (缺则提示安装命令)
#   2. 从 .env / backend/.env / deploy/cn-serverless/.env 读取:
#         ALIBABA_CLOUD_ACCESS_KEY_ID / ALIYUN_ACCESS_KEY_ID
#         ALIBABA_CLOUD_ACCESS_KEY_SECRET / ALIYUN_ACCESS_KEY_SECRET
#         DASHSCOPE_API_KEY
#         OSS_BUCKET / OSS_ENDPOINT / OSS_REGION
#      (没有就提示输入)
#   3. 写入 .cursor/mcp.json 的所有 aliyun-* 与 bailian 的 env / header
#   4. 配置 aliyun CLI 默认 profile (aliyun configure set)
#   5. 配置 ossutil 默认 profile (ossutil config)
#
# 使用:
#   pwsh scripts/setup_aliyun_mcp.ps1
# =============================================================================
$ErrorActionPreference = 'Stop'

$RootDir = (Resolve-Path "$PSScriptRoot\..").Path
Set-Location $RootDir

function HR     { Write-Host ('-' * 60) -ForegroundColor DarkGray }
function Green ($m) { Write-Host $m -ForegroundColor Green }
function Blue  ($m) { Write-Host $m -ForegroundColor Cyan }
function Yellow($m) { Write-Host $m -ForegroundColor Yellow }
function Red   ($m) { Write-Host $m -ForegroundColor Red }

# ---------- 1) 工具检测 ----------
HR; Blue "[1/5] 工具检测..."
$tools = @{
    'aliyun'  = 'https://github.com/aliyun/aliyun-cli/releases (Windows amd64 zip)'
    'ossutil' = 'https://gosspublic.alicdn.com/ossutil/v2/2.3.0/ossutil-2.3.0-windows-amd64.zip'
    'uv'      = 'powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"'
    'uvx'     = '随 uv 一起安装'
}
$missing = @()
foreach ($t in $tools.Keys) {
    if (-not (Get-Command $t -ErrorAction SilentlyContinue)) {
        $missing += $t
        Red ("  X $t  未安装. 安装: $($tools[$t])")
    } else {
        Green ("  + $t  ok")
    }
}
if ($missing.Count -gt 0) {
    Red "请先安装上述工具再重跑本脚本"
    if ($missing -contains 'aliyun' -or $missing -contains 'ossutil') {
        Yellow "提示: 之前已为你装到 $env:USERPROFILE\.aliyun-tools, 请重新打开 PowerShell (新会话才能加载 USER PATH 更新)"
    }
    exit 1
}

# ---------- 2) 读 / 求取凭证 ----------
HR; Blue "[2/5] 加载 / 输入 阿里云凭证..."

function Get-EnvValue ($Path, $Key) {
    if (-not (Test-Path $Path)) { return $null }
    foreach ($line in (Get-Content $Path)) {
        if ($line -match "^\s*$Key=(.*)$") {
            $v = $matches[1].Trim().Trim('"').Trim("'")
            if ($v) { return $v }
        }
    }
    return $null
}

$EnvCandidates = @(
    "$RootDir\.env",
    "$RootDir\backend\.env",
    "$RootDir\deploy\cn-serverless\.env",
    "$RootDir\deploy\cn-serverless\.env.simple"
)

$AK = $null; $SK = $null; $DashKey = $null; $OssBucket = $null; $OssEndpoint = $null; $OssRegion = $null
foreach ($p in $EnvCandidates) {
    if (-not $AK)         { $AK         = Get-EnvValue $p 'ALIBABA_CLOUD_ACCESS_KEY_ID' }
    if (-not $AK)         { $AK         = Get-EnvValue $p 'ALIYUN_ACCESS_KEY_ID' }
    if (-not $AK)         { $AK         = Get-EnvValue $p 'ALI_ACCESS_KEY' }
    if (-not $SK)         { $SK         = Get-EnvValue $p 'ALIBABA_CLOUD_ACCESS_KEY_SECRET' }
    if (-not $SK)         { $SK         = Get-EnvValue $p 'ALIYUN_ACCESS_KEY_SECRET' }
    if (-not $SK)         { $SK         = Get-EnvValue $p 'ALI_SECRET_KEY' }
    if (-not $DashKey)    { $DashKey    = Get-EnvValue $p 'DASHSCOPE_API_KEY' }
    if (-not $OssBucket)  { $OssBucket  = Get-EnvValue $p 'OSS_BUCKET' }
    if (-not $OssEndpoint){ $OssEndpoint= Get-EnvValue $p 'OSS_ENDPOINT' }
    if (-not $OssRegion)  { $OssRegion  = Get-EnvValue $p 'OSS_REGION' }
}

if (-not $OssRegion)   { $OssRegion   = 'cn-hangzhou' }
if (-not $OssEndpoint) { $OssEndpoint = "https://oss-$OssRegion.aliyuncs.com" }

if (-not $AK) {
    Yellow "  未在 .env 找到 ALIBABA_CLOUD_ACCESS_KEY_ID"
    Yellow "  控制台: https://ram.console.aliyun.com/manage/ak"
    $AK = Read-Host '  请粘贴 AccessKeyID (LTAI 开头, 24 字符; 留空跳过)'
}
if ($AK -and -not $SK) {
    $SK = Read-Host '  请粘贴 AccessKeySecret (30 字符)'
}
if (-not $DashKey) {
    Yellow "  未在 .env 找到 DASHSCOPE_API_KEY"
    Yellow "  控制台: https://bailian.console.aliyun.com/?tab=model#/api-key"
    $DashKey = Read-Host '  请粘贴 DashScope API Key (sk-xxx 格式; 留空跳过百炼相关 MCP)'
}
if (-not $OssBucket) {
    $OssBucket = Read-Host "  OSS 桶名 (区域=$OssRegion; 留空不预填)"
}

$mask = { param($s) if (-not $s) { return '(空)' } else { return $s.Substring(0,[Math]::Min(6,$s.Length)) + '***' } }
Green "  AccessKeyID     = $(& $mask $AK)"
Green "  AccessKeySecret = $(& $mask $SK)"
Green "  DashScope Key   = $(& $mask $DashKey)"
Green "  OSS Bucket      = $OssBucket"
Green "  OSS Region      = $OssRegion"
Green "  OSS Endpoint    = $OssEndpoint"

# ---------- 3) 写 .cursor/mcp.json ----------
HR; Blue "[3/5] 写入 .cursor/mcp.json env..."
$McpPath = "$RootDir\.cursor\mcp.json"
$McpExample = "$RootDir\.cursor\mcp.json.example"
# 首次运行: 从模板复制 (mcp.json 在 .gitignore 里, 不会被入库)
if (-not (Test-Path $McpPath) -and (Test-Path $McpExample)) {
    Copy-Item $McpExample $McpPath
    Green "  从 mcp.json.example 复制初始模板"
}
$mcp = (Get-Content $McpPath -Raw -Encoding UTF8) | ConvertFrom-Json

function SetEnv ($srv, $key, $val) {
    if (-not $val) { return }
    if ($null -ne $srv.env -and $srv.env.PSObject.Properties.Name -contains $key) {
        $srv.env.$key = $val
    }
}

# AKSK 写入 4 个 aliyun-* MCP
foreach ($name in 'aliyun-ops','aliyun-rds','aliyun-fc','aliyun-observability') {
    $srv = $mcp.mcpServers.$name
    SetEnv $srv 'ALIBABA_CLOUD_ACCESS_KEY_ID' $AK
    SetEnv $srv 'ALIBABA_CLOUD_ACCESS_KEY_SECRET' $SK
}

# 百炼 WebSearch — 改 headers
if ($DashKey) {
    $bs = $mcp.mcpServers.'aliyun-bailian-websearch'
    if ($null -ne $bs -and $null -ne $bs.headers) {
        $bs.headers.'Authorization' = "Bearer $DashKey"
    }
}

$json = $mcp | ConvertTo-Json -Depth 10
[System.IO.File]::WriteAllText($McpPath, $json, [System.Text.UTF8Encoding]::new($false))
Green "  $McpPath 已更新"

# ---------- 4) aliyun CLI 配置 ----------
HR; Blue "[4/5] 配置 aliyun CLI..."
if ($AK -and $SK) {
    # aliyun configure set --profile default --mode AK --region X --access-key-id X --access-key-secret X
    & aliyun configure set --profile default --mode AK --region $OssRegion --access-key-id $AK --access-key-secret $SK 2>&1 | Out-Null
    Write-Host "  当前 profile 列表:" -ForegroundColor DarkGray
    & aliyun configure list 2>&1 | Select-Object -First 10
    Green "  aliyun 已配置 (profile=default, region=$OssRegion)"
} else {
    Yellow "  跳过 (无 AKSK)"
}

# ---------- 5) ossutil 配置 ----------
HR; Blue "[5/5] 配置 ossutil..."
if ($AK -and $SK) {
    # ossutil 2.x: config set (1.x 的 -e -i -k -r 已废弃)
    & ossutil config set accessKeyID $AK --profile default 2>&1 | Out-Null
    & ossutil config set accessKeySecret $SK --profile default 2>&1 | Out-Null
    & ossutil config set region $OssRegion --profile default 2>&1 | Out-Null
    Green "  ossutil 已配置 (profile=default, region=$OssRegion)"
} else {
    Yellow "  跳过 (无 AKSK)"
}

HR
Green "========================================"
Green "  阿里云开发环境 配置完成"
Green "========================================"
Green "  CLI 实战:"
Green "    aliyun --version                    # 显示版本"
Green "    aliyun ecs DescribeRegions          # 列地域"
Green "    aliyun ecs DescribeInstances --RegionId $OssRegion"
Green "    aliyun oss ls oss://$OssBucket      # 列桶 (CLI 端)"
Green "    ossutil ls oss://$OssBucket         # 列桶 (ossutil)"
Green "    ossutil cp data\ep01.mp4 oss://$OssBucket/episodes/"
Green ""
Green "  Cursor MCP:"
Green "    重启 Cursor / Reload Window 后, 直接对 AI 说:"
Green "    - 用 aliyun-ops 列出我所有 ECS 实例"
Green "    - 用 aliyun-rds 查看 MySQL 实例列表"
Green "    - 用 aliyun-fc 部署一个 hello-world Python 函数"
Green "    - 用 aliyun-observability 查看 SLS 最近 1 小时 ERROR 日志"
Green "    - 用 aliyun-bailian-websearch 帮我查最新 AIGC 法规"
Green ""
Green "  详细文档: ALIYUN_DEV_SETUP.md"
HR
