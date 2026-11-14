#!/usr/bin/env bash
# Restore the zixxx workbench from a backup.
#
# The script refuses to overwrite anything unless --force is given, so a
# mistyped argument cannot destroy the live data. It restores the database
# and the uploaded files, then rebuilds the knowledge index.
#
# Usage: deploy/restore.sh <db-dump.gz> [media.tar.gz] [--force]
set -euo pipefail

cd "$(dirname "$0")/.."

DB_ARCHIVE=""
MEDIA_ARCHIVE=""
FORCE=""

for argument in "$@"; do
    case "$argument" in
        --force)
            FORCE="--force"
            ;;
        -*)
            echo "未知参数 $argument" >&2
            exit 2
            ;;
        *)
            if [ -z "$DB_ARCHIVE" ]; then
                DB_ARCHIVE="$argument"
            elif [ -z "$MEDIA_ARCHIVE" ]; then
                MEDIA_ARCHIVE="$argument"
            else
                echo "多余参数 $argument" >&2
                exit 2
            fi
            ;;
    esac
done

if [ -z "$DB_ARCHIVE" ]; then
    echo "用法：deploy/restore.sh <db-dump.gz> [media.tar.gz] [--force]" >&2
    exit 2
fi
if [ ! -f "$DB_ARCHIVE" ]; then
    echo "[restore] 找不到备份文件 $DB_ARCHIVE" >&2
    exit 2
fi
if [ "$FORCE" != "--force" ]; then
    echo "[restore] 这会覆盖当前数据库。请确认后追加 --force 重新执行。" >&2
    exit 1
fi

DB_NAME="${POSTGRES_DB:-zixxx}"
DB_USER="${POSTGRES_USER:-zixxx}"
MEDIA_DIR="${MEDIA_DIR:-./backend/media}"

# --------------------------------------------------------------------------- #
# 1. 数据库
# --------------------------------------------------------------------------- #
WORK_DIR="$(mktemp -d)"
trap 'rm -rf "$WORK_DIR"' EXIT
gzip -dc "$DB_ARCHIVE" > "$WORK_DIR/db.dump"

if command -v docker >/dev/null 2>&1 && docker compose ps --status running db >/dev/null 2>&1; then
    echo "[restore] 导入数据库。"
    docker compose exec -T db psql -U "$DB_USER" -d postgres -c \
        "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '$DB_NAME' AND pid <> pg_backend_pid();" >/dev/null
    docker compose exec -T db dropdb -U "$DB_USER" --if-exists "$DB_NAME"
    docker compose exec -T db createdb -U "$DB_USER" "$DB_NAME"
    docker compose exec -T db pg_restore -U "$DB_USER" -d "$DB_NAME" --no-owner < "$WORK_DIR/db.dump"
elif command -v pg_restore >/dev/null 2>&1; then
    echo "[restore] 导入数据库。"
    dropdb -U "$DB_USER" --if-exists "$DB_NAME"
    createdb -U "$DB_USER" "$DB_NAME"
    pg_restore -U "$DB_USER" -d "$DB_NAME" --no-owner < "$WORK_DIR/db.dump"
else
    echo "[restore] 找不到 pg_restore 或运行中的数据库容器。" >&2
    exit 1
fi

# --------------------------------------------------------------------------- #
# 2. 文件
# --------------------------------------------------------------------------- #
if [ -n "$MEDIA_ARCHIVE" ] && [ -f "$MEDIA_ARCHIVE" ]; then
    echo "[restore] 还原资料目录。"
    mkdir -p "$(dirname "$MEDIA_DIR")"
    tar -xzf "$MEDIA_ARCHIVE" -C "$(dirname "$MEDIA_DIR")"
else
    echo "[restore] 未提供资料备份，保留现有文件。"
fi

# --------------------------------------------------------------------------- #
# 3. 迁移与知识索引
# --------------------------------------------------------------------------- #
echo "[restore] 应用数据库迁移。"
if command -v docker >/dev/null 2>&1 && docker compose ps --status running web >/dev/null 2>&1; then
    docker compose exec -T web python manage.py migrate --noinput
    echo "[restore] 重建知识库索引。"
    docker compose exec -T web python manage.py rebuild_knowledge_index
else
    (cd backend && python manage.py migrate --noinput)
    echo "[restore] 重建知识库索引。"
    (cd backend && python manage.py rebuild_knowledge_index)
fi

echo "[restore] 完成。请重启服务：docker compose restart web worker"
