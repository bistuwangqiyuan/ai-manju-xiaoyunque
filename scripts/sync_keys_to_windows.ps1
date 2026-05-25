#requires -Version 5.1
<#
.SYNOPSIS
    Sync verified API keys from project .env to Windows user environment + Credential Manager.

.DESCRIPTION
    将本仓库 .env / deploy/cn-serverless/.env 中已验证的 API Key 同步到 Windows 用户级
    环境变量 (setx) 与 Windows Credential Manager (cmdkey), 让 "数十个项目" 直接复用。

    双轨写入策略:
      1. setx <KEY> <VALUE>            -> HKCU\Environment, 持久化, 新开的 PS/CMD 自动可见
      2. cmdkey /generic:XYQ_<KEY> ... -> 凭据管理器, 提供审计轨迹 / 备份 / 高敏感场景

    跑完后:
      - 新开 PowerShell / CMD 即可 $env:DEEPSEEK_API_KEY 等用
      - 凭据管理器查询: cmdkey /list:XYQ_*
      - 同步报告: data/windows_keys_synced.json (key 名 + 长度 + sha256 前 8 字 + 时间)

.PARAMETER EnvFile
    要读取的 .env 文件路径; 默认按优先级搜索 .env -> deploy/cn-serverless/.env

.PARAMETER DryRun
    只打印, 不真正写入注册表 / Credential Manager

.PARAMETER NoCredentialManager
    跳过 Credential Manager 写入, 仅写 setx (更快, 但失去备份轨迹)

.PARAMETER Verbose
    输出详细 setx / cmdkey 命令

.EXAMPLE
    # 一键同步, 推荐
    .\scripts\sync_keys_to_windows.ps1

.EXAMPLE
    # 预演, 不真写
    .\scripts\sync_keys_to_windows.ps1 -DryRun

.EXAMPLE
    # 指定 .env
    .\scripts\sync_keys_to_windows.ps1 -EnvFile .\deploy\cn-serverless\.env
#>
[CmdletBinding()]
param(
    [string]$EnvFile = "",
    [switch]$DryRun,
    [switch]$NoCredentialManager
)

$ErrorActionPreference = "Stop"
$script:HasUtf8Console = $false
try {
    [Console]::OutputEncoding = [System.Text.Encoding]::UTF8
    $script:HasUtf8Console = $true
} catch {}

