#!/bin/bash
# =============================================================================
# veFaaS 单容器启动: Caddy(8000) + FastAPI(8001) + Next.js(3000)
#
# 任何一个进程退出 -> 主进程 (uvicorn) 退出 -> 容器退出 -> veFaaS 自动重启
#
# 持久化:
#   - SQLite        /mnt/nas/xyq/xyq.db
#   - 本地 storage  /mnt/nas/xyq/storage  (TOS 主存储, 此处仅做兜底)
#   - 若 NAS 未挂载  自动回落到容器临时盘 /data (重启丢)
# =============================================================================
set -e

# ---- 1) 确定持久化目录 ----
if [ -d /mnt/nas/xyq ] && [ -w /mnt/nas/xyq ]; then
    DATA_DIR=/mnt/nas/xyq
    echo "[run.sh] NAS persistent storage at $DATA_DIR"
else
    DATA_DIR=/data
    mkdir -p "$DATA_DIR"
    echo "[run.sh] WARNING: NAS not mounted, using ephemeral $DATA_DIR (will reset on restart)"
fi
mkdir -p "$DATA_DIR/storage"
chmod 0755 "$DATA_DIR"

# 让所有进程都读取一致的路径
export STORAGE_ROOT="${STORAGE_ROOT:-$DATA_DIR/storage}"
export DATABASE_URL="${DATABASE_URL:-sqlite:///$DATA_DIR/xyq.db}"

echo "[run.sh] DATABASE_URL    = $DATABASE_URL"
echo "[run.sh] STORAGE_BACKEND = ${STORAGE_BACKEND:-local}"
echo "[run.sh] STORAGE_ROOT    = $STORAGE_ROOT"
echo "[run.sh] EMBEDDED_WORKER = ${EMBEDDED_WORKER:-1}"
echo "[run.sh] TOS_BUCKET      = ${TOS_BUCKET:-(unset)}"
echo "[run.sh] CN_DOMESTIC_MODE= ${CN_DOMESTIC_MODE:-0}"
echo "[run.sh] MANJU_AGENT_MODE= ${MANJU_AGENT_MODE:-0}"

# ---- 2) Caddy 反向代理 (前台输出到 stdout) ----
caddy run --config /etc/caddy/Caddyfile --adapter caddyfile &
CADDY_PID=$!
echo "[run.sh] caddy pid=$CADDY_PID"

# ---- 3) Next.js standalone ----
cd /webapp
node server.js &
WEB_PID=$!
echo "[run.sh] next.js pid=$WEB_PID"
cd /app

# ---- 4) FastAPI (主进程; 退出则容器停止) ----
exec uvicorn app.main:app \
    --host 0.0.0.0 --port 8001 \
    --workers 1 \
    --proxy-headers --forwarded-allow-ips='*' \
    --access-log
