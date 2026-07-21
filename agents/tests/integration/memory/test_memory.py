import sqlite3
import sys
import threading
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agents.agents_scheduler.memory.utils import calculate_time_description
from agents.agents_scheduler.memory.models import MemoryChunk
from agents.agents_scheduler.memory.chinese_tokenizer import tokenize_chinese, tokenize_query
from agents.agents_scheduler.memory.config import MemoryConfig
from agents.agents_scheduler.memory.database import MemoryDB
from agents.agents_scheduler.memory.bm25_index import BM25Index
from agents.agents_scheduler.memory.migrations import run_memory_migrations
from agents.agents_scheduler.memory.service import (
    MemoryService,
    _normalize_memory_input,
    _reciprocal_rank_fusion,
)
from agents.agents_scheduler.memory.vector_store import VectorStore


class TestCalculateTimeDescription:
    def test_just_now(self):
        current = 1000.0
        past = 950.0
        result = calculate_time_description(past, current)
        assert result == "刚刚"

    def test_minutes_ago(self):
        current = 1000.0
        past = 400.0
        result = calculate_time_description(past, current)
        assert "分钟前" in result

    def test_hours_ago(self):
        current = 10000.0
        past = 2000.0
        result = calculate_time_description(past, current)
        assert "小时前" in result

    def test_days_ago(self):
        current = 1000000.0
        past = 100000.0
        result = calculate_time_description(past, current)
        assert "天前" in result

    def test_months_ago(self):
        current = 10000000.0
        past = 1000000.0
        result = calculate_time_description(past, current)
        assert "个月前" in result

    def test_years_ago(self):
        current = 100000000.0
        past = 10000000.0
        result = calculate_time_description(past, current)
        assert "年前" in result

    def test_future(self):
        current = 100.0
        past = 200.0
        result = calculate_time_description(past, current)
        assert result == "未来"


class TestMemoryChunk:
    def test_memory_chunk_create(self):
        with patch("agents.agents_scheduler.memory.models.get_time_system") as mock_ts:
            mock_ts.return_value.get_scaled_timestamp.return_value = 1000.0
            chunk = MemoryChunk.create(
                owner_id=1,
                content="test memory",
                memory_coefficient=0.9
            )
            assert chunk.owner_id == 1
            assert chunk.content == "test memory"
            assert chunk.memory_coefficient == 0.9
            assert chunk.timestamp == 1000.0
            assert chunk.last_decay_timestamp == 1000.0
            assert chunk.id is not None

    def test_memory_chunk_to_dict(self):
        chunk = MemoryChunk(
            id="test-id",
            owner_id=1,
            content="test memory",
            timestamp=1000.0,
            memory_coefficient=0.85,
        )
        d = chunk.to_dict()
        assert d["id"] == "test-id"
        assert d["owner_id"] == 1
        assert d["content"] == "test memory"
        assert d["timestamp"] == 1000.0
        assert d["memory_coefficient"] == 0.85
        assert d["last_decay_timestamp"] == 0.0

    def test_memory_chunk_from_dict(self):
        data = {
            "id": "test-id",
            "owner_id": 1,
            "content": "test memory",
            "timestamp": 1000.0,
            "memory_coefficient": 0.85,
        }
        chunk = MemoryChunk.from_dict(data)
        assert chunk.id == "test-id"
        assert chunk.owner_id == 1
        assert chunk.content == "test memory"
        assert chunk.last_decay_timestamp == 1000.0

    def test_memory_chunk_repr(self):
        chunk = MemoryChunk(
            id="test-id-123456",
            owner_id=1,
            content="test memory",
            timestamp=1000.0,
            memory_coefficient=0.85,
        )
        repr_str = repr(chunk)
        assert "test-id" in repr_str
        assert "0.85" in repr_str

    def test_memory_chunk_repr_truncated(self):
        chunk = MemoryChunk(
            id="test-id",
            owner_id=1,
            content="x" * 100,
            timestamp=1000.0,
            memory_coefficient=0.85,
        )
        repr_str = repr(chunk)
        assert "..." in repr_str


