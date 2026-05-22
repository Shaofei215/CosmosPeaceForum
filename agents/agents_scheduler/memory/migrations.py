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


MIGRATIONS: tuple[tuple[int, Migration], ...] = (
    (1, _migration_0001_initial_schema),
    (2, _migration_0002_semantic_timestamp),
    (3, _migration_0003_memory_type),
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
