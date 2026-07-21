#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

# 备份 agents 侧运行期数据库与索引。
#
# 默认覆盖：
# - agents/management/data/management.db
# - agents/management/data/generated_secrets.json（若存在，属于管理端认证状态）
# - agents/management/data/.jwt_secret（若存在，兼容旧版本）
# - agents/agents_scheduler/memory/data/memories.db
# - agents/agents_scheduler/memory/data/chroma_db
# - agents/agents_scheduler/memory/data/tantivy_index
#
# 注意：SQLite 使用 sqlite3 的在线备份接口（若可用）；目录型索引使用文件快照。
# 为确保 SQLite、ChromaDB 和 Tantivy 三套存储处于同一业务时间点，应在维护窗口暂停
# Agent/Scheduler 写入。自动化任务应使用能够在失败时仍恢复服务的外层脚本或 service。

BACKUP_DIR="${BACKUP_DIR:-./backups/agents}"
RETENTION_DAYS="${RETENTION_DAYS:-14}"
TIMESTAMP="$(date +%Y%m%d-%H%M%S)"

if [[ ! "$RETENTION_DAYS" =~ ^[0-9]+$ ]]; then
  echo "RETENTION_DAYS must be a non-negative integer: $RETENTION_DAYS" >&2
  exit 2
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd -P)"

MANAGEMENT_DATA_DIR="${MANAGEMENT_DATA_DIR:-$REPO_ROOT/agents/management/data}"
MANAGEMENT_DB_PATH="${MANAGEMENT_DB_PATH:-$MANAGEMENT_DATA_DIR/management.db}"

MEMORY_DATA_DIR="${MEMORY_DATA_DIR:-$REPO_ROOT/agents/agents_scheduler/memory/data}"
MEMORY_DB_PATH="${MEMORY_DB_PATH:-$MEMORY_DATA_DIR/memories.db}"
CHROMA_DB_DIR="${CHROMA_DB_DIR:-$MEMORY_DATA_DIR/chroma_db}"
TANTIVY_INDEX_DIR="${TANTIVY_INDEX_DIR:-$MEMORY_DATA_DIR/tantivy_index}"

mkdir -p "$BACKUP_DIR"
BACKUP_DIR="$(cd "$BACKUP_DIR" && pwd -P)"

ARCHIVE_NAME="agents-$TIMESTAMP.tar.gz"
ARCHIVE_PATH="$BACKUP_DIR/$ARCHIVE_NAME"
TEMP_ARCHIVE="$ARCHIVE_PATH.tmp"
WORK_DIR="$BACKUP_DIR/.agents-$TIMESTAMP.work"
MANIFEST="$WORK_DIR/manifest.txt"

cleanup() {
  rm -rf "$WORK_DIR" "$TEMP_ARCHIVE"
}
trap cleanup EXIT

log() {
  printf '[%s] %s\n' "$(date +%H:%M:%S)" "$*"
}

record_manifest() {
  printf '%s\n' "$*" >> "$MANIFEST"
}

copy_sqlite_sidecars() {
  local source_path="$1"
  local destination_path="$2"
  local sidecar

  cp -a "$source_path" "$destination_path"
  for sidecar in -wal -shm -journal; do
    if [[ -e "$source_path$sidecar" ]]; then
      cp -a "$source_path$sidecar" "$destination_path$sidecar"
    fi
  done
}

backup_sqlite() {
  local source_path="$1"
  local destination_path="$2"
  local label="$3"
  local destination_dir
  local destination_name

  if [[ ! -f "$source_path" ]]; then
    log "Skip missing SQLite database: $source_path"
    record_manifest "SKIP $label: missing $source_path"
    return 0
  fi

  destination_dir="$(dirname "$destination_path")"
  destination_name="$(basename "$destination_path")"
  mkdir -p "$destination_dir"

  if command -v sqlite3 >/dev/null 2>&1; then
    log "Backing up SQLite database '$label' from '$source_path'..."
    (
      cd "$destination_dir"
      sqlite3 "$source_path" ".timeout 5000" ".backup main $destination_name"
    )
    record_manifest "SQLITE $label: $source_path -> $destination_path (sqlite3 .backup)"
  else
    log "sqlite3 is not available; copying '$label' with SQLite sidecar files..."
    copy_sqlite_sidecars "$source_path" "$destination_path"
    record_manifest "SQLITE $label: $source_path -> $destination_path (file copy fallback)"
  fi
}

copy_file_if_exists() {
  local source_path="$1"
  local destination_path="$2"
  local label="$3"

  if [[ ! -f "$source_path" ]]; then
    record_manifest "SKIP $label: missing $source_path"
    return 0
  fi

  mkdir -p "$(dirname "$destination_path")"
  cp -a "$source_path" "$destination_path"
  record_manifest "FILE $label: $source_path -> $destination_path"
}

copy_dir_if_exists() {
  local source_path="$1"
  local destination_path="$2"
  local label="$3"

  if [[ ! -d "$source_path" ]]; then
    log "Skip missing directory: $source_path"
    record_manifest "SKIP $label: missing $source_path"
    return 0
  fi

  mkdir -p "$(dirname "$destination_path")"
  log "Copying directory '$label' from '$source_path'..."
  cp -a "$source_path" "$destination_path"
  record_manifest "DIR $label: $source_path -> $destination_path"
}

mkdir -p "$WORK_DIR"

cat > "$MANIFEST" <<EOF
CosmosPeaceForum agents backup
timestamp=$TIMESTAMP
repo_root=$REPO_ROOT
backup_archive=$ARCHIVE_PATH
EOF

backup_sqlite "$MANAGEMENT_DB_PATH" "$WORK_DIR/management/management.db" "management database"
copy_file_if_exists \
  "$MANAGEMENT_DATA_DIR/generated_secrets.json" \
  "$WORK_DIR/management/generated_secrets.json" \
  "management generated secrets"
copy_file_if_exists \
  "$MANAGEMENT_DATA_DIR/.jwt_secret" \
  "$WORK_DIR/management/.jwt_secret" \
  "legacy management jwt secret"

backup_sqlite "$MEMORY_DB_PATH" "$WORK_DIR/memory/memories.db" "memory sqlite database"
copy_dir_if_exists "$CHROMA_DB_DIR" "$WORK_DIR/memory/chroma_db" "memory chromadb"
if [[ -f "$CHROMA_DB_DIR/chroma.sqlite3" ]]; then
  backup_sqlite "$CHROMA_DB_DIR/chroma.sqlite3" "$WORK_DIR/memory/chroma_db/chroma.sqlite3" "chromadb sqlite database"
fi
copy_dir_if_exists "$TANTIVY_INDEX_DIR" "$WORK_DIR/memory/tantivy_index" "memory tantivy index"

record_manifest "created_at=$(date -Iseconds)"

log "Creating archive '$ARCHIVE_PATH'..."
(
  cd "$WORK_DIR"
  tar -czf "$TEMP_ARCHIVE" .
)
mv "$TEMP_ARCHIVE" "$ARCHIVE_PATH"

find "$BACKUP_DIR" -type f -name 'agents-*.tar.gz' -mtime +"$RETENTION_DAYS" -delete

log "Agents backup completed: $ARCHIVE_PATH"