class TestChineseTokenizer:
    def test_tokenize_chinese_basic(self):
        result = tokenize_chinese("今天天气很好")
        assert isinstance(result, list)
        assert len(result) > 0

    def test_tokenize_query_basic(self):
        result = tokenize_query("测试查询")
        assert isinstance(result, list)
        assert len(result) > 0

    def test_tokenize_empty(self):
        result = tokenize_chinese("")
        assert isinstance(result, list)

    def test_tokenize_returns_list_of_strings(self):
        result = tokenize_chinese("你好世界")
        for token in result:
            assert isinstance(token, str)


class TestHybridRetrievalRanking:
    """验证混合检索融合和业务重要度的排序边界。"""

    def test_rrf_promotes_results_found_by_both_retrievers(self):
        """两路检索都命中的候选应优先于只被单路命中的候选。"""
        vector_results = [{"id": "vector-only"}, {"id": "shared"}]
        bm25_results = [{"id": "shared"}, {"id": "bm25-only"}]

        fused = _reciprocal_rank_fusion([vector_results, bm25_results], rank_constant=60)

        assert fused[0][0] == "shared"
        assert {memory_id for memory_id, _ in fused} == {
            "vector-only",
            "shared",
            "bm25-only",
        }

    @pytest.mark.asyncio
    async def test_memory_coefficient_changes_close_relevance_order(self):
        """重要度权重应参与最终分数，并能改变相关性接近的候选顺序。"""
        relevant = MemoryChunk(
            id="relevant",
            owner_id=1,
            content="相关记忆",
            timestamp=1000.0,
            memory_coefficient=0.4,
        )
        important = MemoryChunk(
            id="important",
            owner_id=1,
            content="高重要度但较不相关",
            timestamp=1000.0,
            memory_coefficient=1.0,
        )
        service = MemoryService.__new__(MemoryService)
        service.db = MagicMock()
        service.db.get_memory = AsyncMock(side_effect=[relevant, important])

        memories = await service._load_ranked_memories(
            [("relevant", 0.03), ("important", 0.029)],
            owner_id=1,
            predicate=lambda _: True,
            importance_weight=0.3,
        )

        assert [chunk.id for chunk in memories] == ["important", "relevant"]

    @pytest.mark.asyncio
    async def test_sqlite_owner_check_rejects_foreign_index_candidate(self):
        """即使派生索引返回了错误候选，也不得跨 owner 加载 SQLite 主数据。"""
        foreign = MemoryChunk(
            id="foreign",
            owner_id=2,
            content="其他用户的记忆",
            timestamp=1000.0,
            memory_coefficient=1.0,
        )
        service = MemoryService.__new__(MemoryService)
        service.db = MagicMock()
        service.db.get_memory = AsyncMock(return_value=foreign)

        memories = await service._load_ranked_memories(
            [("foreign", 0.03)],
            owner_id=1,
            predicate=lambda _: True,
            importance_weight=0.3,
        )

        assert memories == []

    @pytest.mark.asyncio
    async def test_candidate_window_expands_until_enough_valid_memories(self):
        """主数据过滤淘汰候选后，检索窗口应继续扩大直至补足结果。"""
        valid = MemoryChunk(
            id="valid",
            owner_id=1,
            content="有效记忆",
            timestamp=1000.0,
            memory_coefficient=0.8,
        )
        service = MemoryService.__new__(MemoryService)
        service.vector_store = MagicMock()
        service.vector_store.query.side_effect = [
            [{"id": "stale"}],
            [{"id": "stale"}, {"id": "valid"}],
        ]
        service.bm25_index = MagicMock()
        service.bm25_index.search.return_value = []
        service.db = MagicMock()
        service.db.get_memory = AsyncMock(
            side_effect=lambda memory_id: valid if memory_id == "valid" else None
        )
        embedding_model = MagicMock()
        embedding_model.get_embedding = AsyncMock(return_value=[0.1, 0.2])
        config = MemoryConfig(
            recall_vector_results=1,
            recall_bm25_results=1,
            recall_max_candidates=4,
        )

        memories = await service._retrieve_ranked_memories(
            owner_id=1,
            context="查询",
            limit=1,
            config=config,
            embedding_model=embedding_model,
            predicate=lambda _: True,
        )

        assert [chunk.id for chunk in memories] == ["valid"]
        assert [
            call.kwargs["n_results"] for call in service.vector_store.query.call_args_list
        ] == [1, 2]


