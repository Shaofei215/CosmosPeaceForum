"""Versioned SQLite migrations for the scheduler memory store."""

from __future__ import annotations

import sqlite3
from collections.abc import Callable


Migration = Callable[[sqlite3.Connection], None]


def _column_names(conn: sqlite3.Connection, table_name: str) -> set[str]:
    return {row["name"] for row in conn.execute(f"PRAGMA table_info({table_name})").fetchall()}


def _migration_0001_initial_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS memories (
            id TEXT PRIMARY KEY,
            owner_id INTEGER NOT NULL,
            content TEXT NOT NULL,
            timestamp REAL NOT NULL,
            memory_coefficient REAL NOT NULL
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_owner_id ON memories(owner_id)")
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_memory_coefficient ON memories(memory_coefficient)"
    )


def _migration_0002_semantic_timestamp(conn: sqlite3.Connection) -> None:
    if "semantic_timestamp" not in _column_names(conn, "memories"):
        conn.execute(
            "ALTER TABLE memories ADD COLUMN semantic_timestamp REAL NOT NULL DEFAULT 0"
        )


def _migration_0003_memory_type(conn: sqlite3.Connection) -> None:
    if "memory_type" not in _column_names(conn, "memories"):
        conn.execute(
            "ALTER TABLE memories ADD COLUMN memory_type TEXT NOT NULL DEFAULT 'normal'"
        )


def _migration_0004_last_decay_timestamp(conn: sqlite3.Connection) -> None:
    """
    增加增量衰减游标，并初始化历史记忆的衰减起点。

    Args:
        conn: 已开启迁移事务的 SQLite 连接。

    Returns:
        None: 迁移完成后直接返回。

    Raises:
        sqlite3.Error: 修改表结构或初始化历史数据失败时抛出。
    """
    if "last_decay_timestamp" not in _column_names(conn, "memories"):
        conn.execute(
            "ALTER TABLE memories ADD COLUMN last_decay_timestamp REAL NOT NULL DEFAULT 0"
        )
        conn.execute(
            "UPDATE memories SET last_decay_timestamp = timestamp "
            "WHERE last_decay_timestamp = 0"
        )


def _migration_0005_last_boost_timestamp(conn: sqlite3.Connection) -> None:
    """
    增加唤醒增强冷却游标。

    Args:
        conn: 已开启迁移事务的 SQLite 连接。

    Returns:
        None: 字段存在或创建完成后直接返回。

    Raises:
        sqlite3.Error: 修改表结构失败时抛出。
    """
    if "last_boost_timestamp" not in _column_names(conn, "memories"):
        conn.execute(
            "ALTER TABLE memories ADD COLUMN last_boost_timestamp REAL NOT NULL DEFAULT 0"
        )


def _migration_0006_index_metadata(conn: sqlite3.Connection) -> None:
    """
    创建派生索引元数据存储表。

    当前不校验 Embedding 模型指纹；该通用表为未来的向量索引
    版本记录与自动重建流程预留。

    Args:
        conn: 已开启迁移事务的 SQLite 连接。

    Returns:
        None: 表创建完成后直接返回。

    Raises:
        sqlite3.Error: 创建表失败时抛出。
    """
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS memory_index_metadata (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
        """
    )


MIGRATIONS: tuple[tuple[int, Migration], ...] = (
    (1, _migration_0001_initial_schema),
    (2, _migration_0002_semantic_timestamp),
    (3, _migration_0003_memory_type),
    (4, _migration_0004_last_decay_timestamp),
    (5, _migration_0005_last_boost_timestamp),
    (6, _migration_0006_index_metadata),
)


def run_memory_migrations(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS memory_schema_migrations (
            version INTEGER PRIMARY KEY,
            applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    applied_versions = {
        row["version"] for row in conn.execute("SELECT version FROM memory_schema_migrations")
    }

    for version, migration in MIGRATIONS:
        if version in applied_versions:
            continue
        migration(conn)
        conn.execute("INSERT INTO memory_schema_migrations (version) VALUES (?)", (version,))

    conn.commit()
