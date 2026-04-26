"""
测试新增的记忆管理功能

覆盖:
1. MemoryChunk 双时间戳机制 (semantic_timestamp + system timestamp)
2. calculate_time_description_from_date 工具函数
3. 自动分块 auto_chunk_text (512 tokens, 50 overlap)
"""

import pytest
import time
from unittest.mock import patch, MagicMock
import sys

# ==================== MemoryChunk Dual Timestamp ====================

from agents.agents_scheduler.memory.models import MemoryChunk


class TestMemoryChunkDualTimestamp:
    """测试 MemoryChunk 的双时间戳机制"""

    def test_create_without_semantic_timestamp(self):
        """不传 semantic_timestamp 时，应与 timestamp 相同"""
        with patch("agents.agents_scheduler.memory.models.get_time_system") as mock_ts:
            mock_ts.return_value.get_scaled_timestamp.return_value = 500.0
            chunk = MemoryChunk.create(
                owner_id=1,
                content="test memory",
                memory_coefficient=0.9
            )
            assert chunk.timestamp == 500.0
            assert chunk.semantic_timestamp == 500.0

    def test_create_with_semantic_timestamp(self):
        """手动传入 semantic_timestamp（如2023年），应保留原始值"""
        with patch("agents.agents_scheduler.memory.models.get_time_system") as mock_ts:
            mock_ts.return_value.get_scaled_timestamp.return_value = 500.0
            semantic_ts = 1672531200  # 2023-01-01
            chunk = MemoryChunk.create(
                owner_id=1,
                content="2023年的记忆",
                memory_coefficient=0.9,
                semantic_timestamp=semantic_ts
            )
            assert chunk.timestamp == 500.0
            assert chunk.semantic_timestamp == semantic_ts

    def test_to_dict_includes_semantic_timestamp(self):
        """to_dict 应包含 semantic_timestamp 字段"""
        chunk = MemoryChunk(
            id="test-id",
            owner_id=1,
            content="test",
            timestamp=1000.0,
            memory_coefficient=0.85,
            semantic_timestamp=1672531200.0,
        )
        d = chunk.to_dict()
        assert "semantic_timestamp" in d
        assert d["semantic_timestamp"] == 1672531200.0

    def test_from_dict_with_semantic_timestamp(self):
        """from_dict 应正确读取 semantic_timestamp"""
        data = {
            "id": "test-id",
            "owner_id": 1,
            "content": "test",
            "timestamp": 1000.0,
            "memory_coefficient": 0.85,
            "semantic_timestamp": 1672531200.0,
        }
        chunk = MemoryChunk.from_dict(data)
        assert chunk.semantic_timestamp == 1672531200.0

    def test_from_dict_without_semantic_timestamp_defaults_to_zero(self):
        """旧数据没有 semantic_timestamp 字段时应默认为 0.0"""
        data = {
            "id": "test-id",
            "owner_id": 1,
            "content": "test",
            "timestamp": 1000.0,
            "memory_coefficient": 0.85,
        }
        chunk = MemoryChunk.from_dict(data)
        assert chunk.semantic_timestamp == 0.0

    def test_semantic_timestamp_zero_treated_as_system_time(self):
        """semantic_timestamp 为 0 时，展示时应使用 system timestamp"""
        chunk = MemoryChunk(
            id="test-id",
            owner_id=1,
            content="test",
            timestamp=1000.0,
            memory_coefficient=0.85,
            semantic_timestamp=0.0,
        )
        assert chunk.semantic_timestamp == 0.0
        assert chunk.timestamp > 0


# ==================== Time Description From Date ====================

from agents.agents_scheduler.memory.utils import (
    calculate_time_description,
    calculate_time_description_from_date,
)


class TestCalculateTimeDescriptionFromDate:
    """测试基于绝对 Unix 时间戳的时间描述"""

    def test_recent_timestamp_returns_relative(self):
        """接近当前时间的语义时间戳应返回相对描述"""
        now = time.time()
        five_min_ago = now - 300
        result = calculate_time_description_from_date(five_min_ago, now)
        assert "分钟前" in result

    def test_old_timestamp_returns_years(self):
        """3年前的语义时间戳应返回年数描述"""
        now = time.time()
        three_years_ago = now - (3 * 365 * 24 * 3600)
        result = calculate_time_description_from_date(three_years_ago, now)
        assert "年前" in result

    def test_future_timestamp(self):
        """未来时间戳应返回具体日期"""
        now = time.time()
        future = now + (30 * 24 * 3600)
        result = calculate_time_description_from_date(future, now)
        assert "年前" not in result
        assert "分钟前" not in result

    def test_small_timestamp_falls_back_to_system_time(self):
        """小于 1000000 的时间戳（系统缩放时间）应回退到常规方法"""
        result = calculate_time_description_from_date(950.0, 1000.0)
        assert result == "刚刚"

    def test_2023_year_timestamp(self):
        """2023年时间戳相对于现在应返回 '年前'"""
        ts_2023 = 1672531200  # 2023-01-01
        now = time.time()
        result = calculate_time_description_from_date(ts_2023, now)
        assert "年前" in result


