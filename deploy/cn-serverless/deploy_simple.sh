#!/usr/bin/env bash
# 极简一键 Serverless 部署 (macOS / Linux / Git-Bash)
# 用法:
#   cd deploy/cn-serverless
#   cp .env.simple.example .env.simple
#   nano .env.simple   # 填 3 个值
#   bash deploy_simple.sh
set -euo pipefail

SL_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(cd "$SL_DIR/../.." && pwd)"
cd "$SL_DIR"

color()  { printf "\033[%sm%s\033[0m\n" "$1" "$2"; }
green()  { color "1;32" "$*"; }
blue()   { color "1;36" "$*"; }
yellow() { color "1;33" "$*"; }
red()    { color "1;31" "$*"; exit 1; }
hr()     { printf -- '============================================================\n'; }

# ---------- 0) 读 .env.simple ----------
if [ ! -f .env.simple ]; then
  red "缺少 .env.simple. 请: cp .env.simple.example .env.simple && nano .env.simple"
fi
set -a; source .env.simple; set +a

# ---------- 1) 校验 ----------
hr; blue "[1/6] 校验必填字段..."
[ -z "${TENCENT_SECRET_ID:-}" ] && red "缺少 TENCENT_SECRET_ID (.env.simple)"
[ -z "${TENCENT_SECRET_KEY:-}" ] && red "缺少 TENCENT_SECRET_KEY (.env.simple)"
[ -z "${ENV_ID:-}" ] && red "缺少 ENV_ID (.env.simple)"
[[ "$TENCENT_SECRET_ID" != AKID* ]] && yellow "[警告] TENCENT_SECRET_ID 不以 AKID 开头, 请确认是否填反了 ID/KEY"
green "  ENV_ID = $ENV_ID"

# ---------- 2) tcb CLI ----------
hr; blue "[2/6] 检查 / 安装 tcb..."
command -v tcb >/dev/null || npm i -g '@cloudbase/cli@latest'
green "  tcb $(tcb -v 2>/dev/null || echo n/a)"

# ---------- 3) 登录 ----------
hr; blue "[3/6] 登录腾讯云..."
tcb logout >/dev/null 2>&1 || true
tcb login --apiKeyId "$TENCENT_SECRET_ID" --apiKey "$TENCENT_SECRET_KEY" >/dev/null
green "  登录成功"

# ---------- 4) 生成密钥 ----------
hr; blue "[4/6] 生成 JWT_SECRET + INTERNAL_API_SECRET..."
JWT_SECRET="${JWT_SECRET:-$(openssl rand -base64 48 | tr -d '\n')}"
INTERNAL_API_SECRET="${INTERNAL_API_SECRET:-$(openssl rand -base64 48 | tr -d '\n')}"
SITE_URL="${SITE_URL:-https://placeholder}"
MOCK_MODE="${MOCK_MODE:-0}"
VOLC_ARK_API_KEY="${VOLC_ARK_API_KEY:-}"
ANTHROPIC_API_KEY="${ANTHROPIC_API_KEY:-}"
DEEPSEEK_API_KEY="${DEEPSEEK_API_KEY:-}"
DOUBAO_API_KEY="${DOUBAO_API_KEY:-}"
export JWT_SECRET INTERNAL_API_SECRET SITE_URL MOCK_MODE \
       VOLC_ARK_API_KEY ANTHROPIC_API_KEY DEEPSEEK_API_KEY DOUBAO_API_KEY
green "  Secrets 已生成"

# ---------- 5) deploy ----------
hr; blue "[5/6] 推送 Dockerfile.allinone..."
yellow "  首次构建约 5-10 分钟 (Next.js + Python + Caddy + ffmpeg 多阶段镜像)"
cd "$ROOT_DIR"
tcb framework deploy -e "$ENV_ID" --config-file deploy/cn-serverless/cloudbaserc.allinone.json

# ---------- 6) URL ----------
hr; blue "[6/6] 获取访问 URL..."
sleep 5
URL=$(tcb run service:list -e "$ENV_ID" --json 2>/dev/null | \
      node -e "let s=''; process.stdin.on('data',c=>s+=c).on('end',()=>{try{const j=JSON.parse(s);const x=(j.find(x=>x.name==='xyq')||{});console.log(x.url||'');}catch(e){}});" || true)

if [ -n "$URL" ]; then
  green "  访问地址: $URL"
  echo "  /api/health 检查..."
  sleep 10
  curl -fsS "$URL/api/health" || yellow "  容器还在启动, 30s 后再试 curl $URL/api/health"
  echo
else
  yellow "  自动获取 URL 失败. 请到 CloudBase 控制台查看:"
  yellow "  https://console.cloud.tencent.com/tcb/service/index?envId=$ENV_ID"
fi

hr
green "========================================"
green "  部署完成"
green "========================================"
green "  - 服务: 单容器 (FastAPI + Next.js + Caddy + SQLite)"
green "  - 数据: /data SQLite (容器临时盘; 要持久化看下方)"
green "  - 闲时: 缩到 0 instance, ¥0/小时"
green ""
green "  下一步 (按需):"
green "  1) 持久化数据: 控制台 → 云托管 → xyq → 持久化存储 → 挂载 CFS 到 /data"
green "  2) 自定义域名: 控制台 → 云托管 → xyq → 自定义域名 (需要备案)"
green "  3) 真实 AI Key: 控制台 → 云托管 → xyq → 环境变量"
hr
