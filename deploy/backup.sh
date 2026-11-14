#!/usr/bin/env bash
# Backup the zixxx workbench.
#
# The database is dumped with pg_dump straight to disk, and the uploaded files
# are copied as an archive. Nothing is loaded into memory (section 12.7).
#
# Usage: deploy/backup.sh [target directory]
set -euo pipefail

cd "$(dirname "$0")/.."

TARGET_DIR="${1:-./backups}"
STAMP="$(date +%Y%m%d-%H%M%S)"
KEEP_DAYS="${BACKUP_KEEP_DAYS:-14}"

mkdir -p "$TARGET_DIR"

DB_NAME="${POSTGRES_DB:-zixxx}"
DB_USER="${POSTGRES_USER:-zixxx}"

echo "[backup] 目标目录：$TARGET_DIR"

# --------------------------------------------------------------------------- #
# 1. 数据库
# --------------------------------------------------------------------------- #
if command -v docker >/dev/null 2>&1 && docker compose ps --status running db >/dev/null 2>&1; then
    DB_DUMP_CMD=(docker compose exec -T db pg_dump -U "$DB_USER" -d "$DB_NAME" --format=custom --no-owner)
elif command -v pg_dump >/dev/null 2>&1; then
    DB_DUMP_CMD=(pg_dump -U "$DB_USER" -d "$DB_NAME" --format=custom --no-owner)
else
    echo "[backup] 找不到 pg_dump 或运行中的数据库容器，备份中止。" >&2
    exit 1
fi

DB_FILE="$TARGET_DIR/db-$STAMP.dump"
echo "[backup] 导出数据库 → $DB_FILE"
"${DB_DUMP_CMD[@]}" > "$DB_FILE"
gzip -f "$DB_FILE"

# --------------------------------------------------------------------------- #
# 2. 上传的文件
# --------------------------------------------------------------------------- #
MEDIA_DIR="${MEDIA_DIR:-./backend/media}"
if [ -d "$MEDIA_DIR" ]; then
    MEDIA_FILE="$TARGET_DIR/media-$STAMP.tar.gz"
    echo "[backup] 打包资料目录 → $MEDIA_FILE"
    tar -czf "$MEDIA_FILE" -C "$(dirname "$MEDIA_DIR")" "$(basename "$MEDIA_DIR")"
else
    echo "[backup] 找不到资料目录 $MEDIA_DIR，跳过文件备份。"
fi

# --------------------------------------------------------------------------- #
# 3. 校验与清理
# --------------------------------------------------------------------------- #
if [ -f "$DB_FILE.gz" ]; then
    gzip -t "$DB_FILE.gz"
    echo "[backup] 数据库备份校验通过。"
fi

find "$TARGET_DIR" -name 'db-*.dump.gz' -mtime "+$KEEP_DAYS" -delete
find "$TARGET_DIR" -name 'media-*.tar.gz' -mtime "+$KEEP_DAYS" -delete

echo "[backup] 完成："
ls -lh "$TARGET_DIR" | tail -n +2
