#!/usr/bin/env bash
# =============================================================================
# 小云雀 AI 漫剧 · 无服务器一键部署 (macOS / Linux / Git-Bash on Windows)
#
# 前提：
#   1. 已安装 node 18+ 和 npm
#   2. 已在 deploy/cn-serverless/.env 填好 TENCENT_SECRET_ID / TENCENT_SECRET_KEY /
#      ENV_ID / DATABASE_URL / JWT_SECRET / INTERNAL_API_SECRET (其它可后填)
#
# 使用：
#   cd deploy/cn-serverless
#   cp .env.example .env  # 编辑填入真实值
#   bash deploy.sh        # 一键执行: 装 CLI → 登录 → 部署 backend → 部署 SCF
# =============================================================================
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
SL_DIR="$ROOT_DIR/deploy/cn-serverless"
cd "$SL_DIR"

if [ ! -f .env ]; then
  echo "ERROR: 缺少 .env，请先 cp .env.example .env 并填值"
  exit 1
fi
set -a; source .env; set +a

color() { printf "\033[%sm%s\033[0m\n" "$1" "$2"; }
green() { color "1;32" "$*"; }
blue()  { color "1;36" "$*"; }
yellow(){ color "1;33" "$*"; }
red()   { color "1;31" "$*"; }
hr() { printf -- '------------------------------------------------------------\n'; }

# ---------- 1. 安装 CLI ----------
hr; blue "[1/5] 检查 / 安装 CLI..."
command -v tcb >/dev/null || npm i -g @cloudbase/cli@latest
command -v scf >/dev/null || npm i -g serverless@3 @tencent-sdk/cloud-cli || true
green "tcb $(tcb -v 2>/dev/null || echo n/a)  |  scf-cli ready"

# ---------- 2. 登录腾讯云 ----------
hr; blue "[2/5] 登录腾讯云 (使用 AKSK)..."
tcb login --apiKeyId "$TENCENT_SECRET_ID" --apiKey "$TENCENT_SECRET_KEY" || true

# ---------- 3. 部署 backend (CloudBase 云托管) ----------
hr; blue "[3/5] 部署 backend 到 CloudBase 云托管 envId=$ENV_ID..."
cd "$ROOT_DIR"
# tcb framework 会读取 deploy/cn-serverless/cloudbaserc.json
ENV_ID="$ENV_ID" \
DATABASE_URL="$DATABASE_URL" \
JWT_SECRET="$JWT_SECRET" \
INTERNAL_API_SECRET="$INTERNAL_API_SECRET" \
CORS_ORIGINS="$CORS_ORIGINS" \
SITE_URL="$SITE_URL" \
COS_ENDPOINT="${COS_ENDPOINT:-}" \
COS_REGION="${COS_REGION:-}" \
COS_BUCKET="${COS_BUCKET:-}" \
COS_SECRET_ID="${COS_SECRET_ID:-}" \
COS_SECRET_KEY="${COS_SECRET_KEY:-}" \
COS_PUBLIC_BASE_URL="${COS_PUBLIC_BASE_URL:-}" \
MOCK_MODE="${MOCK_MODE:-0}" \
VOLC_ARK_API_KEY="${VOLC_ARK_API_KEY:-}" \
VOLC_ACCESS_KEY="${VOLC_ACCESS_KEY:-}" \
VOLC_SECRET_KEY="${VOLC_SECRET_KEY:-}" \
DOUBAO_API_KEY="${DOUBAO_API_KEY:-}" \
DOUBAO_TTS_APPID="${DOUBAO_TTS_APPID:-}" \
DOUBAO_TTS_TOKEN="${DOUBAO_TTS_TOKEN:-}" \
ANTHROPIC_API_KEY="${ANTHROPIC_API_KEY:-}" \
ANTHROPIC_MODEL="${ANTHROPIC_MODEL:-claude-opus-4-7-20260413}" \
DEEPSEEK_API_KEY="${DEEPSEEK_API_KEY:-}" \
DASHSCOPE_API_KEY="${DASHSCOPE_API_KEY:-}" \
MINIMAX_API_KEY="${MINIMAX_API_KEY:-}" \
tcb framework deploy -e "$ENV_ID" --config-file deploy/cn-serverless/cloudbaserc.json

# 从 tcb 输出推断 backend URL
BACKEND_URL_DEPLOYED=$(tcb run service:list -e "$ENV_ID" --json 2>/dev/null | \
  node -e "let s=''; process.stdin.on('data',c=>s+=c).on('end',()=>{try{const j=JSON.parse(s);const x=(j.find(x=>x.name==='${BACKEND_SERVICE_NAME:-xyq-backend}')||{});console.log(x.url||'');}catch(e){}});" 2>/dev/null || true)

if [ -n "$BACKEND_URL_DEPLOYED" ]; then
  BACKEND_URL="$BACKEND_URL_DEPLOYED"
  green "Backend URL: $BACKEND_URL"
else
  yellow "无法自动获取 backend URL，请到 CloudBase 控制台查看后回填 .env 的 BACKEND_URL"
fi

# ---------- 4. 部署 SCF worker tick ----------
hr; blue "[4/5] 部署 SCF 定时 worker tick..."
if [ -z "${BACKEND_URL:-}" ] || [ "$BACKEND_URL" = "https://xyq-backend-xxxxx-1300000000.ap-shanghai.run.tcloudbase.com" ]; then
  yellow "跳过：BACKEND_URL 尚未填入真实值。请先在 CloudBase 控制台拿到 URL 后回填 .env 再重跑"
else
  cd "$SL_DIR/scf-worker-tick"
  cat > .env <<EOF
BACKEND_URL=$BACKEND_URL
INTERNAL_API_SECRET=$INTERNAL_API_SECRET
EOF
  # 替换 template.yaml 中的占位
  sed -e "s|\\\${BACKEND_URL}|$BACKEND_URL|g" \
      -e "s|\\\${INTERNAL_API_SECRET}|$INTERNAL_API_SECRET|g" \
      template.yaml > template.deploy.yaml
  scf deploy --template-file template.deploy.yaml -r "$TENCENT_REGION" || \
    yellow "(SCF 部署失败，请检查 scf CLI 是否登录: scf configure set)"
  rm -f .env template.deploy.yaml
fi

# ---------- 5. 烟雾测试 ----------
hr; blue "[5/5] 烟雾测试..."
if [ -n "${BACKEND_URL:-}" ]; then
  echo "GET $BACKEND_URL/api/health"
  curl -fsS "$BACKEND_URL/api/health" || red "Health 失败"
  echo
  echo "POST $BACKEND_URL/api/internal/worker/tick"
  curl -fsS -X POST -H "Content-Type: application/json" \
    -H "X-Internal-Secret: $INTERNAL_API_SECRET" \
    -d '{"max_jobs":1}' "$BACKEND_URL/api/internal/worker/tick" || red "Tick 失败"
  echo
fi

hr
green "=========================================="
green "  Serverless 部署完成"
green "=========================================="
green "  下一步："
green "    1) 把 BACKEND_URL ($BACKEND_URL) 填到 EdgeOne Pages 项目的环境变量"
green "    2) EdgeOne 控制台 → 导入 GitHub → 选 web/ 目录 → 部署"
green "  EdgeOne 入口: https://console.cloud.tencent.com/edgeone/pages"
hr