class TestBM25OwnerFiltering:
    """验证 owner 条件在 Tantivy 内部参与查询而不是事后截断。"""

    def test_owner_filter_is_applied_before_limit(self, tmp_path):
        """其他 owner 的高分文档不得占满当前 owner 的 top-k 窗口。"""
        index = BM25Index(MemoryConfig(memory_dir=str(tmp_path)))
        memories = [
            {"id": f"foreign-{position}", "content": "苹果 苹果 苹果", "owner_id": 2}
            for position in range(20)
        ]
        memories.append({"id": "owned", "content": "苹果", "owner_id": 1})

        index.rebuild(memories)
        results = index.search("苹果", owner_id=1, limit=1)

        assert [result["id"] for result in results] == ["owned"]
        assert index.get_doc_count(owner_id=1) == 1

    def test_global_search_does_not_apply_owner_filter(self, tmp_path):
        """管理端全局检索应允许不同 owner 的文档共同进入排序。"""
        index = BM25Index(MemoryConfig(memory_dir=str(tmp_path)))
        index.rebuild([
            {"id": "owner-1", "content": "共同关键词", "owner_id": 1},
            {"id": "owner-2", "content": "共同关键词", "owner_id": 2},
        ])

        results = index.search("共同关键词", owner_id=None, limit=10)

        assert {result["id"] for result in results} == {"owner-1", "owner-2"}


class TestManagementMemorySearch:
    """验证管理检索复用正式召回配置，但取消 top-k 并保持无副作用。"""

    @pytest.mark.asyncio
    async def test_search_uses_scope_total_as_candidate_limit(self):
        """全局检索应以主数据总量覆盖 recall_limit 与候选上限。"""
        memories = [
            MemoryChunk(
                id=f"memory-{index}",
                owner_id=index + 1,
                content=f"记忆 {index}",
                timestamp=1000.0,
                memory_coefficient=0.8,
            )
            for index in range(3)
        ]
        service = MemoryService.__new__(MemoryService)
        service._config_lock = threading.RLock()
        service.config = MemoryConfig(recall_limit=1, recall_max_candidates=1)
        service.embedding_model = MagicMock()
        service.db = MagicMock()
        service.db.get_all_memories = AsyncMock(return_value=memories)
        service._retrieve_ranked_memories = AsyncMock(return_value=memories)

        result = await service.search_memories("  共同主题  ")

        assert result == memories
        call = service._retrieve_ranked_memories.await_args.kwargs
        assert call["owner_id"] is None
        assert call["context"] == "共同主题"
        assert call["limit"] == 3
        assert call["max_candidates"] == 3

    @pytest.mark.asyncio
    async def test_owner_search_reads_only_that_owner_scope(self):
        """角色页检索应在 Chroma、BM25 和 SQLite 三层保持 owner 隔离。"""
        memory = MemoryChunk(
            id="owned",
            owner_id=42,
            content="角色记忆",
            timestamp=1000.0,
            memory_coefficient=0.8,
        )
        service = MemoryService.__new__(MemoryService)
        service._config_lock = threading.RLock()
        service.config = MemoryConfig()
        service.embedding_model = MagicMock()
        service.db = MagicMock()
        service.db.get_user_memories = AsyncMock(return_value=[memory])
        service._retrieve_ranked_memories = AsyncMock(return_value=[memory])

        await service.search_memories("主题", owner_id=42)

        service.db.get_user_memories.assert_awaited_once_with(42)
        assert service._retrieve_ranked_memories.await_args.kwargs["owner_id"] == 42


