#!/usr/bin/env bash
# 备份 Postgres 数据 + storage 卷到 ./backups/<timestamp>.tar.gz
set -euo pipefail
cd "$(dirname "$0")"

STAMP=$(date +%Y%m%d-%H%M%S)
BACKUP_DIR=./backups
mkdir -p "$BACKUP_DIR"

echo "[1/2] 导出 Postgres..."
docker exec xyq-postgres pg_dump -U xyq -d xyq -F c -f /tmp/xyq.pgdump
docker cp xyq-postgres:/tmp/xyq.pgdump "$BACKUP_DIR/$STAMP.pgdump"

echo "[2/2] 打包 storage..."
docker run --rm -v xyq_storage-data:/srv -v "$PWD/$BACKUP_DIR":/backup alpine \
  tar -czf "/backup/$STAMP-storage.tgz" -C /srv .

echo "完成：$BACKUP_DIR/$STAMP.pgdump  +  $BACKUP_DIR/$STAMP-storage.tgz"
