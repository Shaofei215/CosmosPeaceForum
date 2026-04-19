# 记忆服务核心层
# 统一管理三写同步、混合检索、衰减与唤醒机制

import logging
from typing import List, Tuple, Optional
from datetime import datetime

from agents.agents_scheduler.memory.config import MemoryConfig, get_memory_config
from agents.agents_scheduler.memory.models import MemoryChunk
from agents.agents_scheduler.memory.database import MemoryDB
from agents.agents_scheduler.memory.vector_store import VectorStore
from agents.agents_scheduler.memory.bm25_index import BM25Index
from agents.agents_scheduler.memory.embedding import EmbeddingModel, get_embedding_model
from agents.agents_scheduler.memory.utils import calculate_time_description
from agents.agents_scheduler.scheduler.time_system import get_time_system

logger = logging.getLogger(__name__)


class MemoryService:
    """
    记忆服务核心类

    统一管理记忆的写入、检索、衰减和删除。
    实现三写同步（SQLite + ChromaDB + Tantivy）和混合检索。

    使用示例：
    ```python
    service = get_memory_service()

    # 写入记忆
    memory_id = await service.write_memory(
        content="我在论坛上看到了关于镜流新角色的讨论",
        owner_id=42,
        memory_coefficient=0.85
    )

    # 召回记忆
    recalled = await service.recall_memories(
        owner_id=42,
        context="镜流角色讨论"
    )
    ```
    """

    _instance: Optional["MemoryService"] = None

    def __init__(self, config: Optional[MemoryConfig] = None):
        """
        初始化记忆服务

        Args:
            config: 记忆系统配置，默认使用全局配置
        """
        self.config = config or get_memory_config()
        self.db = MemoryDB(self.config)
        self.vector_store = VectorStore(self.config)
        self.bm25_index = BM25Index(self.config)
        self.embedding_model = get_embedding_model(self.config)

    async def write_memory(
        self,
        content: str,
        owner_id: int,
        memory_coefficient: float = 0.85
    ) -> str:
        """
        写入记忆（三写同步）

        同时将记忆写入 SQLite、ChromaDB 和 Tantivy。

        Args:
            content: 记忆内容，第一人称叙事性描述
            owner_id: 所属用户 ID
            memory_coefficient: 记忆系数 [0.0, 1.0]，默认 0.85

        Returns:
            str: 记忆 ID
        """
        # 创建记忆分块
        chunk = MemoryChunk.create(
            owner_id=owner_id,
            content=content,
            memory_coefficient=memory_coefficient
        )

        # 1. 写入 SQLite（主存储）
        await self.db.add_memory(chunk)

        # 2. 生成向量并写入 ChromaDB
        try:
            embedding = await self.embedding_model.get_embedding(content)
            self.vector_store.add_vector(
                memory_id=chunk.id,
                owner_id=owner_id,
                embedding=embedding,
                metadata={
                    "memory_coefficient": memory_coefficient,
                    "timestamp": chunk.timestamp,
                }
            )
        except Exception as e:
            logger.warning("向量化失败: %s", e)

        # 3. 写入 Tantivy BM25 索引
        try:
            self.bm25_index.add_doc(
                memory_id=chunk.id,
                content=content,
                owner_id=owner_id
            )
        except Exception as e:
            logger.warning("BM25索引失败: %s", e)

        logger.info("记忆写入成功: id=%s..., owner_id=%d", chunk.id[:8], owner_id)
        return chunk.id

    async def recall_memories(
        self,
        owner_id: int,
        context: str,
        current_time: Optional[float] = None,
        limit: Optional[int] = None
    ) -> List[Tuple[MemoryChunk, str]]:
        """
        混合检索召回记忆

        1. 并行执行向量检索和 BM25 检索
        2. 合并结果集（并集）
        3. 按记忆系数过滤
        4. 按系数排序返回 top-k
        5. 召回时"唤醒"：系数 boost

        Args:
            owner_id: 所属用户 ID
            context: 查询上下文（用于检索）
            current_time: 当前时间戳（可选，默认使用 time_system）
            limit: 召回数量限制（可选，默认使用配置值）

        Returns:
            List[Tuple[MemoryChunk, str]]: 记忆分块和时间描述列表
        """
        if not self.config.memory_enabled:
            return []

        limit = limit or self.config.recall_limit
        ts = get_time_system()
        current_time = current_time or ts.get_scaled_timestamp()

        # 1. 向量检索 - 语义相似
        vector_results = []
        try:
            query_embedding = await self.embedding_model.get_embedding(context)
            vector_results = self.vector_store.query(
                query_embedding=query_embedding,
                owner_id=owner_id,
                n_results=self.config.recall_vector_results
            )
        except Exception as e:
            logger.warning("向量检索失败: %s", e)

        # 2. BM25 检索 - 关键词匹配
        bm25_results = []
        try:
            bm25_results = self.bm25_index.search(
                query=context,
                owner_id=owner_id,
                limit=self.config.recall_bm25_results
            )
        except Exception as e:
            logger.warning("BM25检索失败: %s", e)

        # 3. 并集去重
        all_ids = set()
        id_source = {}  # 记录 ID 来源

        for r in vector_results:
            memory_id = r["id"]
            all_ids.add(memory_id)
            id_source[memory_id] = "vector"

        for r in bm25_results:
            memory_id = r["id"]
            all_ids.add(memory_id)
            id_source[memory_id] = "bm25"

        # 4. 获取实际数据 + 系数过滤
        all_memories = []
        for memory_id in all_ids:
            chunk = await self.db.get_memory(memory_id)
            if chunk and chunk.memory_coefficient >= self.config.threshold:
                all_memories.append(chunk)

        # 5. 按系数降序排序
        all_memories.sort(key=lambda x: x.memory_coefficient, reverse=True)

        # 6. 唤醒机制：召回时 boost 系数
        result = []
        for chunk in all_memories[:limit]:
            # 计算时间描述（使用独立工具函数）
            time_desc = calculate_time_description(chunk.timestamp, current_time)

            # 唤醒：boost 系数
            new_coef = min(1.0, chunk.memory_coefficient + self.config.boost_factor)
            if new_coef != chunk.memory_coefficient:
                chunk.memory_coefficient = new_coef
                await self.db.update_memory(chunk)
                try:
                    self.vector_store.update_vector(
                        chunk.id,
                        metadata={"memory_coefficient": new_coef}
                    )
                except Exception as e:
                    logger.warning("更新向量元数据失败: %s", e)

            result.append((chunk, time_desc))

        logger.info("记忆召回成功: 查询='%s...', 召回%d条", context[:20], len(result))
        return result

    async def decay_memories(self, decay_rate: Optional[float] = None) -> List[str]:
        """
        记忆衰减

        所有记忆的系数按时间差衰减。时间差越大，衰减越多。
        低于阈值的记忆将被删除。

        Args:
            decay_rate: 每次衰减率，默认使用配置值

        Returns:
            List[str]: 被删除的记忆 ID 列表
        """
        decay_rate = decay_rate or self.config.decay_rate
        ts = get_time_system()
        current_time = ts.get_scaled_timestamp()

        # 获取所有记忆
        all_memories = await self.db.get_all_memories()

        deleted_ids = []
        for chunk in all_memories:
            time_delta = current_time - chunk.timestamp
            # 衰减量与时间差成正比（按天计算）
            decay_amount = decay_rate * (time_delta / 86400)
            chunk.memory_coefficient -= decay_amount

            if chunk.memory_coefficient < self.config.threshold:
                # 低于阈值，删除记忆
                await self.delete_memory(chunk.id)
                deleted_ids.append(chunk.id)
            else:
                # 更新衰减后的系数
                await self.db.update_memory(chunk)
                try:
                    self.vector_store.update_vector(
                        chunk.id,
                        metadata={"memory_coefficient": chunk.memory_coefficient}
                    )
                except Exception as e:
                    logger.warning("更新向量元数据失败: %s", e)

        if deleted_ids:
            logger.info("记忆衰减完成: 删除%d条记忆", len(deleted_ids))
        return deleted_ids

    async def delete_memory(self, memory_id: str) -> None:
        """
        删除记忆，同时从三个存储中移除

        Args:
            memory_id: 要删除的记忆 ID
        """
        # 1. 从 SQLite 删除
        await self.db.delete_memory(memory_id)

        # 2. 从 ChromaDB 删除
        try:
            self.vector_store.delete_vector(memory_id)
        except Exception as e:
            logger.warning("从向量存储删除失败: %s", e)

        # 3. 从 Tantivy 删除
        try:
            self.bm25_index.delete_doc(memory_id)
        except Exception as e:
            logger.warning("从BM25索引删除失败: %s", e)

        logger.info("记忆删除成功: id=%s...", memory_id[:8])

    async def clear_user_memories(self, owner_id: int) -> int:
        """
        清除用户所有记忆（谨慎使用）

        Args:
            owner_id: 用户 ID

        Returns:
            int: 删除的记忆数量
        """
        # 1. 获取用户所有记忆
        user_memories = await self.db.get_user_memories(owner_id)
        count = len(user_memories)

        # 2. 从 SQLite 清除
        await self.db.clear_user_memories(owner_id)

        # 3. 从 ChromaDB 清除（逐个删除）
        for chunk in user_memories:
            try:
                self.vector_store.delete_vector(chunk.id)
            except Exception as e:
                logger.warning("从向量存储删除失败: %s", e)

        # 4. 从 Tantivy 清除（逐个删除）
        for chunk in user_memories:
            try:
                self.bm25_index.delete_doc(chunk.id)
            except Exception as e:
                logger.warning("从BM25索引删除失败: %s", e)

        logger.info("用户记忆清除完成: owner_id=%d, 清除%d条", owner_id, count)
        return count

    def close(self):
        """关闭所有连接"""
        self.db.close()


_memory_service: Optional[MemoryService] = None


def get_memory_service(config: Optional[MemoryConfig] = None) -> MemoryService:
    """
    获取记忆服务单例

    Args:
        config: 记忆系统配置，默认使用全局配置

    Returns:
        MemoryService: 记忆服务实例
    """
    global _memory_service
    if _memory_service is None:
        _memory_service = MemoryService(config)
    return _memory_service
