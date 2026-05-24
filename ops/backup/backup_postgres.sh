#!/usr/bin/env bash
set -Eeuo pipefail

# 备份 social_platform PostgreSQL 数据库。
#
# 支持三种模式：
# - POSTGRES_BACKUP_MODE=auto   默认。优先使用正在运行的 Docker Compose postgres 服务；
#                               找不到时退回宿主机 pg_dump。
# - POSTGRES_BACKUP_MODE=docker 强制通过 docker compose exec 执行容器内 pg_dump。
# - POSTGRES_BACKUP_MODE=local  强制使用宿主机 pg_dump，可连接本机或远程 PostgreSQL。
#
# Cron example:
# 15 3 * * * cd /path/to/cosmos-peace-forum && BACKUP_DIR=/data/backups ./ops/backup/backup_postgres.sh
#
# Local/system PostgreSQL example:
# POSTGRES_BACKUP_MODE=local PGHOST=127.0.0.1 PGPORT=5432 PGUSER=cosmos_peace_forum \
#   PGPASSWORD=cosmos_peace_forum ./ops/backup/backup_postgres.sh

BACKUP_DIR="${BACKUP_DIR:-./backups/postgres}"
RETENTION_DAYS="${RETENTION_DAYS:-14}"
POSTGRES_BACKUP_MODE="${POSTGRES_BACKUP_MODE:-auto}"
POSTGRES_SERVICE="${POSTGRES_SERVICE:-postgres}"
POSTGRES_USER="${POSTGRES_USER:-${PGUSER:-cosmos_peace_forum}}"
POSTGRES_DATABASES="${POSTGRES_DATABASES:-cosmos_peace_forum}"
POSTGRES_HOST="${POSTGRES_HOST:-${PGHOST:-localhost}}"
POSTGRES_PORT="${POSTGRES_PORT:-${PGPORT:-5432}}"
PGDUMP_BIN="${PGDUMP_BIN:-pg_dump}"
COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.yml}"
TIMESTAMP="$(date +%Y%m%d-%H%M%S)"

resolve_compose_command() {
  if [[ -n "${COMPOSE_BIN:-}" ]]; then
    read -r -a COMPOSE_CMD <<< "$COMPOSE_BIN"
    return 0
  fi

  if docker compose version >/dev/null 2>&1; then
    COMPOSE_CMD=(docker compose)
    return 0
  fi

  if command -v docker-compose >/dev/null 2>&1; then
    COMPOSE_CMD=(docker-compose)
    return 0
  fi

  return 1
}

docker_postgres_available() {
  local container_id

  [[ -f "$COMPOSE_FILE" ]] || return 1
  resolve_compose_command || return 1

  container_id="$("${COMPOSE_CMD[@]}" -f "$COMPOSE_FILE" ps -q "$POSTGRES_SERVICE" 2>/dev/null || true)"
  [[ -n "$container_id" ]]
}

select_backup_mode() {
  case "$POSTGRES_BACKUP_MODE" in
    auto)
      if docker_postgres_available; then
        BACKUP_MODE="docker"
      elif command -v "$PGDUMP_BIN" >/dev/null 2>&1; then
        BACKUP_MODE="local"
      else
        echo "Unable to find a running Docker Compose postgres service or local '$PGDUMP_BIN'." >&2
        exit 127
      fi
      ;;
    docker)
      if ! resolve_compose_command; then
        echo "Neither 'docker compose' nor 'docker-compose' is available." >&2
        exit 127
      fi
      BACKUP_MODE="docker"
      ;;
    local)
      if ! command -v "$PGDUMP_BIN" >/dev/null 2>&1; then
        echo "Local pg_dump command is not available: $PGDUMP_BIN" >&2
        exit 127
      fi
      BACKUP_MODE="local"
      ;;
    *)
      echo "Invalid POSTGRES_BACKUP_MODE: $POSTGRES_BACKUP_MODE" >&2
      echo "Expected one of: auto, docker, local" >&2
      exit 2
      ;;
  esac
}

dump_database() {
  local database="$1"

  if [[ "$BACKUP_MODE" == "docker" ]]; then
    "${COMPOSE_CMD[@]}" -f "$COMPOSE_FILE" exec -T "$POSTGRES_SERVICE" \
      pg_dump -U "$POSTGRES_USER" "$database"
  else
    "$PGDUMP_BIN" \
      -h "$POSTGRES_HOST" \
      -p "$POSTGRES_PORT" \
      -U "$POSTGRES_USER" \
      "$database"
  fi
}

mkdir -p "$BACKUP_DIR"
BACKUP_DIR="$(cd "$BACKUP_DIR" && pwd -P)"

BACKUP_MODE=""
select_backup_mode

DATABASE_LIST="${POSTGRES_DATABASES//,/ }"
for database in $DATABASE_LIST; do
  if [[ ! "$database" =~ ^[A-Za-z0-9_.-]+$ ]]; then
    echo "Invalid database name: $database" >&2
    exit 2
  fi

  output_file="$BACKUP_DIR/$database-$TIMESTAMP.sql.gz"
  temp_file="$output_file.tmp"

  echo "Backing up PostgreSQL database '$database' with mode '$BACKUP_MODE' to '$output_file'..."
  dump_database "$database" | gzip -9 > "$temp_file"

  mv "$temp_file" "$output_file"
done

find "$BACKUP_DIR" -type f -name "*.sql.gz" -mtime +"$RETENTION_DAYS" -delete

echo "PostgreSQL backup completed."