class TestMemoryEditing:
    """验证单条编辑的主数据提交与响应后派生索引重建。"""

    @pytest.mark.asyncio
    async def test_update_primary_preserves_identity_and_updates_editable_fields(self):
        """管理编辑不得改变 owner、创建时间和记忆 ID。"""
        original = MemoryChunk(
            id="editable",
            owner_id=42,
            content="旧内容",
            timestamp=1000.0,
            semantic_timestamp=900.0,
            memory_coefficient=0.5,
        )
        service = MemoryService.__new__(MemoryService)
        service.db = MagicMock()
        service.db.get_memory = AsyncMock(return_value=original)
        service.db.update_memory = AsyncMock()

        updated = await service.update_memory_primary(
            memory_id="editable",
            content="  新内容  ",
            memory_coefficient=0.9,
            semantic_timestamp=1200.0,
            memory_type="static",
        )

        assert updated is original
        assert updated.id == "editable"
        assert updated.owner_id == 42
        assert updated.timestamp == 1000.0
        assert updated.content == "新内容"
        assert updated.semantic_timestamp == 1200.0
        assert updated.memory_coefficient == 0.9
        assert updated.memory_type == "static"
        service.db.update_memory.assert_awaited_once_with(original)

    @pytest.mark.asyncio
    async def test_refresh_indexes_reembeds_and_replaces_both_indexes(self):
        """内容编辑后必须用当前 Embedding 配置重嵌入，并替换 BM25 文档。"""
        memory = MemoryChunk(
            id="editable",
            owner_id=42,
            content="新内容",
            timestamp=1000.0,
            semantic_timestamp=900.0,
            memory_coefficient=0.8,
        )
        service = MemoryService.__new__(MemoryService)
        service._config_lock = threading.RLock()
        service.embedding_model = MagicMock()
        service.embedding_model.get_embedding = AsyncMock(return_value=[0.1, 0.2])
        service.db = MagicMock()
        service.db.get_memory = AsyncMock(return_value=memory)
        service.vector_store = MagicMock()
        service.bm25_index = MagicMock()

        await service.refresh_memory_indexes("editable")

        service.embedding_model.get_embedding.assert_awaited_once_with("新内容")
        service.vector_store.upsert_vector.assert_called_once_with(
            memory_id="editable",
            embedding=[0.1, 0.2],
            metadata=service._vector_metadata(memory),
        )
        service.bm25_index.delete_doc.assert_called_once_with("editable")
        service.bm25_index.add_doc.assert_called_once_with("editable", "新内容", 42)


class TestMemoryInputValidation:
    """验证记忆写入边界在服务层统一收口。"""

    def test_normalizes_valid_input(self):
        """合法的字符串数字应被规范化为存储类型。"""
        normalized = _normalize_memory_input(
            "  我看到了一条帖子  ",
            "42",
            "0.8",
            "1000",
            "normal",
        )

        assert normalized == ("我看到了一条帖子", 42, 0.8, 1000.0, "normal")

    @pytest.mark.parametrize(
        ("field", "value"),
        [
            ("content", "   "),
            ("owner_id", 0),
            ("memory_coefficient", 1.1),
            ("memory_coefficient", float("nan")),
            ("semantic_timestamp", -1),
            ("memory_type", "unknown"),
        ],
    )
    def test_rejects_invalid_input(self, field, value):
        """空内容、非法所有者和越界数值应被拒绝。"""
        arguments = {
            "content": "有效记忆",
            "owner_id": 1,
            "memory_coefficient": 0.8,
            "semantic_timestamp": 1000.0,
            "memory_type": "normal",
        }
        arguments[field] = value

        with pytest.raises((TypeError, ValueError)):
            _normalize_memory_input(**arguments)


class TestMemoryServiceReload:
    """验证记忆热更新同时替换业务配置和 Embedding 客户端。"""

    def test_reload_config_applies_credential_change(self):
        """新的 Embedding 凭据应立即应用到已存在服务。"""
        service = MemoryService.__new__(MemoryService)
        service._config_lock = threading.RLock()
        service.config = MemoryConfig(
            embedding_base_url="https://example/v1",
            embedding_model_name="same-model",
            embedding_api_key="old-key",
        )
        service.embedding_model = MagicMock()
        service.vector_store = MagicMock()
        service.db = MagicMock()
        new_config = MemoryConfig(
            embedding_base_url="https://example/v1",
            embedding_model_name="same-model",
            embedding_api_key="new-key",
        )

        service.reload_config(new_config)

        assert service.config is new_config
        assert service.embedding_model.api_key == "new-key"
        service.vector_store.get_vector_count.assert_not_called()

    def test_reload_config_allows_model_change_with_existing_vectors(self):
        """暂未实现索引重建时，已有向量不应阻止 Embedding 模型切换。"""
        service = MemoryService.__new__(MemoryService)
        service._config_lock = threading.RLock()
        service.config = MemoryConfig(embedding_model_name="old-model")
        service.embedding_model = MagicMock()
        service.vector_store = MagicMock()
        service.vector_store.get_vector_count.return_value = 1
        service.db = MagicMock()
        new_config = MemoryConfig(embedding_model_name="new-model")

        service.reload_config(new_config)

        assert service.config is new_config
        assert service.embedding_model.model_name == "new-model"
        service.vector_store.get_vector_count.assert_not_called()


