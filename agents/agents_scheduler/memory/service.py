# 记忆服务核心层
# 统一管理三写同步、混合检索、衰减与唤醒机制

import logging
import math
import threading
from typing import Any, Callable, Dict, List, Literal, Optional, Tuple, cast

from agents.agents_scheduler.memory.config import MemoryConfig, get_memory_config
from agents.agents_scheduler.memory.models import MemoryChunk
from agents.agents_scheduler.memory.database import MemoryDB
from agents.agents_scheduler.memory.vector_store import VectorStore
from agents.agents_scheduler.memory.bm25_index import BM25Index
from agents.agents_scheduler.memory.embedding import EmbeddingModel
from agents.agents_scheduler.memory.utils import (
    calculate_time_description,
    calculate_time_description_from_date,
)
from agents.agents_scheduler.scheduler.time_system import get_time_system

logger = logging.getLogger(__name__)

MEMORY_TYPES = {"normal", "static"}


def _normalize_memory_input(
    content: str,
    owner_id: int | str,
    memory_coefficient: float | str,
    semantic_timestamp: float | str,
    memory_type: str,
) -> Tuple[str, int, float, float, Literal["normal", "static"]]:
    """
    校验并规范化记忆写入参数。

    Args:
        content: 记忆文本。
        owner_id: 记忆所有者平台用户 ID。
        memory_coefficient: 记忆重要度系数。
        semantic_timestamp: 记忆实际发生时间戳，0 表示使用当前时间。
        memory_type: 记忆类型，仅支持 normal 或 static。

    Returns:
        Tuple[str, int, float, float, Literal["normal", "static"]]: 规范化后的参数。

    Raises:
        ValueError: 字段为空、越界、非有限数字或类型非法时抛出。
        TypeError: 内容不是字符串时抛出。
    """
    if not isinstance(content, str):
        raise TypeError("content 必须是字符串")
    normalized_content = content.strip()
    if not normalized_content:
        raise ValueError("content 不能为空")

    if isinstance(owner_id, bool):
        raise ValueError("owner_id 必须是正整数")
    try:
        normalized_owner_id = int(owner_id)
    except (TypeError, ValueError) as exc:
        raise ValueError("owner_id 必须是正整数") from exc
    if normalized_owner_id <= 0 or str(normalized_owner_id) != str(owner_id).strip():
        raise ValueError("owner_id 必须是正整数")

    if isinstance(memory_coefficient, bool):
        raise ValueError("memory_coefficient 必须在 0.0 到 1.0 之间")
    try:
        normalized_coefficient = float(memory_coefficient)
    except (TypeError, ValueError) as exc:
        raise ValueError("memory_coefficient 必须在 0.0 到 1.0 之间") from exc
    if not math.isfinite(normalized_coefficient) or not 0.0 <= normalized_coefficient <= 1.0:
        raise ValueError("memory_coefficient 必须在 0.0 到 1.0 之间")

    if isinstance(semantic_timestamp, bool):
        raise ValueError("semantic_timestamp 必须是非负有限数字")
    try:
        normalized_semantic_timestamp = float(semantic_timestamp)
    except (TypeError, ValueError) as exc:
        raise ValueError("semantic_timestamp 必须是非负有限数字") from exc
    if not math.isfinite(normalized_semantic_timestamp) or normalized_semantic_timestamp < 0:
        raise ValueError("semantic_timestamp 必须是非负有限数字")

    if not isinstance(memory_type, str) or memory_type not in MEMORY_TYPES:
        raise ValueError("memory_type 仅支持 normal 或 static")

    normalized_memory_type = cast(Literal["normal", "static"], memory_type)
    return (
        normalized_content,
        normalized_owner_id,
        normalized_coefficient,
        normalized_semantic_timestamp,
        normalized_memory_type,
    )


