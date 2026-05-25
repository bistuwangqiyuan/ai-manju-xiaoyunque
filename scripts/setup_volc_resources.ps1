#requires -Version 5.1
<#
.SYNOPSIS
    一键检查 / 创建火山引擎部署所需的全部云资源.

.DESCRIPTION
    流程:
      1. 检查 ve / tosutil / docker / python 可用; 缺则提示安装链接
      2. 检查 VOLC_ACCESS_KEY / SECRET_KEY 是否就绪 (从 setx 拿)
      3. ve configure 是否已 login; 否则用 setx 的 ak/sk 自动 login
      4. TOS bucket: 检查 -> (可选) 创建
      5. 容器镜像仓库 (CR) 实例 + 命名空间 + 仓库: 检查 -> (可选) 创建
      6. veFaaS 服务开通状态: 检查 -> 输出授权链接
      7. API 网关实例: 检查 -> 输出创建链接
      8. NAS (可选): 检查 -> 输出创建链接
      9. 输出 .env 增量 (TOS_BUCKET / 镜像地址 / API 网关 ID 等)

.PARAMETER CreateBucket
    若 TOS bucket 不存在则自动创建 (用 tosutil)

.PARAMETER BucketName
    TOS bucket 名 (默认 xyq-prod-cn-beijing)

.PARAMETER Region
    火山区域 (默认 cn-beijing)

.PARAMETER DryRun
    只检查不创建

.EXAMPLE
    # 标准巡检
    .\scripts\setup_volc_resources.ps1

.EXAMPLE
    # 自动建 bucket
    .\scripts\setup_volc_resources.ps1 -CreateBucket -BucketName xyq-prod-cn-beijing
