import pytest
from unittest.mock import patch, MagicMock
import sys

from agents.agents_scheduler.memory.utils import calculate_time_description
from agents.agents_scheduler.memory.models import MemoryChunk
from agents.agents_scheduler.memory.chinese_tokenizer import tokenize_chinese, tokenize_query


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
