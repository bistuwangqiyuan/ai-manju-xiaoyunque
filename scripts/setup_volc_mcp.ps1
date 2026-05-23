# =============================================================================
# 火山引擎开发环境 一键配置 (Windows PowerShell)
#
# 做 5 件事:
#   1. 校验 ve.exe / tosutil.exe / uv 是否就位 (缺则提示安装命令)
#   2. 从 .env / backend/.env / deploy/cn-serverless/.env 读取 VOLC AKSK + ARK Key
#      (没有就提示输入, 输入后追加保存到 .env)
#   3. 写入 .cursor/mcp.json 的所有 env 字段
#   4. 配置 ve CLI 认证 (ve configure set)
#   5. 配置 tosutil 认证 (tosutil config)
#
# 使用:
#   pwsh scripts/setup_volc_mcp.ps1
# =============================================================================
$ErrorActionPreference = 'Stop'

$RootDir = (Resolve-Path "$PSScriptRoot\..").Path
Set-Location $RootDir

function HR { Write-Host ('-' * 60) -ForegroundColor DarkGray }
function Green ($m) { Write-Host $m -ForegroundColor Green }
function Blue  ($m) { Write-Host $m -ForegroundColor Cyan }
function Yellow($m) { Write-Host $m -ForegroundColor Yellow }
function Red   ($m) { Write-Host $m -ForegroundColor Red }

# ---------- 1) 工具检测 ----------
HR; Blue "[1/5] 工具检测..."
$tools = @{
    've'      = 'https://github.com/volcengine/volcengine-cli/releases (Windows amd64)'
    'tosutil' = 'https://tos-tools.tos-cn-beijing.volces.com/windows/tosutil'
    'uv'      = 'powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"'
    'npx'     = 'https://nodejs.org (Node 18+)'
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
    if ($missing -contains 've' -or $missing -contains 'tosutil') {
        Yellow "提示: 之前已为你装到 $env:USERPROFILE\.volc-tools, 请重新打开 PowerShell (新会话才能加载 USER PATH 更新)"
    }
    exit 1
}

# ---------- 2) 读 / 求取 AKSK ----------
HR; Blue "[2/5] 加载 / 输入 火山引擎凭证..."

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

$AK = $null; $SK = $null; $ArkKey = $null; $TosBucket = $null
foreach ($p in $EnvCandidates) {
    if (-not $AK)        { $AK        = Get-EnvValue $p 'VOLC_ACCESS_KEY' }
    if (-not $AK)        { $AK        = Get-EnvValue $p 'VOLC_AK' }
    if (-not $SK)        { $SK        = Get-EnvValue $p 'VOLC_SECRET_KEY' }
    if (-not $SK)        { $SK        = Get-EnvValue $p 'VOLC_SK' }
    if (-not $ArkKey)    { $ArkKey    = Get-EnvValue $p 'VOLC_ARK_API_KEY' }
    if (-not $ArkKey)    { $ArkKey    = Get-EnvValue $p 'ARK_API_KEY' }
    if (-not $TosBucket) { $TosBucket = Get-EnvValue $p 'S3_BUCKET' }
    if (-not $TosBucket) { $TosBucket = Get-EnvValue $p 'TOS_BUCKET' }
}

if (-not $AK) {
    Yellow "  未在 .env 中找到 VOLC_ACCESS_KEY"
    $AK = Read-Host '  请粘贴 VOLC_ACCESS_KEY (以 AKLT 或 AKID 开头, 24+ 字符; 留空跳过)'
    if (-not $AK) { Yellow "  跳过 AKSK 配置, MCP 仍可装但需手填" }
}
if ($AK -and -not $SK) {
    $SK = Read-Host '  请粘贴 VOLC_SECRET_KEY (40 字符, 通常 = base64) '
}
if (-not $ArkKey) {
    Yellow "  未在 .env 中找到 VOLC_ARK_API_KEY"
    $ArkKey = Read-Host '  请粘贴 VOLC_ARK_API_KEY (UUID 形式; 留空跳过 Seedream/Jimeng MCP)'
}
if (-not $TosBucket) {
    $TosBucket = Read-Host '  TOS 桶名 (留空则不预填; 后续可自己改 .cursor/mcp.json)'
}