class TestVectorMetadataFiltering:
    """验证 Chroma 在召回候选前应用业务元数据过滤。"""

    def test_vector_metadata_snapshot_contains_all_filter_fields(self):
        """系数更新使用的完整快照必须保留 owner、类型和时间过滤字段。"""
        chunk = MemoryChunk(
            id="metadata-memory",
            owner_id=42,
            content="元数据测试",
            timestamp=1000.0,
            semantic_timestamp=900.0,
            memory_coefficient=0.8,
            memory_type="normal",
            last_boost_timestamp=800.0,
        )

        metadata = MemoryService._vector_metadata(chunk)

        assert metadata == {
            "owner_id": 42,
            "memory_coefficient": 0.8,
            "timestamp": 1000.0,
            "semantic_timestamp": 900.0,
            "memory_type": "normal",
            "last_boost_timestamp": 800.0,
        }

    def test_query_pushes_type_and_time_filters_to_chroma(self):
        """记忆类型和最大语义时间应进入 Chroma where 条件。"""
        store = VectorStore.__new__(VectorStore)
        store._lock = threading.RLock()
        store.collection = MagicMock()
        store.collection.query.return_value = {
            "ids": [[]],
            "metadatas": [[]],
            "distances": [[]],
        }

        store.query(
            query_embedding=[0.1, 0.2],
            owner_id=42,
            n_results=20,
            memory_type="static",
            max_semantic_timestamp=1234.0,
        )

        where = store.collection.query.call_args.kwargs["where"]
        assert where == {
            "$and": [
                {"owner_id": 42},
                {"memory_type": "static"},
                {"semantic_timestamp": {"$lte": 1234.0}},
            ]
        }

    def test_global_query_omits_owner_where_filter(self):
        """跨角色管理检索不应向 Chroma 注入 owner 条件。"""
        store = VectorStore.__new__(VectorStore)
        store._lock = threading.RLock()
        store.collection = MagicMock()
        store.collection.query.return_value = {
            "ids": [[]],
            "metadatas": [[]],
            "distances": [[]],
        }

        store.query(query_embedding=[0.1, 0.2], owner_id=None, n_results=20)

        assert "where" not in store.collection.query.call_args.kwargs


class TestMemoryDecay:
    """验证记忆衰减只处理上次执行后的新增时间。"""

    @pytest.mark.asyncio
    async def test_repeated_decay_at_same_time_is_idempotent(self):
        """相同时间点重复运行衰减任务不应重复扣减系数。"""
        chunk = MemoryChunk(
            id="memory-id",
            owner_id=1,
            content="测试记忆",
            timestamp=1000.0,
            memory_coefficient=0.8,
            last_decay_timestamp=1000.0,
        )
        current_time = 1000.0 + 86400.0
        service = MemoryService.__new__(MemoryService)
        service.config = MagicMock(decay_rate=0.1, threshold=0.3)
        service.config.memory_enabled = True
        service._config_lock = threading.RLock()
        service.db = MagicMock()
        service.db.get_all_memories = AsyncMock(return_value=[chunk])
        service.db.update_memory = AsyncMock()
        service.vector_store = MagicMock()

        with patch(
            "agents.agents_scheduler.memory.service.get_time_system"
        ) as mock_time_system:
            mock_time_system.return_value.get_scaled_timestamp.return_value = current_time
            await service.decay_memories()
            await service.decay_memories()

        assert chunk.memory_coefficient == pytest.approx(0.7)
        assert chunk.last_decay_timestamp == current_time
        service.db.update_memory.assert_awaited_once()