# ---------------------------------------------------------------------------
# 已验证 Key 白名单 - 跨项目复用
# ---------------------------------------------------------------------------
# 分类:
#   tier 1 (核心国产): 全部 setx + Credential Manager 双轨, 跨项目最常用
#   tier 2 (海外兜底): setx + Credential Manager 双轨, fallback 用
#   tier 3 (配置/非密): 只 setx, 不写凭据 (region / endpoint / bucket 等)
$WhitelistKeys = @(
    # ---- tier 1: 火山引擎核心 ----
    @{ Name="VOLC_ACCESS_KEY";       Tier=1; Category="volc";   Sensitive=$true  },
    @{ Name="VOLC_SECRET_KEY";       Tier=1; Category="volc";   Sensitive=$true  },
    @{ Name="VOLC_ARK_API_KEY";      Tier=1; Category="volc";   Sensitive=$true  },
    @{ Name="ARK_API_KEY";           Tier=1; Category="volc";   Sensitive=$true  },
    @{ Name="DOUBAO_API_KEY";        Tier=1; Category="volc";   Sensitive=$true  },
    @{ Name="DOUBAO_ENDPOINT_ID";    Tier=1; Category="volc";   Sensitive=$false },
    @{ Name="DOUBAO_MODEL";          Tier=3; Category="volc";   Sensitive=$false },
    @{ Name="DOUBAO_TTS_APPID";      Tier=1; Category="volc";   Sensitive=$true  },
    @{ Name="DOUBAO_TTS_TOKEN";      Tier=1; Category="volc";   Sensitive=$true  },
    @{ Name="DOUBAO_TTS_CLUSTER";    Tier=3; Category="volc";   Sensitive=$false },
    @{ Name="ARK_BASE_URL";          Tier=3; Category="volc";   Sensitive=$false },
    @{ Name="VOLC_ARK_ENDPOINT";     Tier=3; Category="volc";   Sensitive=$false },
    @{ Name="VOLC_ARK_ENDPOINT_ID";  Tier=3; Category="volc";   Sensitive=$false },
    @{ Name="VOLC_REGION";           Tier=3; Category="volc";   Sensitive=$false },
    @{ Name="TOS_BUCKET";            Tier=3; Category="volc";   Sensitive=$false },
    @{ Name="TOS_ENDPOINT";          Tier=3; Category="volc";   Sensitive=$false },
    @{ Name="S3_ACCESS_KEY";         Tier=1; Category="volc";   Sensitive=$true  },
    @{ Name="S3_SECRET_KEY";         Tier=1; Category="volc";   Sensitive=$true  },
    @{ Name="S3_BUCKET";             Tier=3; Category="volc";   Sensitive=$false },
    @{ Name="S3_ENDPOINT";           Tier=3; Category="volc";   Sensitive=$false },
    @{ Name="S3_REGION";             Tier=3; Category="volc";   Sensitive=$false },

    # ---- tier 1: 阿里云核心 ----
    @{ Name="ALIYUN_ACCESS_KEY_ID";          Tier=1; Category="aliyun"; Sensitive=$true  },
    @{ Name="ALIYUN_ACCESS_KEY_SECRET";      Tier=1; Category="aliyun"; Sensitive=$true  },
    @{ Name="ALIBABA_CLOUD_ACCESS_KEY_ID";   Tier=1; Category="aliyun"; Sensitive=$true  },
    @{ Name="ALIBABA_CLOUD_ACCESS_KEY_SECRET"; Tier=1; Category="aliyun"; Sensitive=$true },
    @{ Name="DASHSCOPE_API_KEY";    Tier=1; Category="aliyun"; Sensitive=$true  },
    @{ Name="TONGYI_API_KEY";       Tier=1; Category="aliyun"; Sensitive=$true  },
    @{ Name="OSS_REGION";           Tier=3; Category="aliyun"; Sensitive=$false },
    @{ Name="OSS_ENDPOINT";         Tier=3; Category="aliyun"; Sensitive=$false },
    @{ Name="DASHSCOPE_MODEL";      Tier=3; Category="aliyun"; Sensitive=$false },
    @{ Name="TONGYI_MODEL";         Tier=3; Category="aliyun"; Sensitive=$false },

    # ---- tier 1: LLM Fallback Chain (Phase 2) ----
    @{ Name="DEEPSEEK_API_KEY";     Tier=1; Category="llm-chain"; Sensitive=$true },
    @{ Name="DEEPSEEK_MODEL";       Tier=3; Category="llm-chain"; Sensitive=$false },
    @{ Name="GLM_API_KEY";          Tier=1; Category="llm-chain"; Sensitive=$true },
    @{ Name="GLM_MODEL";            Tier=3; Category="llm-chain"; Sensitive=$false },
    @{ Name="MOONSHOT_API_KEY";     Tier=1; Category="llm-chain"; Sensitive=$true },
    @{ Name="MOONSHOT_MODEL";       Tier=3; Category="llm-chain"; Sensitive=$false },
    @{ Name="MISTRAL_API_KEY";      Tier=1; Category="llm-chain"; Sensitive=$true },
    @{ Name="MISTRAL_MODEL";        Tier=3; Category="llm-chain"; Sensitive=$false },
    @{ Name="GROQ_API_KEY";         Tier=1; Category="llm-chain"; Sensitive=$true },
    @{ Name="GROQ_MODEL";           Tier=3; Category="llm-chain"; Sensitive=$false },
    @{ Name="XAI_API_KEY";          Tier=1; Category="llm-chain"; Sensitive=$true },
    @{ Name="XAI_MODEL";            Tier=3; Category="llm-chain"; Sensitive=$false },
    @{ Name="SPARK_API_KEY";        Tier=1; Category="llm-chain"; Sensitive=$true },
    @{ Name="SPARK_MODEL";          Tier=3; Category="llm-chain"; Sensitive=$false },

    # ---- tier 2: 海外兜底 ----
    @{ Name="ANTHROPIC_API_KEY";    Tier=2; Category="overseas"; Sensitive=$true },
    @{ Name="ANTHROPIC_MODEL";      Tier=3; Category="overseas"; Sensitive=$false },
    @{ Name="ANTHROPIC_BASE_URL";   Tier=3; Category="overseas"; Sensitive=$false },
    @{ Name="GEMINI_API_KEY";       Tier=2; Category="overseas"; Sensitive=$true },

    # ---- tier 1: 腾讯云 ----
    @{ Name="TENCENT_SECRET_ID";    Tier=1; Category="tencent"; Sensitive=$true  },
    @{ Name="TENCENT_SECRET_KEY";   Tier=1; Category="tencent"; Sensitive=$true  },
    @{ Name="TENCENT_REGION";       Tier=3; Category="tencent"; Sensitive=$false }
)

