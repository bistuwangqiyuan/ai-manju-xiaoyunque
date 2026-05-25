#requires -Version 5.1
<#
.SYNOPSIS
    一键部署小云雀 AI 漫剧到火山引擎 veFaaS.

.DESCRIPTION
    流程:
      1. 检查 VOLC_ACCESS_KEY / VOLC_SECRET_KEY / TOS_BUCKET 已就绪
      2. 检查 docker / python 可用
      3. (可选) docker login 火山镜像仓库
      4. docker build -> docker push
      5. python deploy.py 调火山 OpenAPI 创建/更新函数
      6. 输出公网域名

.PARAMETER ImageTag
    镜像 tag (默认 v9.<yyyyMMddHHmm>)

.PARAMETER SkipBuild
    跳过 docker build/push (基于已有镜像)

.PARAMETER DryRun
    不真正调用 OpenAPI / docker, 只打印命令

.EXAMPLE
    # 首次部署
    .\deploy.ps1

.EXAMPLE
    # 仅更新函数 (基于已有镜像)
    .\deploy.ps1 -SkipBuild -ImageTag v9.0.1
#>
[CmdletBinding()]
param(
    [string]$ImageTag = "",
    [switch]$SkipBuild,
    [switch]$DryRun,
    [string]$AppName = "xyq-manju",
    [string]$ImageRepo = ""
)

$ErrorActionPreference = "Stop"
try { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 } catch {}

$repoRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
if (-not (Test-Path "$repoRoot\backend\app\main.py")) {
    Write-Error "Cannot locate repo root; rerun from project root."
    exit 1
}
Set-Location $repoRoot

Write-Host ""
Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "  小云雀 AI 漫剧 -> 火山引擎 veFaaS (v9)" -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host ""

# ---- 1) 检查环境变量 ----
$required = @("VOLC_ACCESS_KEY", "VOLC_SECRET_KEY")
$missing = @()
foreach ($k in $required) {
    $v = [Environment]::GetEnvironmentVariable($k, "User")
    if (-not $v) { $v = [Environment]::GetEnvironmentVariable($k, "Process") }
    if (-not $v) { $missing += $k }
}
if ($missing.Count -gt 0) {
    Write-Host "缺少环境变量: $($missing -join ', ')" -ForegroundColor Red
    Write-Host "请先跑: .\scripts\sync_keys_to_windows.ps1" -ForegroundColor Yellow
    exit 1
}

# 让当前会话拿到 setx 写的值
.\scripts\load_global_keys.ps1 -Quiet

# ---- 2) 检查工具 ----
$dockerOk = $false
$pythonOk = $false
try { docker --version | Out-Null; $dockerOk = $true } catch {}
try { python --version | Out-Null; $pythonOk = $true } catch {}

if (-not $pythonOk) {
    Write-Error "python not found in PATH"
    exit 1
}
if (-not $dockerOk -and -not $SkipBuild) {
    Write-Host "docker 不可用, 自动 -SkipBuild (你需要预先把镜像 push 到火山 CR)" -ForegroundColor Yellow
    $SkipBuild = $true
}

# ---- 3) 计算 image tag ----
if (-not $ImageTag) {
    $ImageTag = "v9." + (Get-Date -Format "yyyyMMddHHmm")
}
if (-not $ImageRepo) {
    $region = $env:VOLC_REGION
    if (-not $region) { $region = "cn-beijing" }
    $ImageRepo = "cr-$region.volces.com/xyq/manju"
}
$fullImage = "${ImageRepo}:${ImageTag}"
Write-Host "Image:    $fullImage" -ForegroundColor Green
Write-Host "AppName:  $AppName" -ForegroundColor Green
Write-Host "Region:   $($env:VOLC_REGION ?? 'cn-beijing')" -ForegroundColor Green
Write-Host "DryRun:   $DryRun" -ForegroundColor Green
Write-Host ""

# ---- 4) build & push ----
if (-not $SkipBuild) {
    Write-Host "[1/3] docker build" -ForegroundColor Cyan
    $buildArgs = @(
        "build",
        "-f", "deploy/cn-volc-vefaas/Dockerfile.vefaas",
        "-t", $fullImage,
        "--platform", "linux/amd64",
        "."
    )
    if ($DryRun) {
        Write-Host "  [DRY] docker $($buildArgs -join ' ')" -ForegroundColor DarkYellow
    } else {
        & docker @buildArgs
        if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    }

    Write-Host "[2/3] docker push" -ForegroundColor Cyan
    if ($DryRun) {
        Write-Host "  [DRY] docker push $fullImage" -ForegroundColor DarkYellow
    } else {
        Write-Host "  (若未登录火山 CR, 跑: docker login cr-cn-beijing.volces.com -u <AccessKeyID>)" -ForegroundColor DarkGray
        & docker push $fullImage
        if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    }
} else {
    Write-Host "[1-2/3] 跳过 build/push (-SkipBuild)" -ForegroundColor DarkGray
}

# ---- 5) 调 OpenAPI ----
Write-Host "[3/3] python deploy.py" -ForegroundColor Cyan
$pyArgs = @(
    "deploy/cn-volc-vefaas/deploy.py",
    "--app-name", $AppName,
    "--image-repo", $ImageRepo,
    "--image-tag", $ImageTag
)
if ($DryRun) { $pyArgs += "--dry-run" }

& python @pyArgs
$rc = $LASTEXITCODE

Write-Host ""
if ($rc -eq 0) {
    Write-Host "完成!" -ForegroundColor Green
    Write-Host "  - 浏览器查看: https://console.volcengine.com/vefaas"
    Write-Host "  - 生产 smoke: python scripts\verify_volc_chain.py --live"
} else {
    Write-Host "部署失败 (exit=$rc), 请查 OpenAPI 错误日志" -ForegroundColor Red
}
exit $rc
