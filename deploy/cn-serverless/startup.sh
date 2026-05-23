#!/bin/bash
# 单容器启动: caddy + uvicorn + next.js
# 任何一个进程退出 → 整个容器退出 → CloudBase 重启
set -e

mkdir -p /data /data/storage
chmod 0755 /data

echo "[startup] DATABASE_URL=$DATABASE_URL"
echo "[startup] STORAGE_DIR=$STORAGE_DIR"
echo "[startup] EMBEDDED_WORKER=$EMBEDDED_WORKER"

# 1. Caddy 反向代理 (前台输出到 stdout)
caddy run --config /etc/caddy/Caddyfile --adapter caddyfile &
CADDY_PID=$!

# 2. Next.js standalone (使用 web-builder 生成的 server.js)
cd /webapp
node server.js &
WEB_PID=$!

# 3. FastAPI (主进程, 退出则容器停止)
cd /app
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1 \
     --proxy-headers --forwarded-allow-ips='*'
