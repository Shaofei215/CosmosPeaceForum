#!/usr/bin/env bash
set -Eeuo pipefail

# Cron example:
# 15 3 * * * cd /path/to/imaginary-tree && BACKUP_DIR=/data/backups ./ops/backup/backup_postgres.sh

BACKUP_DIR="${BACKUP_DIR:-./backups/postgres}"
RETENTION_DAYS="${RETENTION_DAYS:-14}"
POSTGRES_SERVICE="${POSTGRES_SERVICE:-postgres}"
POSTGRES_USER="${POSTGRES_USER:-imaginary_tree}"
POSTGRES_DATABASES="${POSTGRES_DATABASES:-imaginary_tree}"
COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.yml}"
TIMESTAMP="$(date +%Y%m%d-%H%M%S)"

if [[ -n "${COMPOSE_BIN:-}" ]]; then
  read -r -a COMPOSE_CMD <<< "$COMPOSE_BIN"
elif docker compose version >/dev/null 2>&1; then
  COMPOSE_CMD=(docker compose)
elif command -v docker-compose >/dev/null 2>&1; then
  COMPOSE_CMD=(docker-compose)
else
  echo "Neither 'docker compose' nor 'docker-compose' is available." >&2
  exit 127
fi

mkdir -p "$BACKUP_DIR"

DATABASE_LIST="${POSTGRES_DATABASES//,/ }"
for database in $DATABASE_LIST; do
  if [[ ! "$database" =~ ^[A-Za-z0-9_.-]+$ ]]; then
    echo "Invalid database name: $database" >&2
    exit 2
  fi

  output_file="$BACKUP_DIR/$database-$TIMESTAMP.sql.gz"
  temp_file="$output_file.tmp"

  echo "Backing up PostgreSQL database '$database' to '$output_file'..."
  "${COMPOSE_CMD[@]}" -f "$COMPOSE_FILE" exec -T "$POSTGRES_SERVICE" \
    pg_dump -U "$POSTGRES_USER" "$database" \
    | gzip -9 > "$temp_file"

  mv "$temp_file" "$output_file"
done

find "$BACKUP_DIR" -type f -name "*.sql.gz" -mtime +"$RETENTION_DAYS" -delete

echo "PostgreSQL backup completed."
