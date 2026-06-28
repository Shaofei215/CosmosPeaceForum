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
    async def test_relevance_precedes_memory_coefficient(self):
        """记忆重要度只能打破同分，不能覆盖 RRF 相关性顺序。"""
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
            [("relevant", 0.03), ("important", 0.02)],
            lambda _: True,
        )

        assert [chunk.id for chunk in memories] == ["relevant", "important"]


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

    def test_reload_config_rebuilds_embedding_model(self):
        """新的 Embedding 端点和模型应立即应用到已存在服务。"""
        service = MemoryService.__new__(MemoryService)
        service._config_lock = threading.RLock()
        service.config = MemoryConfig(
            embedding_base_url="https://old.example/v1",
            embedding_model_name="old-model",
        )
        service.embedding_model = MagicMock()
        new_config = MemoryConfig(
            embedding_base_url="https://new.example/v1",
            embedding_model_name="new-model",
        )

        service.reload_config(new_config)

        assert service.config is new_config
        assert service.embedding_model.base_url == "https://new.example/v1"
        assert service.embedding_model.model_name == "new-model"


class TestVectorMetadataFiltering:
    """验证 Chroma 在召回候选前应用业务元数据过滤。"""

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
