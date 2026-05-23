#!/usr/bin/env bash
# 升级到最新 main：拉代码 + 重建 backend/web + 滚动重启
set -euo pipefail
cd "$(dirname "$0")/.."
git pull --rebase --autostash
cd deploy/cn
docker compose --env-file .env build backend web
docker compose --env-file .env up -d backend web
docker compose --env-file .env logs --tail=50 backend
echo "升级完成"