# 摘要
$mask = { param($s) if (-not $s) { return '(空)' } else { return $s.Substring(0,[Math]::Min(6,$s.Length)) + '***' } }
Green "  AK     = $(& $mask $AK)"
Green "  SK     = $(& $mask $SK)"
Green "  ArkKey = $(& $mask $ArkKey)"
Green "  TOS    = $TosBucket"

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

function SetIf ($obj, $key, $val) {
    if (-not $val) { return }
    if ($null -ne $obj.env -and $obj.env.PSObject.Properties.Name -contains $key) {
        $obj.env.$key = $val
    }
}

SetIf $mcp.mcpServers.'volc-tos'     'VOLCENGINE_ACCESS_KEY' $AK
SetIf $mcp.mcpServers.'volc-tos'     'VOLCENGINE_SECRET_KEY' $SK
SetIf $mcp.mcpServers.'volc-tos'     'TOS_BUCKET'            $TosBucket
SetIf $mcp.mcpServers.'volc-vefaas'  'VOLCENGINE_ACCESS_KEY' $AK
SetIf $mcp.mcpServers.'volc-vefaas'  'VOLCENGINE_SECRET_KEY' $SK
SetIf $mcp.mcpServers.'volc-cdn'     'VOLCENGINE_ACCESS_KEY' $AK
SetIf $mcp.mcpServers.'volc-cdn'     'VOLCENGINE_SECRET_KEY' $SK
SetIf $mcp.mcpServers.'volc-imagex'  'VOLCENGINE_ACCESS_KEY' $AK
SetIf $mcp.mcpServers.'volc-imagex'  'VOLCENGINE_SECRET_KEY' $SK
SetIf $mcp.mcpServers.'volc-jimeng'  'ARK_API_KEY'           $ArkKey

# Seedream MCP uses --ark-key=XXX arg (not env), patch the placeholder
if ($ArkKey) {
    $args = $mcp.mcpServers.'volc-seedream'.args
    for ($i = 0; $i -lt $args.Count; $i++) {
        if ($args[$i] -like '*ARK_KEY_PLACEHOLDER*') {
            $args[$i] = '--ark-key=' + $ArkKey
        }
    }
}

# 写回
$json = $mcp | ConvertTo-Json -Depth 10
[System.IO.File]::WriteAllText($McpPath, $json, [System.Text.UTF8Encoding]::new($false))
Green "  $McpPath 已更新"

# ---------- 4) ve CLI 配置 ----------
HR; Blue "[4/5] 配置 ve CLI..."
if ($AK -and $SK) {
    & ve configure set --profile default --ak $AK --sk $SK --region cn-beijing 2>&1 | Out-Null
    & ve configure list 2>&1 | Select-Object -First 8
    Green "  ve 已配置 (profile=default, region=cn-beijing)"
} else {
    Yellow "  跳过 (无 AKSK)"
}

# ---------- 5) tosutil 配置 ----------
HR; Blue "[5/5] 配置 tosutil..."
if ($AK -and $SK) {
    & tosutil config -i $AK -k $SK -e tos-cn-beijing.volces.com -re cn-beijing 2>&1 | Out-Null
    Green "  tosutil 已配置 (endpoint=tos-cn-beijing.volces.com, region=cn-beijing)"
} else {
    Yellow "  跳过 (无 AKSK)"
}

HR
Green "========================================"
Green "  火山引擎开发环境 配置完成"
Green "========================================"
Green "  CLI:"
Green "    ve --help                    # 主 CLI (覆盖 100+ 火山服务)"
Green "    ve ark --help                # 方舟 (LLM/Doubao/Skylark)"
Green "    ve tos --help                # 对象存储"
Green "    tosutil ls tos://$TosBucket  # 列桶"
Green ""
Green "  Cursor MCP:"
Green "    重启 Cursor / Reload Window 后, 你可以直接对 AI 说:"
Green "    - 用 volc-tos 列出 bucket xxx 的所有 mp4"
Green "    - 用 volc-jimeng 帮我生成一张古风女子立绘"
Green "    - 用 volc-vefaas 查看我的 serverless 函数列表"
Green ""
Green "  下一步: 见 VOLC_DEV_SETUP.md"
HR