class TestMemoryDatabaseMigration:
    """验证记忆数据库迁移和新增字段持久化。"""

    def test_last_decay_timestamp_is_persisted(self, tmp_path):
        """新建数据库应包含并正确读写增量衰减时间戳。"""
        database = MemoryDB(MemoryConfig(memory_dir=str(tmp_path)))
        chunk = MemoryChunk(
            id="migration-memory",
            owner_id=1,
            content="迁移测试记忆",
            timestamp=1000.0,
            memory_coefficient=0.8,
            last_decay_timestamp=2000.0,
        )

        try:
            database._add_memory_sync(chunk)
            restored = database._get_memory_sync(chunk.id)
        finally:
            database.close()

        assert restored is not None
        assert restored.last_decay_timestamp == 2000.0

    @pytest.mark.asyncio
    async def test_boost_cooldown_is_checked_atomically(self, tmp_path):
        """冷却窗口内重复召回不得再次增强，窗口结束后才允许下一次增强。"""
        database = MemoryDB(MemoryConfig(memory_dir=str(tmp_path)))
        chunk = MemoryChunk(
            id="cooldown-memory",
            owner_id=1,
            content="冷却测试记忆",
            timestamp=1000.0,
            memory_coefficient=0.7,
            last_decay_timestamp=1000.0,
        )

        try:
            await database.add_memory(chunk)
            first = await database.try_boost_memory(
                chunk.id, 1, 0.1, current_time=1000.0, cooldown_seconds=100
            )
            cooling = await database.try_boost_memory(
                chunk.id, 1, 0.1, current_time=1050.0, cooldown_seconds=100
            )
            after_cooldown = await database.try_boost_memory(
                chunk.id, 1, 0.1, current_time=1101.0, cooldown_seconds=100
            )
        finally:
            database.close()

        assert first is not None
        assert first.memory_coefficient == pytest.approx(0.8)
        assert first.last_boost_timestamp == 1000.0
        assert cooling is None
        assert after_cooldown is not None
        assert after_cooldown.memory_coefficient == pytest.approx(0.9)

    def test_legacy_memories_are_backfilled_from_creation_time(self):
        """版本 3 数据升级时应以创建时间初始化上次衰减时间。"""
        connection = sqlite3.connect(":memory:")
        connection.row_factory = sqlite3.Row
        connection.executescript(
            """
            CREATE TABLE memories (
                id TEXT PRIMARY KEY,
                owner_id INTEGER NOT NULL,
                content TEXT NOT NULL,
                timestamp REAL NOT NULL,
                memory_coefficient REAL NOT NULL,
                semantic_timestamp REAL NOT NULL DEFAULT 0,
                memory_type TEXT NOT NULL DEFAULT 'normal'
            );
            CREATE TABLE memory_schema_migrations (
                version INTEGER PRIMARY KEY,
                applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            INSERT INTO memory_schema_migrations (version) VALUES (1), (2), (3);
            INSERT INTO memories (
                id, owner_id, content, timestamp, memory_coefficient
            ) VALUES ('legacy-memory', 1, '历史记忆', 1234.0, 0.8);
            """
        )

        try:
            run_memory_migrations(connection)
            row = connection.execute(
                "SELECT last_decay_timestamp FROM memories WHERE id = 'legacy-memory'"
            ).fetchone()
        finally:
            connection.close()

        assert row is not None
        assert row["last_decay_timestamp"] == 1234.0

    def test_shared_connection_serializes_concurrent_writes(self, tmp_path):
        """多个 Agent 线程共享 SQLite connection 时应完整写入所有记忆。"""
        database = MemoryDB(MemoryConfig(memory_dir=str(tmp_path)))
        errors = []

        def write_one(index: int) -> None:
            """
            在单独线程中写入一条记忆。

            Args:
                index: 用于构造唯一记忆 ID 的序号。

            Returns:
                None: 写入成功或异常已收集后返回。
            """
            try:
                database._add_memory_sync(MemoryChunk(
                    id=f"thread-memory-{index}",
                    owner_id=1,
                    content=f"并发记忆 {index}",
                    timestamp=1000.0 + index,
                    memory_coefficient=0.8,
                    last_decay_timestamp=1000.0 + index,
                ))
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=write_one, args=(index,)) for index in range(8)]
        try:
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join(timeout=5)
            memories = database._get_all_memories_sync()
        finally:
            database.close()

        assert errors == []
        assert len(memories) == 8
