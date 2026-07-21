"""Agent 长期记忆 SQLite 的版本化数据库迁移。

v1.0.0-beta.1 是项目首个发布版本，因此本模块只保留能够从空库创建当前完整结构的
初始基线。后续结构变化应继续在 ``MIGRATIONS`` 中追加新版本。
"""

from __future__ import annotations

import sqlite3
from collections.abc import Callable


Migration = Callable[[sqlite3.Connection], None]


def _migration_0001_initial_schema(conn: sqlite3.Connection) -> None:
    """创建 v1.0.0-beta.1 所需的完整长期记忆结构。

    Args:
        conn: 已开启迁移事务的 SQLite 连接。

    Returns:
        None: 全部表和索引创建完成后直接返回。

    Raises:
        sqlite3.Error: 创建表或索引失败时抛出。
    """

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS memories (
            id TEXT PRIMARY KEY,
            owner_id INTEGER NOT NULL,
            content TEXT NOT NULL,
            timestamp REAL NOT NULL,
            memory_coefficient REAL NOT NULL,
            semantic_timestamp REAL NOT NULL DEFAULT 0,
            memory_type TEXT NOT NULL DEFAULT 'normal',
            last_decay_timestamp REAL NOT NULL DEFAULT 0,
            last_boost_timestamp REAL NOT NULL DEFAULT 0
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_owner_id ON memories(owner_id)")
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_memory_coefficient ON memories(memory_coefficient)"
    )
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
)


def run_memory_migrations(conn: sqlite3.Connection) -> None:
    """把长期记忆 SQLite 升级到当前版本。

    Args:
        conn: 配置了 ``sqlite3.Row`` 行工厂的 SQLite 连接。

    Returns:
        None: 所有待执行迁移提交后直接返回。

    Raises:
        sqlite3.Error: 读取迁移记录、应用迁移或提交事务失败时抛出。
    """

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