# ---------------------------------------------------------------------------
# .env 解析
# ---------------------------------------------------------------------------
function Get-DotEnvFile {
    param([string]$Explicit)
    if ($Explicit -and (Test-Path $Explicit)) { return (Resolve-Path $Explicit).Path }
    $candidates = @(
        ".\.env",
        ".\deploy\cn-serverless\.env",
        ".\backend\.env"
    )
    foreach ($p in $candidates) {
        if (Test-Path $p) { return (Resolve-Path $p).Path }
    }
    return $null
}

function Parse-DotEnv {
    param([string]$Path)
    $result = @{}
    if (-not (Test-Path $Path)) { return $result }
    $rawLines = Get-Content -Path $Path -Encoding UTF8
    foreach ($line in $rawLines) {
        if ([string]::IsNullOrWhiteSpace($line)) { continue }
        $t = $line.Trim()
        if ($t.StartsWith("#")) { continue }
        $eq = $t.IndexOf("=")
        if ($eq -lt 1) { continue }
        $k = $t.Substring(0, $eq).Trim()
        $v = $t.Substring($eq + 1).Trim()
        # strip surrounding quotes
        if (($v.StartsWith('"') -and $v.EndsWith('"')) -or `
            ($v.StartsWith("'") -and $v.EndsWith("'"))) {
            $v = $v.Substring(1, $v.Length - 2)
        }
        # strip inline trailing comment ( whitespace + # )
        $hashIdx = -1
        for ($i = 0; $i -lt $v.Length - 1; $i++) {
            if ($v[$i] -eq ' ' -and $v[$i+1] -eq '#') { $hashIdx = $i; break }
            if ($v[$i] -eq "`t" -and $v[$i+1] -eq '#') { $hashIdx = $i; break }
        }
        if ($hashIdx -gt 0) { $v = $v.Substring(0, $hashIdx).Trim() }
        if (-not [string]::IsNullOrWhiteSpace($v)) {
            $result[$k] = $v
        }
    }
    return $result
}

function Merge-EnvSources {
    # 优先级: .env > deploy/cn-serverless/.env > backend/.env
    $merged = @{}
    $files = @(".\backend\.env", ".\deploy\cn-serverless\.env", ".\.env")
    foreach ($f in $files) {
        if (Test-Path $f) {
            $parsed = Parse-DotEnv $f
            foreach ($k in $parsed.Keys) {
                $merged[$k] = $parsed[$k]
            }
        }
    }
    return $merged
}

