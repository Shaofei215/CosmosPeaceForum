# SQLite 持久化存储层
# 提供记忆分块的 CRUD 操作，作为记忆系统的主数据源

import asyncio
import sqlite3
import threading
from typing import Optional, List
from pathlib import Path

from agents.agents_scheduler.memory.config import MemoryConfig
from agents.agents_scheduler.memory.migrations import run_memory_migrations
from agents.agents_scheduler.memory.models import MemoryChunk


class MemoryDB:
    """
    SQLite 记忆数据库封装类

    提供异步记忆分块存储操作，作为记忆系统的主数据源。
    所有操作都通过 owner_id 实现所有权隔离。

    表结构：
    - id: TEXT PRIMARY KEY
    - owner_id: INTEGER NOT NULL
    - content: TEXT NOT NULL
    - timestamp: REAL NOT NULL
    - memory_coefficient: REAL NOT NULL

    索引：
    - idx_owner_id: 加速按 owner_id 查询
    - idx_memory_coefficient: 加速按记忆系数排序
    """

    def __init__(self, config: MemoryConfig):
        """
        初始化数据库连接

        Args:
            config: 记忆系统配置
        """
        self.db_path = config.get_memory_db_path()
        self._conn: Optional[sqlite3.Connection] = None
        self._lock = threading.RLock()
        self._init_db()

    def _init_db(self):
        """
        初始化数据库表和索引

        创建 memories 表及必要的索引。
        """
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row

        run_memory_migrations(self._conn)

    async def add_memory(self, chunk: MemoryChunk) -> None:
        """
        添加记忆分块

        Args:
            chunk: 要添加的记忆分块
        """
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,
            self._add_memory_sync,
            chunk
        )

    def _add_memory_sync(self, chunk: MemoryChunk):
        """同步版本的添加记忆"""
        with self._lock:
            cursor = self._conn.cursor()
            cursor.execute(
                """
                INSERT INTO memories (
                    id, owner_id, content, timestamp, semantic_timestamp,
                    memory_coefficient, memory_type, last_decay_timestamp,
                    last_boost_timestamp
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    chunk.id,
                    chunk.owner_id,
                    chunk.content,
                    chunk.timestamp,
                    chunk.semantic_timestamp,
                    chunk.memory_coefficient,
                    chunk.memory_type,
                    chunk.last_decay_timestamp,
                    chunk.last_boost_timestamp,
                )
            )
            self._conn.commit()

    async def get_memory(self, memory_id: str) -> Optional[MemoryChunk]:
        """
        根据 ID 获取记忆分块

        Args:
            memory_id: 记忆分块 ID

        Returns:
            Optional[MemoryChunk]: 记忆分块，如果不存在则返回 None
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            self._get_memory_sync,
            memory_id
        )

    def _get_memory_sync(self, memory_id: str) -> Optional[MemoryChunk]:
        """同步版本的获取记忆"""
        with self._lock:
            cursor = self._conn.cursor()
            cursor.execute("SELECT * FROM memories WHERE id = ?", (memory_id,))
            row = cursor.fetchone()
            if row is None:
                return None
            return MemoryChunk.from_dict(dict(row))

    async def update_memory(self, chunk: MemoryChunk) -> None:
        """
        更新记忆分块

        Args:
            chunk: 要更新的记忆分块（根据 ID 更新）
        """
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,
            self._update_memory_sync,
            chunk
        )

    def _update_memory_sync(self, chunk: MemoryChunk):
        """同步版本的更新记忆"""
        with self._lock:
            cursor = self._conn.cursor()
            cursor.execute(
                """
                UPDATE memories
                SET content = ?, timestamp = ?, semantic_timestamp = ?, memory_coefficient = ?,
                    memory_type = ?, last_decay_timestamp = ?, last_boost_timestamp = ?
                WHERE id = ?
                """,
                (
                    chunk.content,
                    chunk.timestamp,
                    chunk.semantic_timestamp,
                    chunk.memory_coefficient,
                    chunk.memory_type,
                    chunk.last_decay_timestamp,
                    chunk.last_boost_timestamp,
                    chunk.id,
                )
            )
            self._conn.commit()

    async def delete_memory(self, memory_id: str) -> None:
        """
        删除记忆分块

        Args:
            memory_id: 要删除的记忆分块 ID
        """
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,
            self._delete_memory_sync,
            memory_id
        )

    def _delete_memory_sync(self, memory_id: str):
        """同步版本的删除记忆"""
        with self._lock:
            cursor = self._conn.cursor()
            cursor.execute("DELETE FROM memories WHERE id = ?", (memory_id,))
            self._conn.commit()

    async def get_all_memories(self) -> List[MemoryChunk]:
        """
        获取所有记忆分块

        Returns:
            List[MemoryChunk]: 所有记忆分块列表
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            self._get_all_memories_sync
        )

    def _get_all_memories_sync(self) -> List[MemoryChunk]:
        """同步版本的获取所有记忆"""
        with self._lock:
            cursor = self._conn.cursor()
            cursor.execute("SELECT * FROM memories ORDER BY timestamp DESC")
            return [MemoryChunk.from_dict(dict(row)) for row in cursor.fetchall()]

    async def try_boost_memory(
        self,
        memory_id: str,
        owner_id: int,
        boost_factor: float,
        current_time: float,
        cooldown_seconds: int,
    ) -> Optional[MemoryChunk]:
        """
        在冷却条件满足时原子增强一条普通记忆。

        Args:
            memory_id: 待增强的记忆 ID。
            owner_id: 记忆所有者 ID，用于再次落实所有权边界。
            boost_factor: 本次增加的记忆系数。
            current_time: 当前缩放时间戳。
            cooldown_seconds: 两次增强之间要求的最小缩放秒数。

        Returns:
            Optional[MemoryChunk]: 成功增强后的记忆；冷却中或记录不存在时返回 ``None``。
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            self._try_boost_memory_sync,
            memory_id,
            owner_id,
            boost_factor,
            current_time,
            cooldown_seconds,
        )

    def _try_boost_memory_sync(
        self,
        memory_id: str,
        owner_id: int,
        boost_factor: float,
        current_time: float,
        cooldown_seconds: int,
    ) -> Optional[MemoryChunk]:
        """同步执行带冷却条件的原子唤醒增强。"""
        cooldown_cutoff = current_time - cooldown_seconds
        # 0 是历史记录“从未增强”的哨兵值，时间轴恰好位于 0 时写入极小正数以免重复放行。
        stored_boost_time = max(current_time, 1e-9)
        with self._lock:
            cursor = self._conn.cursor()
            cursor.execute(
                """
                UPDATE memories
                SET memory_coefficient = MIN(1.0, memory_coefficient + ?),
                    last_boost_timestamp = ?
                WHERE id = ?
                  AND owner_id = ?
                  AND memory_type = 'normal'
                  AND (
                      last_boost_timestamp = 0
                      OR last_boost_timestamp <= ?
                  )
                RETURNING *
                """,
                (
                    boost_factor,
                    stored_boost_time,
                    memory_id,
                    owner_id,
                    cooldown_cutoff,
                ),
            )
            row = cursor.fetchone()
            self._conn.commit()
            return MemoryChunk.from_dict(dict(row)) if row is not None else None

    def get_latest_clock_timestamp(self) -> float:
        """
        获取持久化记忆中最大的缩放时间戳。

        Returns:
            float: 创建、衰减或唤醒时间中的最大值；无记忆时返回 ``0.0``。
        """
        with self._lock:
            cursor = self._conn.cursor()
            cursor.execute(
                """
                SELECT MAX(
                    timestamp,
                    last_decay_timestamp,
                    last_boost_timestamp
                ) AS latest_timestamp
                FROM memories
                ORDER BY latest_timestamp DESC
                LIMIT 1
                """
            )
            row = cursor.fetchone()
            return float(row["latest_timestamp"] or 0.0) if row else 0.0

    def get_index_metadata(self, key: str) -> Optional[str]:
        """
        读取派生索引元数据。

        Args:
            key: 元数据键。

        Returns:
            Optional[str]: 已保存的值；不存在时返回 ``None``。
        """
        with self._lock:
            cursor = self._conn.cursor()
            cursor.execute("SELECT value FROM memory_index_metadata WHERE key = ?", (key,))
            row = cursor.fetchone()
            return str(row["value"]) if row else None

    def set_index_metadata(self, key: str, value: str) -> None:
        """
        写入或覆盖派生索引元数据。

        Args:
            key: 元数据键。
            value: 元数据值。

        Returns:
            None: 提交完成后直接返回。
        """
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO memory_index_metadata (key, value)
                VALUES (?, ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value
                """,
                (key, value),
            )
            self._conn.commit()

    async def get_user_memories(self, owner_id: int) -> List[MemoryChunk]:
        """
        获取指定用户的所有记忆分块

        Args:
            owner_id: 用户 ID

        Returns:
            List[MemoryChunk]: 该用户的所有记忆分块列表
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            self._get_user_memories_sync,
            owner_id
        )

    def _get_user_memories_sync(self, owner_id: int) -> List[MemoryChunk]:
        """同步版本的获取用户记忆"""
        with self._lock:
            cursor = self._conn.cursor()
            cursor.execute(
                "SELECT * FROM memories WHERE owner_id = ? ORDER BY timestamp DESC",
                (owner_id,)
            )
            return [MemoryChunk.from_dict(dict(row)) for row in cursor.fetchall()]

    async def clear_user_memories(self, owner_id: int) -> int:
        """
        清除指定用户的所有记忆分块

        Args:
            owner_id: 用户 ID

        Returns:
            int: 删除的记忆数量
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            self._clear_user_memories_sync,
            owner_id
        )

    def _clear_user_memories_sync(self, owner_id: int) -> int:
        """同步版本的清除用户记忆"""
        with self._lock:
            cursor = self._conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM memories WHERE owner_id = ?", (owner_id,))
            count = cursor.fetchone()[0]
            cursor.execute("DELETE FROM memories WHERE owner_id = ?", (owner_id,))
            self._conn.commit()
            return count

    async def get_memories_above_threshold(
        self,
        owner_id: int,
        threshold: float
    ) -> List[MemoryChunk]:
        """
        获取指定用户且记忆系数高于阈值的记忆分块

        Args:
            owner_id: 用户 ID
            threshold: 记忆系数阈值

        Returns:
            List[MemoryChunk]: 符合条件的记忆分块列表
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            self._get_memories_above_threshold_sync,
            owner_id,
            threshold
        )

    def _get_memories_above_threshold_sync(
        self,
        owner_id: int,
        threshold: float
    ) -> List[MemoryChunk]:
        """同步版本的获取高于阈值的记忆"""
        with self._lock:
            cursor = self._conn.cursor()
            cursor.execute(
                """
                SELECT * FROM memories
                WHERE owner_id = ? AND memory_coefficient >= ?
                ORDER BY memory_coefficient DESC
                """,
                (owner_id, threshold)
            )
            return [MemoryChunk.from_dict(dict(row)) for row in cursor.fetchall()]

    def close(self):
        """关闭数据库连接"""
        with self._lock:
            if self._conn:
                self._conn.close()
                self._conn = None

    def __del__(self):
        """析构函数，确保关闭数据库连接"""
        self.close()