def _reciprocal_rank_fusion(
    ranked_result_sets: List[List[Dict[str, Any]]],
    rank_constant: int,
) -> List[Tuple[str, float]]:
    """
    使用 Reciprocal Rank Fusion 合并多个检索器的排名。

    RRF 仅依赖各检索器内部名次，不直接混合量纲不同的向量距离和 BM25
    分数。多路检索都命中的记忆会自然获得更高的融合分数。

    Args:
        ranked_result_sets: 各检索器按相关性降序返回的结果列表，元素必须包含 id。
        rank_constant: RRF 排名常数，必须大于 0。

    Returns:
        List[Tuple[str, float]]: 按融合分数降序排列的记忆 ID 与分数。

    Raises:
        ValueError: rank_constant 不大于 0 时抛出。
    """
    if rank_constant <= 0:
        raise ValueError("RRF rank_constant 必须大于 0")

    fused_scores: Dict[str, float] = {}
    first_seen_order: Dict[str, int] = {}
    next_order = 0

    for result_set in ranked_result_sets:
        seen_in_result_set = set()
        for rank, item in enumerate(result_set, start=1):
            memory_id = str(item.get("id", "")).strip()
            if not memory_id or memory_id in seen_in_result_set:
                continue
            seen_in_result_set.add(memory_id)
            if memory_id not in first_seen_order:
                first_seen_order[memory_id] = next_order
                next_order += 1
            fused_scores[memory_id] = (
                fused_scores.get(memory_id, 0.0) + 1.0 / (rank_constant + rank)
            )

    return sorted(
        fused_scores.items(),
        key=lambda item: (-item[1], first_seen_order[item[0]], item[0]),
    )


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
        self._config_lock = threading.RLock()
        self.db = MemoryDB(self.config)
        self.vector_store = VectorStore(self.config)
        self.bm25_index = BM25Index(self.config)
        self.embedding_model = EmbeddingModel(self.config)
        self._synchronize_vector_metadata()

    def reload_config(self, config: MemoryConfig) -> None:
        """
        在保留已打开存储索引的前提下热更新运行配置。

        Args:
            config: 从 management 数据库重新加载的记忆配置。

        Returns:
            None: 配置与 Embedding 客户端替换完成后直接返回。
        """
        with self._config_lock:
            self.config = config
            self.embedding_model = EmbeddingModel(config)

    @staticmethod
    def _vector_metadata(chunk: MemoryChunk) -> Dict[str, Any]:
        """
        生成 Chroma 检索和过滤使用的完整元数据。

        Args:
            chunk: SQLite 中的记忆主数据。

        Returns:
            Dict[str, Any]: 包含所有者、类型、时间和重要度的元数据。
        """
        return {
            "owner_id": chunk.owner_id,
            "memory_coefficient": chunk.memory_coefficient,
            "timestamp": chunk.timestamp,
            "semantic_timestamp": chunk.semantic_timestamp,
            "memory_type": chunk.memory_type,
        }

    def _synchronize_vector_metadata(self) -> None:
        """
        将历史 Chroma 记录的过滤元数据补齐到当前模型。

        该步骤只更新已存在的向量记录，不会触发重新 Embedding。

        Returns:
            None: 同步成功或记录警告后直接返回。
        """
        try:
            memories = self.db._get_all_memories_sync()
            metadata_by_id = {
                chunk.id: self._vector_metadata(chunk)
                for chunk in memories
            }
            self.vector_store.update_existing_metadatas(metadata_by_id)
        except Exception as exc:
            logger.warning("历史向量元数据同步失败: %s", exc)

    async def write_memory(
        self,
        content: str,
        owner_id: int | str,
        memory_coefficient: float | str = 0.85,
        semantic_timestamp: float | str = 0.0,
        memory_type: str = "normal",
    ) -> str:
        """
        写入记忆（三写同步）

        同时将记忆写入 SQLite、ChromaDB 和 Tantivy。

        Args:
            content: 记忆内容，第一人称叙事性描述
            owner_id: 所属用户 ID
            memory_coefficient: 记忆系数 [0.0, 1.0]，默认 0.85
            semantic_timestamp: 语义时间戳，默认为 0 表示使用当前系统时间
            memory_type: 记忆类型，"normal" 为普通记忆，"static" 为静态记忆

        Returns:
            str: 记忆 ID
        """
        (
            content,
            owner_id,
            memory_coefficient,
            semantic_timestamp,
            memory_type,
        ) = _normalize_memory_input(
            content,
            owner_id,
            memory_coefficient,
            semantic_timestamp,
            memory_type,
        )

        # 创建记忆分块
        chunk = MemoryChunk.create(
            owner_id=owner_id,
            content=content,
            memory_coefficient=memory_coefficient,
            semantic_timestamp=semantic_timestamp,
            memory_type=memory_type,
        )

        with self._config_lock:
            embedding_model = self.embedding_model

        # 1. 写入 SQLite（主存储）
        await self.db.add_memory(chunk)

        # 2. 生成向量并写入 ChromaDB
        try:
            embedding = await embedding_model.get_embedding(content)
            self.vector_store.add_vector(
                memory_id=chunk.id,
                owner_id=owner_id,
                embedding=embedding,
                metadata=self._vector_metadata(chunk),
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
        limit: Optional[int] = None,
    ) -> List[Tuple[MemoryChunk, str]]:
        """
        混合检索召回记忆

        1. 分别执行向量检索和 BM25 检索
        2. 使用 RRF 融合两路排名
        3. 按记忆系数过滤
        4. 按相关性返回 top-k
        5. 召回时执行唤醒 boost

        Args:
            owner_id: 所属用户 ID
            context: 查询上下文（用于检索）
            current_time: 当前时间戳（可选，默认使用 time_system）
            limit: 召回数量限制（可选，默认使用配置值）

        Returns:
            List[Tuple[MemoryChunk, str]]: 记忆分块和时间描述列表
        """
        with self._config_lock:
            config = self.config
            embedding_model = self.embedding_model

        if not config.memory_enabled:
            return []

        limit = limit or config.recall_limit
        ts = get_time_system()
        current_time = current_time or ts.get_scaled_timestamp()

        # 1. 向量检索 - 语义相似
        vector_results = []
        try:
            query_embedding = await embedding_model.get_embedding(context)
            vector_results = self.vector_store.query(
                query_embedding=query_embedding,
                owner_id=owner_id,
                n_results=config.recall_vector_results
            )
        except Exception as e:
            logger.warning("向量检索失败: %s", e)

        # 2. BM25 检索 - 关键词匹配
        bm25_results = []
        try:
            bm25_results = self.bm25_index.search(
                query=context,
                owner_id=owner_id,
                limit=config.recall_bm25_results
            )
        except Exception as e:
            logger.warning("BM25检索失败: %s", e)

        # 3. 使用 RRF 融合两路排名，避免直接混合不同量纲的原始分数
        fused_results = _reciprocal_rank_fusion(
            [vector_results, bm25_results],
            config.rrf_rank_constant,
        )

        # 4. 获取实际数据并过滤；相关性为主，记忆系数仅用于融合分数相同的情况
        ranked_memories = await self._load_ranked_memories(
            fused_results,
            lambda chunk: chunk.memory_coefficient >= config.threshold,
        )

        # 5. 唤醒机制：召回时 boost 系数（静态记忆不参与唤醒）
        result = []
        for chunk in ranked_memories[:limit]:
            # 计算时间描述（优先使用语义时间戳）
            if chunk.semantic_timestamp > 0 and chunk.semantic_timestamp > 1000000:
                time_desc = calculate_time_description_from_date(chunk.semantic_timestamp)
            else:
                time_desc = calculate_time_description(chunk.timestamp, current_time)

            # 唤醒：boost 系数（仅对普通记忆）
            if chunk.memory_type == "normal":
                new_coef = min(1.0, chunk.memory_coefficient + config.boost_factor)
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

    async def recall_memories_with_time_filter(
        self,
        owner_id: int,
        context: str,
        max_semantic_timestamp: float,
        limit: Optional[int] = None
    ) -> List[Tuple[MemoryChunk, str]]:
        """
        混合检索召回记忆（带时间过滤，用于 LLM 分块场景）

        与 recall_static_memories 的区别：
        1. 召回所有类型的记忆（normal + static），不仅限于 static
        2. 过滤掉 semantic_timestamp 大于 max_semantic_timestamp 的记忆
        3. 不触发 boost 唤醒机制，不改变记忆系数

        Args:
            owner_id: 所属用户 ID
            context: 查询上下文（用于检索）
            max_semantic_timestamp: 最大语义时间戳，仅召回此时间之前的记忆
            limit: 召回数量限制（可选，默认使用配置值）

        Returns:
            List[Tuple[MemoryChunk, str]]: 记忆分块和时间描述列表
        """
        with self._config_lock:
            config = self.config
            embedding_model = self.embedding_model

        if not config.memory_enabled:
            return []

        limit = limit or config.recall_limit
        ts = get_time_system()
        current_time = ts.get_scaled_timestamp()

        # 1. 向量检索 - 语义相似
        vector_results = []
        try:
            query_embedding = await embedding_model.get_embedding(context)
            vector_results = self.vector_store.query(
                query_embedding=query_embedding,
                owner_id=owner_id,
                n_results=config.recall_vector_results,
                max_semantic_timestamp=max_semantic_timestamp,
            )
        except Exception as e:
            logger.warning("向量检索失败: %s", e)

        # 2. BM25 检索 - 关键词匹配
        bm25_results = []
        try:
            bm25_results = self.bm25_index.search(
                query=context,
                owner_id=owner_id,
                limit=config.recall_bm25_results
            )
        except Exception as e:
            logger.warning("BM25检索失败: %s", e)

        # 3. 融合排名后再加载主数据，时间与重要度只作为过滤条件
        fused_results = _reciprocal_rank_fusion(
            [vector_results, bm25_results],
            config.rrf_rank_constant,
        )
        ranked_memories = await self._load_ranked_memories(
            fused_results,
            lambda chunk: (
                chunk.semantic_timestamp <= max_semantic_timestamp
                and chunk.memory_coefficient >= config.threshold
            ),
        )

        # 4. 生成结果（不触发 boost）
        result = []
        for chunk in ranked_memories[:limit]:
            if chunk.semantic_timestamp > 0 and chunk.semantic_timestamp > 1000000:
                time_desc = calculate_time_description_from_date(chunk.semantic_timestamp)
            else:
                time_desc = calculate_time_description(chunk.timestamp, current_time)
            result.append((chunk, time_desc))

        logger.info("时间过滤记忆召回成功: 查询='%s...', 召回%d条", context[:20], len(result))
        return result

    async def recall_static_memories(
        self,
        owner_id: int,
        context: str,
        limit: Optional[int] = None
    ) -> List[Tuple[MemoryChunk, str]]:
        """
        混合检索召回静态记忆（用于 LLM 分块场景）

        与 recall_memories 的区别：
        1. 只召回 memory_type="static" 的记忆
        2. 不触发 boost 唤醒机制，不改变记忆系数

        Args:
            owner_id: 所属用户 ID
            context: 查询上下文（用于检索）
            limit: 召回数量限制（可选，默认使用配置值）

        Returns:
            List[Tuple[MemoryChunk, str]]: 记忆分块和时间描述列表
        """
        with self._config_lock:
            config = self.config
            embedding_model = self.embedding_model

        if not config.memory_enabled:
            return []

        limit = limit or config.recall_limit
        ts = get_time_system()
        current_time = ts.get_scaled_timestamp()

        # 1. 向量检索 - 语义相似
        vector_results = []
        try:
            query_embedding = await embedding_model.get_embedding(context)
            vector_results = self.vector_store.query(
                query_embedding=query_embedding,
                owner_id=owner_id,
                n_results=config.recall_vector_results,
                memory_type="static",
            )
        except Exception as e:
            logger.warning("向量检索失败: %s", e)

        # 2. BM25 检索 - 关键词匹配
        bm25_results = []
        try:
            bm25_results = self.bm25_index.search(
                query=context,
                owner_id=owner_id,
                limit=config.recall_bm25_results
            )
        except Exception as e:
            logger.warning("BM25检索失败: %s", e)

        # 3. 融合排名后再加载主数据，类型与重要度只作为过滤条件
        fused_results = _reciprocal_rank_fusion(
            [vector_results, bm25_results],
            config.rrf_rank_constant,
        )
        ranked_memories = await self._load_ranked_memories(
            fused_results,
            lambda chunk: (
                chunk.memory_type == "static"
                and chunk.memory_coefficient >= config.threshold
            ),
        )

        # 4. 生成结果（静态记忆不触发 boost）
        result = []
        for chunk in ranked_memories[:limit]:
            if chunk.semantic_timestamp > 0 and chunk.semantic_timestamp > 1000000:
                time_desc = calculate_time_description_from_date(chunk.semantic_timestamp)
            else:
                time_desc = calculate_time_description(chunk.timestamp, current_time)
            result.append((chunk, time_desc))

        logger.info("静态记忆召回成功: 查询='%s...', 召回%d条", context[:20], len(result))
        return result

    async def _load_ranked_memories(
        self,
        fused_results: List[Tuple[str, float]],
        predicate: Callable[[MemoryChunk], bool],
    ) -> List[MemoryChunk]:
        """
        按融合排名批量语义加载候选记忆并执行主数据过滤。

        当前候选池较小，仍逐条读取 SQLite；该方法集中保留融合分数，后续可在
        不改变排序语义的前提下替换为批量查询。

        Args:
            fused_results: RRF 输出的记忆 ID 与融合分数。
            predicate: 针对 SQLite 主数据执行的过滤函数。

        Returns:
            List[MemoryChunk]: 相关性优先、重要度仅作同分排序的记忆列表。
        """
        candidates: List[Tuple[MemoryChunk, float]] = []
        for memory_id, fused_score in fused_results:
            chunk = await self.db.get_memory(memory_id)
            if chunk and predicate(chunk):
                candidates.append((chunk, fused_score))

        candidates.sort(
            key=lambda item: (-item[1], -item[0].memory_coefficient, item[0].id),
        )
        return [chunk for chunk, _ in candidates]

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
        with self._config_lock:
            config = self.config

        if not config.memory_enabled:
            return []

        decay_rate = decay_rate or config.decay_rate
        ts = get_time_system()
        current_time = ts.get_scaled_timestamp()

        # 获取所有记忆
        all_memories = await self.db.get_all_memories()

        deleted_ids = []
        for chunk in all_memories:
            # 静态记忆不参与衰减，系数恒定不变
            if chunk.memory_type == "static":
                continue

            last_decay_timestamp = chunk.last_decay_timestamp or chunk.timestamp
            time_delta = max(0.0, current_time - last_decay_timestamp)
            if time_delta == 0:
                continue

            # 仅扣除上次衰减后的新增时间，避免定时任务重复计算完整记忆年龄
            decay_amount = decay_rate * (time_delta / 86400)
            chunk.memory_coefficient -= decay_amount
            chunk.last_decay_timestamp = current_time

            if chunk.memory_coefficient < config.threshold:
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
_memory_service_lock = threading.RLock()


def get_memory_service(config: Optional[MemoryConfig] = None) -> MemoryService:
    """
    获取记忆服务单例

    Args:
        config: 记忆系统配置，默认使用全局配置

    Returns:
        MemoryService: 记忆服务实例
    """
    global _memory_service
    with _memory_service_lock:
        if _memory_service is None:
            _memory_service = MemoryService(config)
        return _memory_service


def reload_memory_service(config: Optional[MemoryConfig] = None) -> MemoryService:
    """
    将最新配置应用到已存在的记忆服务和 Embedding 客户端。

    存储索引对象保持不变，避免热更新时重复打开 Tantivy writer。

    Args:
        config: 可选的已重载配置；未提供时读取当前配置单例。

    Returns:
        MemoryService: 已应用新配置的全局记忆服务。
    """
    global _memory_service
    resolved_config = config or get_memory_config()
    with _memory_service_lock:
        if _memory_service is None:
            _memory_service = MemoryService(resolved_config)
        else:
            _memory_service.reload_config(resolved_config)
        return _memory_service