#>
[CmdletBinding()]
param(
    [string]$BucketName = "xyq-prod-cn-beijing",
    [string]$Region     = "cn-beijing",
    [string]$CRNamespace = "xyq",
    [string]$CRRepo      = "manju",
    [switch]$CreateBucket,
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"
try { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 } catch {}

$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot

# ---- 让 User-level setx 写的 keys 在当前 session 立刻生效 ----
$keysToReload = @("VOLC_ACCESS_KEY","VOLC_SECRET_KEY","TOS_BUCKET","TOS_ENDPOINT","VOLC_REGION")
foreach ($k in $keysToReload) {
    $v = [Environment]::GetEnvironmentVariable($k, "User")
    if ($v -and -not [string]::IsNullOrWhiteSpace($v)) {
        Set-Item -Path "env:$k" -Value $v -Force
    }
}

Write-Host ""
Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "  火山引擎云资源巡检 / 自动创建" -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "Region:       $Region"
Write-Host "Bucket:       $BucketName"
Write-Host "CR namespace: $CRNamespace / repo: $CRRepo"
Write-Host "DryRun:       $DryRun"
Write-Host ""

# ---- 检查辅助函数 ----
function Test-Cmd {
    param([string]$Name)
    try {
        $null = Get-Command $Name -ErrorAction Stop
        return $true
    } catch {
        return $false
    }
}

function Step($num, $title) {
    Write-Host ""
    Write-Host "── $num/8 $title ──" -ForegroundColor Yellow
}

$checklist = @{
    ve_cli         = $false
    tosutil        = $false
    docker         = $false
    python         = $false
    ak_present     = $false
    bucket_exists  = $false
    cr_namespace   = "未检查"
    vefaas_authed  = "需控制台手动确认"
    apig_authed    = "需控制台手动确认"
    nas_id         = "未创建"
}

# ---- 1) CLI 检查 ----
Step 1 "检查 CLI 工具"
$checklist.ve_cli = Test-Cmd "ve"
$checklist.tosutil = Test-Cmd "tosutil"
$checklist.docker  = Test-Cmd "docker"
$checklist.python  = Test-Cmd "python"

if (-not $checklist.ve_cli) {
    Write-Host "  ✗ ve CLI 未安装" -ForegroundColor Red
    Write-Host "    下载: https://www.volcengine.com/docs/6291/65566" -ForegroundColor DarkGray
    Write-Host "    或: scripts\setup_volc_mcp.ps1 (自动下载)" -ForegroundColor DarkGray
} else { Write-Host "  ✓ ve CLI" -ForegroundColor Green }

if (-not $checklist.tosutil) {
    Write-Host "  ✗ tosutil 未安装" -ForegroundColor Red
    Write-Host "    下载: https://www.volcengine.com/docs/6349/148777" -ForegroundColor DarkGray
} else { Write-Host "  ✓ tosutil" -ForegroundColor Green }

if (-not $checklist.docker) {
    Write-Host "  ⚠ docker 未找到 (deploy.ps1 -SkipBuild 仍可工作)" -ForegroundColor Yellow
} else { Write-Host "  ✓ docker" -ForegroundColor Green }

if (-not $checklist.python) {
    Write-Host "  ✗ python 未安装" -ForegroundColor Red
    exit 1
} else { Write-Host "  ✓ python" -ForegroundColor Green }

# ---- 2) AKSK 检查 ----
Step 2 "AKSK 凭据"
$ak = $env:VOLC_ACCESS_KEY
$sk = $env:VOLC_SECRET_KEY
if (-not $ak -or -not $sk) {
    Write-Host "  ✗ VOLC_ACCESS_KEY / SECRET_KEY 未配置" -ForegroundColor Red
    Write-Host "    先跑: .\scripts\sync_keys_to_windows.ps1" -ForegroundColor Yellow
    exit 1
}
Write-Host "  ✓ AK len=$($ak.Length) SK len=$($sk.Length)" -ForegroundColor Green
$checklist.ak_present = $true

# ---- 3) ve CLI 登录 ----
Step 3 "ve CLI 登录"
if ($checklist.ve_cli) {
    try {
        $configList = & ve configure list 2>&1 | Out-String
        if ($configList -match "access[_-]key" -or $configList -match "AccessKey") {
            Write-Host "  ✓ ve configure list 已登录" -ForegroundColor Green
        } else {
            Write-Host "  ⚠ ve configure 未登录, 自动 ve configure set ..." -ForegroundColor Yellow
            if (-not $DryRun) {
                & ve configure set --access-key=$ak --secret-key=$sk --region=$Region 2>&1 | Out-Null
                Write-Host "  ✓ ve configure 完成" -ForegroundColor Green
            }
        }
    } catch {
        Write-Warning "ve configure list failed: $_"
    }
} else {
    Write-Host "  - skipped (ve CLI 未装)" -ForegroundColor DarkGray
}

# ---- 4) TOS bucket ----
Step 4 "TOS bucket: $BucketName"
if ($checklist.tosutil) {
    try {
        # tosutil config (v2.x 用 --profile)
        $tosCfgOut = & tosutil config -h 2>&1 | Out-String
        if (-not $DryRun) {
            # 静默配置 default profile
            $endpoint = "https://tos-$Region.volces.com"
            $null = & tosutil config -e $endpoint -i $ak -k $sk -re $Region 2>&1
        }

        # 列出 bucket 列表
        $listOut = & tosutil ls 2>&1 | Out-String
        if ($listOut -match $BucketName) {
            Write-Host "  ✓ bucket 已存在" -ForegroundColor Green
            $checklist.bucket_exists = $true
        } elseif ($CreateBucket) {
            if ($DryRun) {
                Write-Host "  [DRY] tosutil mb tos://$BucketName -region $Region" -ForegroundColor DarkYellow
            } else {
                $mbOut = & tosutil mb tos://$BucketName -region $Region 2>&1 | Out-String
                if ($LASTEXITCODE -eq 0) {
                    Write-Host "  ✓ bucket 创建成功" -ForegroundColor Green
                    $checklist.bucket_exists = $true
                } else {
                    Write-Host "  ✗ bucket 创建失败: $mbOut" -ForegroundColor Red
                }
            }
        } else {
            Write-Host "  ⚠ bucket 不存在; 加 -CreateBucket 自动建; 或控制台创建:" -ForegroundColor Yellow
            Write-Host "    https://console.volcengine.com/tos/bucket?region=$Region" -ForegroundColor DarkGray
        }
    } catch {
        Write-Warning "tosutil 调用失败: $_"
    }
} else {
    Write-Host "  - skipped (tosutil 未装); 控制台创建:" -ForegroundColor DarkGray
    Write-Host "    https://console.volcengine.com/tos/bucket?region=$Region" -ForegroundColor DarkGray
}

# ---- 5) 容器镜像仓库 ----
Step 5 "容器镜像仓库 (CR)"
$crHost = "cr-$Region.volces.com"
Write-Host "  期望地址: $crHost/$CRNamespace/${CRRepo}:<tag>"
Write-Host "  控制台:   https://console.volcengine.com/cr/instance" -ForegroundColor DarkGray
Write-Host "  你需要确认:" -ForegroundColor DarkGray
Write-Host "    1) 已开通 CR (免费版即可)" -ForegroundColor DarkGray
Write-Host "    2) 已创建命名空间 '$CRNamespace'" -ForegroundColor DarkGray
Write-Host "    3) 已创建仓库 '$CRRepo' 在 '$CRNamespace' 下" -ForegroundColor DarkGray
Write-Host "    4) docker login $crHost -u <AK_ID> -p <SK>" -ForegroundColor DarkGray
$checklist.cr_namespace = "$crHost/$CRNamespace/$CRRepo"

# ---- 6) veFaaS 服务开通 ----
Step 6 "veFaaS 服务"
Write-Host "  控制台: https://console.volcengine.com/vefaas" -ForegroundColor DarkGray
Write-Host "  ⚠ 首次访问需点【立即授权】(一次性 IAM 授权 ServerlessApplicationRole)" -ForegroundColor Yellow
Write-Host "  授权后跑 deploy.ps1 才能 CreateFunction" -ForegroundColor DarkGray

# ---- 7) API 网关 ----
Step 7 "API 网关"
Write-Host "  控制台: https://console.volcengine.com/veapig" -ForegroundColor DarkGray
Write-Host "  ⚠ 首次访问需点【立即授权】" -ForegroundColor Yellow
Write-Host "  授权后创建 1 个实例 + 1 个 Service + 1 个 Upstream, 拿到名字回填 config.yaml" -ForegroundColor DarkGray

# ---- 8) NAS (可选) ----
Step 8 "NAS 文件系统 (可选, SQLite 持久化)"
Write-Host "  控制台: https://console.volcengine.com/nas/instance?region=$Region" -ForegroundColor DarkGray
Write-Host "  推荐: 容量型, NFS v3, 区域必须与 veFaaS 一致 ($Region)" -ForegroundColor DarkGray
Write-Host "  创建后把 NAS ID 填到 deploy/cn-volc-vefaas/config.yaml 的 nas_mounts[0].nas_id" -ForegroundColor DarkGray

# ---- 总结报告 ----
Write-Host ""
Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "  巡检总结" -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

$report = [PSCustomObject]@{
    timestamp = (Get-Date).ToString("o")
    region    = $Region
    checks    = $checklist
}
$reportPath = Join-Path $repoRoot "data\volc_resources_check.json"
$null = New-Item -ItemType Directory -Force -Path (Split-Path $reportPath) -ErrorAction SilentlyContinue
$json = $report | ConvertTo-Json -Depth 5
[System.IO.File]::WriteAllText($reportPath, $json, [System.Text.UTF8Encoding]::new($false))

foreach ($k in $checklist.Keys | Sort-Object) {
    $v = $checklist[$k]
    $color = if ($v -eq $true) { "Green" } elseif ($v -eq $false) { "Red" } else { "Yellow" }
    Write-Host ("  {0,-18} = {1}" -f $k, $v) -ForegroundColor $color
}
Write-Host ""
Write-Host "报告写入: $reportPath" -ForegroundColor Cyan
Write-Host ""

# ---- 输出 .env 增量 (供用户拷贝) ----
Write-Host "建议追加 / 修正到 .env:" -ForegroundColor Cyan
Write-Host "----------------------------------------"
Write-Host "TOS_BUCKET=$BucketName"
Write-Host "TOS_ENDPOINT=https://tos-$Region.volces.com"
Write-Host "TOS_REGION=$Region"
Write-Host "VOLC_REGION=$Region"
Write-Host "CR_HOST=$crHost"
Write-Host "CR_NAMESPACE=$CRNamespace"
Write-Host "CR_REPO=$CRRepo"
Write-Host "----------------------------------------"
Write-Host ""
Write-Host "下一步:"
Write-Host "  - 在控制台完成上面的 3 个【立即授权】"
Write-Host "  - .\deploy\cn-volc-vefaas\deploy.ps1 -DryRun  (验证 OpenAPI payload)"
Write-Host "  - .\deploy\cn-volc-vefaas\deploy.ps1          (实跑部署)"
