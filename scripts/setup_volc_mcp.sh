#!/usr/bin/env bash
# 火山引擎开发环境一键配置 (macOS / Linux / Git-Bash on Windows)
# 等效于 setup_volc_mcp.ps1
#
# 用法: bash scripts/setup_volc_mcp.sh
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

color()  { printf "\033[%sm%s\033[0m\n" "$1" "$2"; }
green()  { color "1;32" "$*"; }
blue()   { color "1;36" "$*"; }
yellow() { color "1;33" "$*"; }
red()    { color "1;31" "$*"; }
hr()     { printf -- '------------------------------------------------------------\n'; }

# ---------- 1) 工具检测 ----------
hr; blue "[1/5] 工具检测..."
declare -A TOOLS=(
  [ve]="https://github.com/volcengine/volcengine-cli/releases"
  [tosutil]="https://tos-tools.tos-cn-beijing.volces.com/linux/tosutil (或 darwin/)"
  [uv]="curl -LsSf https://astral.sh/uv/install.sh | sh"
  [npx]="https://nodejs.org"
  [jq]="brew install jq  /  apt install jq"
)
missing=()
for t in "${!TOOLS[@]}"; do
  if command -v "$t" >/dev/null 2>&1; then
    green "  + $t  ok"
  else
    red "  X $t  缺. 安装: ${TOOLS[$t]}"
    missing+=("$t")
  fi
done
[ ${#missing[@]} -gt 0 ] && { red "请先安装上述工具"; exit 1; }

# ---------- 2) 从 .env 读取或求输入 ----------
hr; blue "[2/5] 加载 / 输入 火山引擎凭证..."

get_env() {
  local file="$1" key="$2"
  [ -f "$file" ] || return 1
  local v
  v=$(grep -E "^\s*${key}=" "$file" 2>/dev/null | head -1 | sed -E "s/^\s*${key}=//" | sed "s/^['\"]//;s/['\"]$//")
  [ -n "$v" ] && echo "$v"
}

ENV_FILES=("$ROOT_DIR/.env" "$ROOT_DIR/backend/.env" "$ROOT_DIR/deploy/cn-serverless/.env" "$ROOT_DIR/deploy/cn-serverless/.env.simple")

AK=""; SK=""; ARK_KEY=""; TOS_BUCKET=""
for f in "${ENV_FILES[@]}"; do
  [ -z "$AK" ]         && AK=$(get_env "$f" VOLC_ACCESS_KEY || get_env "$f" VOLC_AK || echo "")
  [ -z "$SK" ]         && SK=$(get_env "$f" VOLC_SECRET_KEY || get_env "$f" VOLC_SK || echo "")
  [ -z "$ARK_KEY" ]    && ARK_KEY=$(get_env "$f" VOLC_ARK_API_KEY || get_env "$f" ARK_API_KEY || echo "")
  [ -z "$TOS_BUCKET" ] && TOS_BUCKET=$(get_env "$f" S3_BUCKET || get_env "$f" TOS_BUCKET || echo "")
done

[ -z "$AK" ]      && read -rp "  VOLC_ACCESS_KEY (留空跳过): " AK
[ -n "$AK" -a -z "$SK" ] && read -rsp "  VOLC_SECRET_KEY (输入隐藏): " SK && echo
[ -z "$ARK_KEY" ] && read -rp "  VOLC_ARK_API_KEY (UUID; 留空跳过 Seedream/Jimeng): " ARK_KEY
[ -z "$TOS_BUCKET" ] && read -rp "  TOS_BUCKET (留空不预填): " TOS_BUCKET

mask() { [ -z "$1" ] && echo "(空)" || echo "${1:0:6}***"; }
green "  AK     = $(mask "$AK")"
green "  SK     = $(mask "$SK")"
green "  ArkKey = $(mask "$ARK_KEY")"
green "  TOS    = $TOS_BUCKET"

# ---------- 3) 写 .cursor/mcp.json ----------
hr; blue "[3/5] 更新 .cursor/mcp.json env..."
MCP="$ROOT_DIR/.cursor/mcp.json"

if [ -n "$AK" ]; then
  jq --arg ak "$AK" --arg sk "$SK" --arg ark "$ARK_KEY" --arg bucket "$TOS_BUCKET" '
    .mcpServers."volc-tos".env.VOLCENGINE_ACCESS_KEY = $ak
    | .mcpServers."volc-tos".env.VOLCENGINE_SECRET_KEY = $sk
    | (if $bucket != "" then .mcpServers."volc-tos".env.TOS_BUCKET = $bucket else . end)
    | .mcpServers."volc-vefaas".env.VOLCENGINE_ACCESS_KEY = $ak
    | .mcpServers."volc-vefaas".env.VOLCENGINE_SECRET_KEY = $sk
    | .mcpServers."volc-cdn".env.VOLCENGINE_ACCESS_KEY = $ak
    | .mcpServers."volc-cdn".env.VOLCENGINE_SECRET_KEY = $sk
    | .mcpServers."volc-imagex".env.VOLCENGINE_ACCESS_KEY = $ak
    | .mcpServers."volc-imagex".env.VOLCENGINE_SECRET_KEY = $sk
    | (if $ark != "" then .mcpServers."volc-jimeng".env.ARK_API_KEY = $ark else . end)
    | (if $ark != "" then .mcpServers."volc-seedream".args |= map(if test("ARK_KEY_PLACEHOLDER") then "--ark-key=" + $ark else . end) else . end)
  ' "$MCP" > "$MCP.tmp" && mv "$MCP.tmp" "$MCP"
  green "  $MCP 已更新"
else
  yellow "  跳过 (无 AKSK)"
fi

# ---------- 4) ve CLI ----------
hr; blue "[4/5] 配置 ve CLI..."
if [ -n "$AK" ] && [ -n "$SK" ]; then
  ve configure set --profile default --ak "$AK" --sk "$SK" --region cn-beijing >/dev/null 2>&1
  green "  ve 已配置 (profile=default, region=cn-beijing)"
else
  yellow "  跳过 (无 AKSK)"
fi

# ---------- 5) tosutil ----------
hr; blue "[5/5] 配置 tosutil..."
if [ -n "$AK" ] && [ -n "$SK" ]; then
  tosutil config -i "$AK" -k "$SK" -e tos-cn-beijing.volces.com -re cn-beijing >/dev/null 2>&1
  green "  tosutil 已配置"
else
  yellow "  跳过 (无 AKSK)"
fi

hr
green "========================================"
green "  火山引擎开发环境 配置完成"
green "========================================"
green "  下一步: 重启 Cursor / Reload Window, 然后:"
green "    - 直接对 AI 说: '用 volc-tos 列出 bucket 中的 mp4'"
green "    - 详情见: VOLC_DEV_SETUP.md"
hr
