#!/usr/bin/env pwsh
<#
.SYNOPSIS
  Sync validated API keys from Windows User-level env vars to GitHub repo Secrets.
.DESCRIPTION
  与 sync_keys_to_windows.ps1 是镜像关系 — 后者把 .env -> Windows;
  本脚本把 Windows -> GitHub repo Secrets (用 gh CLI).

  使用前提:
    1. 已跑过 sync_keys_to_windows.ps1
    2. gh CLI 已登录 (gh auth status)
.PARAMETER Repo
  GitHub repo, 默认 bistuwangqiyuan/ai-manju-xiaoyunque
.PARAMETER DryRun
  只打印不写
.EXAMPLE
  .\scripts\sync_keys_to_github.ps1
  .\scripts\sync_keys_to_github.ps1 -DryRun
#>
[CmdletBinding()]
param(
    [string]$Repo = "bistuwangqiyuan/ai-manju-xiaoyunque",
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"

$Whitelist = @(
    # tier 1 核心
    "VOLC_ACCESS_KEY", "VOLC_SECRET_KEY", "VOLC_ARK_API_KEY", "ARK_API_KEY",
    "DOUBAO_API_KEY", "DOUBAO_ENDPOINT_ID", "DOUBAO_MODEL",
    "DOUBAO_TTS_APPID", "DOUBAO_TTS_TOKEN", "DOUBAO_TTS_CLUSTER",
    "TOS_BUCKET", "TOS_ENDPOINT", "TOS_REGION",
    # tier 2 阿里
    "ALIYUN_ACCESS_KEY_ID", "ALIYUN_ACCESS_KEY_SECRET",
    "DASHSCOPE_API_KEY", "TONGYI_API_KEY",
    # tier 3 LLM fallback
    "DEEPSEEK_API_KEY", "GLM_API_KEY", "MOONSHOT_API_KEY",
    "MISTRAL_API_KEY", "GROQ_API_KEY", "XAI_API_KEY", "SPARK_API_KEY",
    # tier 4 海外兜底
    "ANTHROPIC_API_KEY", "GEMINI_API_KEY",
    "MINIMAX_API_KEY",
    # tier 5 业务
    "JWT_SECRET", "INTERNAL_API_SECRET",
    "CN_DOMESTIC_MODE", "LLM_PROVIDER_CHAIN",
    "TTS_PRIMARY", "IMAGE_GEN_PRIMARY", "SCHEMA_VALIDATOR"
)

function Test-Placeholder {
    param([string]$Value)
    if ([string]::IsNullOrWhiteSpace($Value)) { return $true }
    if ($Value.Length -lt 4) { return $true }
    $patterns = @('<paste-', '<paste_', 'REPLACE_ME', 'your-', 'YOUR_',
                  'xxxx', 'placeholder', '{{', '${', 'api-key-')
    foreach ($p in $patterns) {
        if ($Value -like "*$p*") { return $true }
    }
    return $false
}

Write-Host "================================================================" -ForegroundColor Cyan
Write-Host " Sync Windows env -> GitHub Secrets ($Repo)" -ForegroundColor Cyan
Write-Host "================================================================" -ForegroundColor Cyan

$ok = 0; $skip = 0; $fail = 0
$ghOk = $false
try { gh auth status 2>&1 | Out-Null; $ghOk = $true } catch {}
if (-not $ghOk) {
    Write-Host "FATAL: gh CLI not authenticated. Run: gh auth login" -ForegroundColor Red
    exit 1
}

foreach ($key in $Whitelist) {
    $v = [Environment]::GetEnvironmentVariable($key, "User")
    if (-not $v) { $v = [Environment]::GetEnvironmentVariable($key, "Machine") }
    if (Test-Placeholder $v) {
        Write-Host "[SKIP] $key (empty or placeholder)" -ForegroundColor DarkGray
        $skip++
        continue
    }
    if ($DryRun) {
        Write-Host "[DRY ] $key  (len=$($v.Length))" -ForegroundColor Yellow
        $ok++
        continue
    }
    try {
        $v | gh secret set $key --repo $Repo 2>&1 | Out-Null
        Write-Host "[OK  ] $key  (len=$($v.Length))" -ForegroundColor Green
        $ok++
    }
    catch {
        Write-Host "[FAIL] $key — $_" -ForegroundColor Red
        $fail++
    }
}

Write-Host ""
Write-Host "----------------------------------------------------------------" -ForegroundColor Cyan
Write-Host " Done: ok=$ok  skipped=$skip  failed=$fail" -ForegroundColor Cyan
Write-Host ""
if ($DryRun) { Write-Host "(dry-run; nothing written)" -ForegroundColor Yellow }
Write-Host "Verify: gh secret list --repo $Repo" -ForegroundColor DarkGray
