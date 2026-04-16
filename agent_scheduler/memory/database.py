# SQLite 持久化存储层
# 提供记忆分块的 CRUD 操作，作为记忆系统的主数据源

import sqlite3
import asyncio
from typing import Optional, List
from pathlib import Path

from agent_scheduler.memory.config import MemoryConfig
from agent_scheduler.memory.models import MemoryChunk


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
        self._init_db()

    def _init_db(self):
        """
        初始化数据库表和索引

        创建 memories 表及必要的索引。
        """
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row

        cursor = self._conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS memories (
                id TEXT PRIMARY KEY,
                owner_id INTEGER NOT NULL,
                content TEXT NOT NULL,
                timestamp REAL NOT NULL,
                memory_coefficient REAL NOT NULL
            )
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_owner_id 
            ON memories(owner_id)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_memory_coefficient 
            ON memories(memory_coefficient)
        """)

        self._conn.commit()

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
        cursor = self._conn.cursor()
        cursor.execute(
            """
            INSERT INTO memories (id, owner_id, content, timestamp, memory_coefficient)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                chunk.id,
                chunk.owner_id,
                chunk.content,
                chunk.timestamp,
                chunk.memory_coefficient,
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
        cursor = self._conn.cursor()
        cursor.execute(
            """
            UPDATE memories 
            SET content = ?, timestamp = ?, memory_coefficient = ?
            WHERE id = ?
            """,
            (
                chunk.content,
                chunk.timestamp,
                chunk.memory_coefficient,
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
        cursor = self._conn.cursor()
        cursor.execute("SELECT * FROM memories ORDER BY timestamp DESC")
        return [MemoryChunk.from_dict(dict(row)) for row in cursor.fetchall()]

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
        if self._conn:
            self._conn.close()
            self._conn = None

    def __del__(self):
        """析构函数，确保关闭数据库连接"""
        self.close()