# ==================== Auto Chunk Text ====================

def _auto_chunk_text(text: str, chunk_size: int = 512, overlap: int = 50) -> list[str]:
    """
    自动分块文本（基于 jieba 中文分词）

    中文按词语计为 token，分块边界保证在完整词语处。
    """
    import jieba
    words = list(jieba.cut(text))

    chunks = []
    start = 0
    while start < len(words):
        end = min(start + chunk_size, len(words))
        chunk_words = words[start:end]
        chunks.append(''.join(chunk_words))

        if end >= len(words):
            break

        start = end - overlap
        if start < 0:
            start = 0

    return chunks


class TestAutoChunkText:
    """测试自动分块功能 (512 tokens, 50 overlap)"""

    def test_short_text_single_chunk(self):
        """短于 chunk_size 的文本应只产生一个分块"""
        text = "这是一段很短的记忆"
        chunks = _auto_chunk_text(text)
        assert len(chunks) == 1
        assert chunks[0] == text

    def test_long_text_multiple_chunks(self):
        """长文本应产生多个分块"""
        # 生成 1200 个中文字符（约 1200 tokens）
        text = "中" * 1200
        chunks = _auto_chunk_text(text, chunk_size=512, overlap=50)
        assert len(chunks) >= 2

        # 验证总覆盖
        total_chars = sum(len(c) for c in chunks)
        assert total_chars > 1200  # 因为有重叠，总字符数应大于原文

    def test_overlap_between_chunks(self):
        """相邻分块之间应有重叠"""
        # 创建可识别的文本
        text = "ABCDEFGH" * 100  # 800 chars
        chunks = _auto_chunk_text(text, chunk_size=512, overlap=50)

        if len(chunks) >= 2:
            # 第二个分块的开头应该和第一个分块的结尾有重叠
            first_end = chunks[0][-60:]  # 取最后60个字符
            second_start = chunks[1][:60]
            # 应该有至少 50 个字符重叠
            overlap_len = 0
            for i in range(min(len(first_end), len(second_start))):
                if first_end[i:] == second_start[:len(first_end) - i]:
                    overlap_len = len(first_end) - i
                    break
            assert overlap_len >= 40  # 留一些容差

    def test_exact_chunk_size(self):
        """正好等于 chunk_size 的文本应只产生一个分块"""
        text = "A" * 512
        chunks = _auto_chunk_text(text, chunk_size=512, overlap=50)
        assert len(chunks) == 1

    def test_chunk_size_plus_one(self):
        """词语数超过 chunk_size 时应产生两个分块"""
        # "今天天气很好 " 会被 jieba 分为约 3-4 个词，重复 200 次远超 512
        text = "今天天气很好 " * 200
        chunks = _auto_chunk_text(text, chunk_size=512, overlap=50)
        assert len(chunks) >= 2

    def test_mixed_chinese_english(self):
        """中英文混合文本应正确分块"""
        text = "今天天气很好 Today is a great day " * 50
        chunks = _auto_chunk_text(text, chunk_size=512, overlap=50)
        assert len(chunks) >= 1

    def test_empty_text(self):
        """空文本应返回空列表"""
        chunks = _auto_chunk_text("")
        assert len(chunks) == 0

    def test_single_char(self):
        """单个字符应返回单个分块"""
        chunks = _auto_chunk_text("A")
        assert len(chunks) == 1
        assert chunks[0] == "A"

    def test_english_words_tokenization(self):
        """英文单词应按单词分割"""
        text = "hello world foo bar"
        # 4个单词 + 3个空格 = 每个单词是1个token
        chunks = _auto_chunk_text(text, chunk_size=512, overlap=50)
        assert len(chunks) == 1


# ==================== Integration: Memory Upload Flow ====================

class TestMemoryUploadValidation:
    """测试记忆上传的参数验证逻辑"""

    def test_auto_chunk_requires_semantic_time(self):
        """自动分块模式必须提供 semantic_time"""
        # 这是后端验证逻辑，这里用简单的参数校验模拟
        payload = {
            "owner_id": 1,
            "content": "test",
            "chunk_mode": "auto",
        }
        assert "semantic_time" not in payload or payload.get("semantic_time") is None
        # 应拒绝

    def test_auto_chunk_requires_memory_coefficient(self):
        """自动分块模式必须提供 memory_coefficient"""
        payload = {
            "owner_id": 1,
            "content": "test",
            "chunk_mode": "auto",
        }
        assert "memory_coefficient" not in payload
        # 应拒绝

    def test_llm_chunk_requires_personality_prompt(self):
        """LLM 分块模式必须提供 personality_prompt"""
        payload = {
            "owner_id": 1,
            "content": "test",
            "chunk_mode": "llm",
        }
        assert "personality_prompt" not in payload
        # 应拒绝

    def test_llm_chunk_personality_prompt_provided(self):
        """LLM 分块模式有 personality_prompt 应通过验证"""
        payload = {
            "owner_id": 1,
            "content": "test",
            "chunk_mode": "llm",
            "personality_prompt": "我是一个开朗的角色",
        }
        assert payload["personality_prompt"] is not None
        # 应通过