# ---------------------------------------------------------------------------
# 写入器
# ---------------------------------------------------------------------------
function Set-UserEnvVar {
    param(
        [string]$Name,
        [string]$Value,
        [switch]$DryRun
    )
    # setx 限制 1024 字符; 超长 key 改用 [Environment]::SetEnvironmentVariable
    # ($Value 通常 < 200 字符)
    if ($DryRun) {
        Write-Host "  [DRY] setx $Name <hidden $($Value.Length) chars>" -ForegroundColor DarkYellow
        return $true
    }
    try {
        if ($Value.Length -gt 1024) {
            [Environment]::SetEnvironmentVariable($Name, $Value, "User")
        } else {
            $null = & setx $Name $Value 2>&1
            if ($LASTEXITCODE -ne 0) {
                # fallback to API
                [Environment]::SetEnvironmentVariable($Name, $Value, "User")
            }
        }
        # also set in current session for immediate use
        Set-Item -Path "env:$Name" -Value $Value -Force
        return $true
    } catch {
        Write-Warning "setx $Name failed: $_"
        return $false
    }
}

function Set-CredentialManager {
    param(
        [string]$Name,
        [string]$Value,
        [switch]$DryRun
    )
    $target = "XYQ_$Name"
    if ($DryRun) {
        Write-Host "  [DRY] cmdkey /generic:$target /user:apikey /pass:<hidden>" -ForegroundColor DarkYellow
        return $true
    }
    try {
        # cmdkey 输出在 PS5.1 上偶尔有 BOM; 走 Start-Process 静默
        $args = @("/generic:$target", "/user:apikey", "/pass:$Value")
        $proc = Start-Process -FilePath "cmdkey.exe" -ArgumentList $args `
            -NoNewWindow -Wait -PassThru -RedirectStandardOutput "$env:TEMP\cmdkey.out" `
            -RedirectStandardError "$env:TEMP\cmdkey.err"
        if ($proc.ExitCode -ne 0) {
            $err = Get-Content "$env:TEMP\cmdkey.err" -ErrorAction SilentlyContinue
            Write-Warning "cmdkey $target failed (exit=$($proc.ExitCode)): $err"
            return $false
        }
        return $true
    } catch {
        Write-Warning "cmdkey $target threw: $_"
        return $false
    } finally {
        Remove-Item "$env:TEMP\cmdkey.out","$env:TEMP\cmdkey.err" -ErrorAction SilentlyContinue
    }
}

# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------
$repoRoot = Split-Path -Parent $PSScriptRoot
if (-not $repoRoot) { $repoRoot = (Get-Location).Path }
Set-Location $repoRoot

Write-Host ""
Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "  AI 漫剧 Windows 全局 Key 同步工具 (v1.0)" -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "工作目录: $repoRoot"
Write-Host "DryRun:   $DryRun"
Write-Host "Credential Manager: $(if($NoCredentialManager){'skip'}else{'enabled'})"
Write-Host ""

$envValues = if ($EnvFile) { Parse-DotEnv (Get-DotEnvFile $EnvFile) } else { Merge-EnvSources }
Write-Host "读取到 $($envValues.Count) 个变量, 白名单 $($WhitelistKeys.Count) 个 keys" -ForegroundColor Green
Write-Host ""

$report = @{
    timestamp = (Get-Date).ToString("o")
    env_files_used = @()
    written = @()
    skipped = @()
    failed = @()
    summary = @{ total=0; setx_ok=0; cm_ok=0; setx_failed=0; cm_failed=0; skipped=0 }
}

foreach ($f in @(".\.env", ".\deploy\cn-serverless\.env", ".\backend\.env")) {
    if (Test-Path $f) { $report.env_files_used += (Resolve-Path $f).Path }
}

