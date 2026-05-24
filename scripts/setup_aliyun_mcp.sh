#!/usr/bin/env bash
# 阿里云开发环境 一键配置 (macOS / Linux / Git-Bash on Windows)
# 等效于 setup_aliyun_mcp.ps1
#
# 用法: bash scripts/setup_aliyun_mcp.sh
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
  [aliyun]="https://github.com/aliyun/aliyun-cli/releases"
  [ossutil]="https://gosspublic.alicdn.com/ossutil/v2/2.3.0/"
  [uv]="curl -LsSf https://astral.sh/uv/install.sh | sh"
  [uvx]="随 uv 一起装"
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

# ---------- 2) 读 / 求输入 ----------
hr; blue "[2/5] 加载 / 输入 阿里云凭证..."
get_env() {
  local file="$1" key="$2"
  [ -f "$file" ] || return 1
  grep -E "^\s*${key}=" "$file" 2>/dev/null | head -1 | sed -E "s/^\s*${key}=//" | sed "s/^['\"]//;s/['\"]$//"
}
ENV_FILES=("$ROOT_DIR/.env" "$ROOT_DIR/backend/.env"
           "$ROOT_DIR/deploy/cn-serverless/.env" "$ROOT_DIR/deploy/cn-serverless/.env.simple")

AK=""; SK=""; DASH=""; OSS_BUCKET=""; OSS_ENDPOINT=""; OSS_REGION=""
for f in "${ENV_FILES[@]}"; do
  [ -z "$AK" ]           && AK=$(get_env "$f" ALIBABA_CLOUD_ACCESS_KEY_ID || get_env "$f" ALIYUN_ACCESS_KEY_ID || echo "")
  [ -z "$SK" ]           && SK=$(get_env "$f" ALIBABA_CLOUD_ACCESS_KEY_SECRET || get_env "$f" ALIYUN_ACCESS_KEY_SECRET || echo "")
  [ -z "$DASH" ]         && DASH=$(get_env "$f" DASHSCOPE_API_KEY || echo "")
  [ -z "$OSS_BUCKET" ]   && OSS_BUCKET=$(get_env "$f" OSS_BUCKET || echo "")
  [ -z "$OSS_ENDPOINT" ] && OSS_ENDPOINT=$(get_env "$f" OSS_ENDPOINT || echo "")
  [ -z "$OSS_REGION" ]   && OSS_REGION=$(get_env "$f" OSS_REGION || echo "")
done

[ -z "$OSS_REGION" ]   && OSS_REGION="cn-hangzhou"
[ -z "$OSS_ENDPOINT" ] && OSS_ENDPOINT="https://oss-$OSS_REGION.aliyuncs.com"

[ -z "$AK" ]    && read -rp "  ALIBABA_CLOUD_ACCESS_KEY_ID (LTAI 开头; 留空跳过): " AK
[ -n "$AK" -a -z "$SK" ] && read -rsp "  ALIBABA_CLOUD_ACCESS_KEY_SECRET: " SK && echo
[ -z "$DASH" ] && read -rp "  DASHSCOPE_API_KEY (sk-xxx; 留空跳过百炼): " DASH
[ -z "$OSS_BUCKET" ] && read -rp "  OSS_BUCKET (留空不预填): " OSS_BUCKET

mask() { [ -z "$1" ] && echo "(空)" || echo "${1:0:6}***"; }
green "  AccessKeyID     = $(mask "$AK")"
green "  AccessKeySecret = $(mask "$SK")"
green "  DashScope Key   = $(mask "$DASH")"
green "  OSS Bucket      = $OSS_BUCKET"
green "  OSS Region      = $OSS_REGION"
green "  OSS Endpoint    = $OSS_ENDPOINT"

# ---------- 3) 写 .cursor/mcp.json ----------
hr; blue "[3/5] 更新 .cursor/mcp.json env..."
MCP="$ROOT_DIR/.cursor/mcp.json"
MCP_EX="$ROOT_DIR/.cursor/mcp.json.example"
# 首次运行: 从模板复制 (mcp.json 在 .gitignore 里, 不会被入库)
[ -f "$MCP" ] || { [ -f "$MCP_EX" ] && cp "$MCP_EX" "$MCP" && green "  从 mcp.json.example 复制初始模板"; }

if [ -n "$AK" ]; then
  jq --arg ak "$AK" --arg sk "$SK" --arg dash "$DASH" '
    .mcpServers."aliyun-ops".env.ALIBABA_CLOUD_ACCESS_KEY_ID = $ak
    | .mcpServers."aliyun-ops".env.ALIBABA_CLOUD_ACCESS_KEY_SECRET = $sk
    | .mcpServers."aliyun-rds".env.ALIBABA_CLOUD_ACCESS_KEY_ID = $ak
    | .mcpServers."aliyun-rds".env.ALIBABA_CLOUD_ACCESS_KEY_SECRET = $sk
    | .mcpServers."aliyun-fc".env.ALIBABA_CLOUD_ACCESS_KEY_ID = $ak
    | .mcpServers."aliyun-fc".env.ALIBABA_CLOUD_ACCESS_KEY_SECRET = $sk
    | .mcpServers."aliyun-observability".env.ALIBABA_CLOUD_ACCESS_KEY_ID = $ak
    | .mcpServers."aliyun-observability".env.ALIBABA_CLOUD_ACCESS_KEY_SECRET = $sk
    | (if $dash != "" then .mcpServers."aliyun-bailian-websearch".headers.Authorization = ("Bearer " + $dash) else . end)
  ' "$MCP" > "$MCP.tmp" && mv "$MCP.tmp" "$MCP"
  green "  $MCP 已更新"
else
  yellow "  跳过 (无 AKSK)"
fi

# ---------- 4) aliyun CLI ----------
hr; blue "[4/5] 配置 aliyun CLI..."
if [ -n "$AK" ] && [ -n "$SK" ]; then
  aliyun configure set --profile default --mode AK --region "$OSS_REGION" \
                       --access-key-id "$AK" --access-key-secret "$SK" >/dev/null 2>&1
  green "  aliyun 已配置 (profile=default, region=$OSS_REGION)"
else
  yellow "  跳过 (无 AKSK)"
fi

# ---------- 5) ossutil ----------
hr; blue "[5/5] 配置 ossutil..."
if [ -n "$AK" ] && [ -n "$SK" ]; then
  ossutil config set accessKeyID "$AK" --profile default >/dev/null 2>&1
  ossutil config set accessKeySecret "$SK" --profile default >/dev/null 2>&1
  ossutil config set region "$OSS_REGION" --profile default >/dev/null 2>&1
  green "  ossutil 已配置 (profile=default, region=$OSS_REGION)"
else
  yellow "  跳过 (无 AKSK)"
fi

hr
green "========================================"
green "  阿里云开发环境 配置完成"
green "========================================"
green "  下一步: 重启 Cursor / Reload Window"
green "  详细文档: ALIYUN_DEV_SETUP.md"
hr