foreach ($spec in $WhitelistKeys) {
    $name = $spec.Name
    $tier = $spec.Tier
    $category = $spec.Category
    $sensitive = $spec.Sensitive

    if (-not $envValues.ContainsKey($name)) {
        $report.skipped += @{ name=$name; reason="not_in_env"; tier=$tier; category=$category }
        $report.summary.skipped++
        continue
    }
    $value = $envValues[$name]
    if ([string]::IsNullOrWhiteSpace($value)) {
        $report.skipped += @{ name=$name; reason="empty_value"; tier=$tier; category=$category }
        $report.summary.skipped++
        continue
    }
    # 跳过占位
    if ($value -match "^(REPLACE_ME|YOUR_|\$\{|xxxx|placeholder)" -or $value.Length -lt 4) {
        $report.skipped += @{ name=$name; reason="placeholder_value"; tier=$tier; category=$category }
        $report.summary.skipped++
        continue
    }

    $hashHex = ""
    try {
        $sha = [System.Security.Cryptography.SHA256]::Create()
        $bytes = [System.Text.Encoding]::UTF8.GetBytes($value)
        $hashHex = ([System.BitConverter]::ToString($sha.ComputeHash($bytes)) -replace '-','').Substring(0,8).ToLowerInvariant()
    } catch {}

    $tierLabel = "[t$tier]"
    $catLabel = "($category)".PadRight(13)
    Write-Host "$tierLabel $catLabel $name [len=$($value.Length) sha=$hashHex]" -ForegroundColor Gray

    $setxOk = Set-UserEnvVar -Name $name -Value $value -DryRun:$DryRun
    if ($setxOk) { $report.summary.setx_ok++ } else { $report.summary.setx_failed++ }

    $cmOk = $false
    if ($sensitive -and -not $NoCredentialManager) {
        $cmOk = Set-CredentialManager -Name $name -Value $value -DryRun:$DryRun
        if ($cmOk) { $report.summary.cm_ok++ } else { $report.summary.cm_failed++ }
    }

    $entry = @{
        name = $name
        tier = $tier
        category = $category
        sensitive = $sensitive
        length = $value.Length
        sha256_8 = $hashHex
        setx = if ($setxOk) { "ok" } else { "failed" }
        credential_manager = if ($NoCredentialManager) { "skipped" } elseif ($sensitive) { if ($cmOk) {"ok"} else {"failed"} } else { "not_required" }
    }
    if ($setxOk -or $cmOk) {
        $report.written += $entry
    } else {
        $report.failed += $entry
    }
    $report.summary.total++
}

# ---------------------------------------------------------------------------
# 写入报告
# ---------------------------------------------------------------------------
$dataDir = Join-Path $repoRoot "data"
if (-not (Test-Path $dataDir)) { New-Item -ItemType Directory -Path $dataDir | Out-Null }
$reportPath = Join-Path $dataDir "windows_keys_synced.json"

$json = $report | ConvertTo-Json -Depth 6
[System.IO.File]::WriteAllText($reportPath, $json, [System.Text.UTF8Encoding]::new($false))

Write-Host ""
Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "  同步完成" -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "  总计扫描:   $($report.summary.total)" -ForegroundColor Green
Write-Host "  setx 成功:  $($report.summary.setx_ok)" -ForegroundColor Green
if (-not $NoCredentialManager) {
    Write-Host "  CredMgr 成功: $($report.summary.cm_ok)" -ForegroundColor Green
}
Write-Host "  跳过:       $($report.summary.skipped)" -ForegroundColor Yellow
if ($report.summary.setx_failed -gt 0 -or $report.summary.cm_failed -gt 0) {
    Write-Host "  失败:       setx=$($report.summary.setx_failed)  cm=$($report.summary.cm_failed)" -ForegroundColor Red
}
Write-Host ""
Write-Host "  报告: $reportPath" -ForegroundColor Cyan
Write-Host ""
Write-Host "下一步:" -ForegroundColor Cyan
Write-Host "  1. 关闭并重开 PowerShell / VS Code / Cursor (让 setx 生效)"
Write-Host "  2. 验证: `$env:DEEPSEEK_API_KEY  (任意新 shell)"
Write-Host "  3. 在其他项目用: . `"$repoRoot\scripts\load_global_keys.ps1`""
Write-Host "  4. 凭据管理器查询: cmdkey /list:XYQ_*"
Write-Host ""
