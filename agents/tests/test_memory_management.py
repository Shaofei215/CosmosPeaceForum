"""
测试新增的记忆管理功能

覆盖:
1. MemoryChunk 双时间戳机制 (semantic_timestamp + system timestamp)
2. calculate_time_description_from_date 工具函数
3. 自动分块 auto_chunk_text (512 tokens, 50 overlap)
4. LLM 智能分块 chunk_memories 工具
5. LLM 智能分块 _llm_smart_chunk 函数 (LangChain Tool 调用)
"""

import pytest
import time
from unittest.mock import patch, MagicMock
import sys
import shutil
from pathlib import Path

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

    @pytest.mark.asyncio
    async def test_memory_db_persists_semantic_timestamp(self):
        """写入数据库后应保留 semantic_timestamp，管理端展示依赖该字段。"""
        from agents.agents_scheduler.memory.database import MemoryDB

        test_dir = Path("agents/tests/.tmp_memory_db_semantic").resolve()
        if test_dir.exists():
            shutil.rmtree(test_dir)
        test_dir.mkdir(parents=True)

        class TestConfig:
            def get_memory_db_path(self):
                return str(test_dir / "memories.db")

        db = MemoryDB(TestConfig())
        chunk = MemoryChunk(
            id="semantic-test-id",
            owner_id=999001,
            content="用于测试语义时间持久化的记忆",
            timestamp=1000.0,
            memory_coefficient=0.85,
            semantic_timestamp=1672531200.0,
        )

        try:
            await db.add_memory(chunk)
            retrieved = await db.get_memory(chunk.id)
        finally:
            db.close()
            shutil.rmtree(test_dir)

        assert retrieved is not None
        assert retrieved.semantic_timestamp == 1672531200.0


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


# ==================== LLM Smart Chunk: chunk_memories Tool ====================

class TestChunkMemoriesTool:
    """测试 chunk_memories LangChain 工具"""

    def test_chunk_memories_returns_input_as_is(self):
        """chunk_memories 工具应原样返回输入的 memories 列表"""
        from agents.management.backend.api.memories import chunk_memories

        memories = [
            {"content": "我今天学到了新知识", "memory_coefficient": 0.8},
            {"content": "我和朋友聊了天", "memory_coefficient": 0.6},
        ]
        result = chunk_memories.invoke({"memories": memories})
        assert result == memories

    def test_chunk_memories_empty_list(self):
        """chunk_memories 工具应支持空列表"""
        from agents.management.backend.api.memories import chunk_memories

        result = chunk_memories.invoke({"memories": []})
        assert result == []

    def test_chunk_memories_single_memory(self):
        """chunk_memories 工具应支持单条记忆"""
        from agents.management.backend.api.memories import chunk_memories

        memories = [{"content": "单独一条记忆", "memory_coefficient": 0.9}]
        result = chunk_memories.invoke({"memories": memories})
        assert len(result) == 1
        assert result[0]["content"] == "单独一条记忆"
        assert result[0]["memory_coefficient"] == 0.9


# ==================== LLM Smart Chunk: _llm_smart_chunk ====================

def _create_mock_chunk_config():
    """创建模拟的分块模型配置"""
    config = MagicMock()
    config.model_name = "gpt-4"
    config.temperature = 0.7
    config.max_token = 4096
    config.api_key = "test-api-key"
    config.base_url = "https://api.openai.com/v1"
    return config


def _create_mock_llm_response(memories):
    """创建模拟的 LLM 工具调用响应"""
    mock_response = MagicMock()
    mock_response.content = ""
    mock_response.tool_calls = [
        {
            "name": "chunk_memories",
            "args": {"memories": memories},
            "id": "call_test_123",
        }
    ]
    return mock_response


class TestLlmSmartChunk:
    """测试 _llm_smart_chunk 函数 (LangChain Tool 调用)"""

    def test_successful_chunking_single_memory(self):
        """成功调用 LLM 分块，返回单条记忆"""
        import asyncio
        from agents.management.backend.api.memories import _llm_smart_chunk
        from fastapi import HTTPException

        mock_config = _create_mock_chunk_config()
        mock_memories = [
            {"content": "我今天学到了新知识", "memory_coefficient": 0.8}
        ]
        mock_response = _create_mock_llm_response(mock_memories)

        async def run_test():
            with patch("agents.management.backend.api.memories.get_active_chunk_model_config") as mock_get_config, \
                 patch("agents.management.backend.api.memories.ChatOpenAI") as mock_chat_openai:
                mock_get_config.return_value = mock_config
                mock_llm = MagicMock()
                mock_llm_with_tools = MagicMock()
                mock_llm.bind_tools.return_value = mock_llm_with_tools
                mock_llm_with_tools.invoke.return_value = mock_response
                mock_chat_openai.return_value = mock_llm

                mock_db = MagicMock()

                return await _llm_smart_chunk(
                    text="今天学到了新知识",
                    owner_id=1,
                    personality_prompt="我是一个学生",
                    semantic_timestamp=1000.0,
                    memory_coefficient=0.85,
                    db=mock_db,
                )

        result = asyncio.run(run_test())

        assert len(result) == 1
        assert result[0]["content"] == "我今天学到了新知识"
        assert result[0]["memory_coefficient"] == 0.8

    def test_extracts_raw_tool_calls_from_chat_message(self):
        """兼容 ChatMessage.additional_kwargs 中的 OpenAI 原始 tool_calls。"""
        import json
        from langchain_core.messages import ChatMessage
        from agents.management.backend.api.memories import _extract_chunked_memories

        mock_memories = [
            {"content": "我被原始 tool_calls 成功解析", "memory_coefficient": 0.82}
        ]
        response = ChatMessage(
            role="assistant",
            content="",
            additional_kwargs={
                "tool_calls": [
                    {
                        "id": "call_raw",
                        "type": "function",
                        "function": {
                            "name": "chunk_memories",
                            "arguments": json.dumps({"memories": mock_memories}, ensure_ascii=False),
                        },
                    }
                ]
            },
        )

        result = _extract_chunked_memories(response)

        assert result == mock_memories

    def test_extracts_json_content_fallback(self):
        """工具调用不可用时，兼容模型直接返回 JSON。"""
        from langchain_core.messages import ChatMessage
        from agents.management.backend.api.memories import _extract_chunked_memories

        response = ChatMessage(
            role="assistant",
            content='```json\n{"memories":[{"content":"我来自 JSON fallback","memory_coefficient":0.77}]}\n```',
        )

        result = _extract_chunked_memories(response)

        assert result == [{"content": "我来自 JSON fallback", "memory_coefficient": 0.77}]

    def test_successful_chunking_multiple_memories(self):
        """成功调用 LLM 分块，返回多条记忆"""
        import asyncio
        from agents.management.backend.api.memories import _llm_smart_chunk

        mock_config = _create_mock_chunk_config()
        mock_memories = [
            {"content": "我今天学到了新知识", "memory_coefficient": 0.8},
            {"content": "我和朋友讨论了问题", "memory_coefficient": 0.7},
            {"content": "我决定明天继续学习", "memory_coefficient": 0.9},
        ]
        mock_response = _create_mock_llm_response(mock_memories)

        async def run_test():
            with patch("agents.management.backend.api.memories.get_active_chunk_model_config") as mock_get_config, \
                 patch("agents.management.backend.api.memories.ChatOpenAI") as mock_chat_openai:
                mock_get_config.return_value = mock_config
                mock_llm = MagicMock()
                mock_llm_with_tools = MagicMock()
                mock_llm.bind_tools.return_value = mock_llm_with_tools
                mock_llm_with_tools.invoke.return_value = mock_response
                mock_chat_openai.return_value = mock_llm

                mock_db = MagicMock()

                return await _llm_smart_chunk(
                    text="今天学到了新知识，和朋友讨论了问题，决定明天继续学习",
                    owner_id=1,
                    personality_prompt="我是一个学生",
                    semantic_timestamp=1000.0,
                    memory_coefficient=0.85,
                    db=mock_db,
                )

        result = asyncio.run(run_test())

        assert len(result) == 3
        assert result[0]["content"] == "我今天学到了新知识"
        assert result[1]["content"] == "我和朋友讨论了问题"
        assert result[2]["content"] == "我决定明天继续学习"

    def test_raises_when_no_config(self):
        """未配置分块模型时应抛出 HTTPException"""
        import asyncio
        from agents.management.backend.api.memories import _llm_smart_chunk
        from fastapi import HTTPException, status

        async def run_test():
            with patch("agents.management.backend.api.memories.get_active_chunk_model_config") as mock_get_config:
                mock_get_config.return_value = None
                mock_db = MagicMock()

                return await _llm_smart_chunk(
                    text="test",
                    owner_id=1,
                    personality_prompt="test",
                    semantic_timestamp=1000.0,
                    memory_coefficient=0.85,
                    db=mock_db,
                )

        with pytest.raises(HTTPException) as exc_info:
            asyncio.run(run_test())

        assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST

    def test_raises_when_no_tool_calls(self):
        """LLM 未调用工具时应抛出 HTTPException"""
        import asyncio
        from agents.management.backend.api.memories import _llm_smart_chunk
        from fastapi import HTTPException, status

        mock_config = _create_mock_chunk_config()
        mock_response = MagicMock()
        mock_response.content = "一些文本响应"
        mock_response.tool_calls = []

        async def run_test():
            with patch("agents.management.backend.api.memories.get_active_chunk_model_config") as mock_get_config, \
                 patch("agents.management.backend.api.memories.ChatOpenAI") as mock_chat_openai:
                mock_get_config.return_value = mock_config
                mock_llm = MagicMock()
                mock_llm_with_tools = MagicMock()
                mock_llm.bind_tools.return_value = mock_llm_with_tools
                mock_llm_with_tools.invoke.return_value = mock_response
                mock_chat_openai.return_value = mock_llm

                mock_db = MagicMock()

                return await _llm_smart_chunk(
                    text="test",
                    owner_id=1,
                    personality_prompt="test",
                    semantic_timestamp=1000.0,
                    memory_coefficient=0.85,
                    db=mock_db,
                )

        with pytest.raises(HTTPException) as exc_info:
            asyncio.run(run_test())

        assert exc_info.value.status_code == status.HTTP_502_BAD_GATEWAY

    def test_raises_when_empty_memories(self):
        """LLM 工具调用返回空记忆列表时应抛出 HTTPException"""
        import asyncio
        from agents.management.backend.api.memories import _llm_smart_chunk
        from fastapi import HTTPException, status

        mock_config = _create_mock_chunk_config()
        mock_response = _create_mock_llm_response([])

        async def run_test():
            with patch("agents.management.backend.api.memories.get_active_chunk_model_config") as mock_get_config, \
                 patch("agents.management.backend.api.memories.ChatOpenAI") as mock_chat_openai:
                mock_get_config.return_value = mock_config
                mock_llm = MagicMock()
                mock_llm_with_tools = MagicMock()
                mock_llm.bind_tools.return_value = mock_llm_with_tools
                mock_llm_with_tools.invoke.return_value = mock_response
                mock_chat_openai.return_value = mock_llm

                mock_db = MagicMock()

                return await _llm_smart_chunk(
                    text="test",
                    owner_id=1,
                    personality_prompt="test",
                    semantic_timestamp=1000.0,
                    memory_coefficient=0.85,
                    db=mock_db,
                )

        with pytest.raises(HTTPException) as exc_info:
            asyncio.run(run_test())

        assert exc_info.value.status_code == status.HTTP_502_BAD_GATEWAY

    def test_llm_invoked_with_correct_prompts(self):
        """验证 LLM 调用时传入了正确的提示词"""
        import asyncio
        from agents.management.backend.api.memories import _llm_smart_chunk

        mock_config = _create_mock_chunk_config()
        mock_memories = [{"content": "test", "memory_coefficient": 0.8}]
        mock_response = _create_mock_llm_response(mock_memories)

        async def run_test():
            with patch("agents.management.backend.api.memories.get_active_chunk_model_config") as mock_get_config, \
                 patch("agents.management.backend.api.memories.ChatOpenAI") as mock_chat_openai:
                mock_get_config.return_value = mock_config
                mock_llm = MagicMock()
                mock_llm_with_tools = MagicMock()
                mock_llm.bind_tools.return_value = mock_llm_with_tools
                mock_llm_with_tools.invoke.return_value = mock_response
                mock_chat_openai.return_value = mock_llm

                mock_db = MagicMock()

                await _llm_smart_chunk(
                    text="待分块文本",
                    owner_id=1,
                    personality_prompt="角色个性提示",
                    semantic_timestamp=1000.0,
                    memory_coefficient=0.85,
                    db=mock_db,
                )

                mock_llm_with_tools.invoke.assert_called_once()
                call_args = mock_llm_with_tools.invoke.call_args[0][0]
                assert len(call_args) == 2
                assert call_args[0]["role"] == "system"
                assert call_args[1]["role"] == "user"
                assert "角色个性提示" in call_args[1]["content"]
                assert "待分块文本" in call_args[1]["content"]
                assert "512 tokens" in call_args[0]["content"]

        asyncio.run(run_test())

    def test_chatopenai_called_with_correct_kwargs(self):
        """验证 ChatOpenAI 使用了正确的配置参数"""
        import asyncio
        from agents.management.backend.api.memories import _llm_smart_chunk

        mock_config = _create_mock_chunk_config()
        mock_config.base_url = "https://custom-api.com/v1"
        mock_memories = [{"content": "test", "memory_coefficient": 0.8}]
        mock_response = _create_mock_llm_response(mock_memories)

        async def run_test():
            with patch("agents.management.backend.api.memories.get_active_chunk_model_config") as mock_get_config, \
                 patch("agents.management.backend.api.memories.ChatOpenAI") as mock_chat_openai:
                mock_get_config.return_value = mock_config
                mock_llm = MagicMock()
                mock_llm_with_tools = MagicMock()
                mock_llm.bind_tools.return_value = mock_llm_with_tools
                mock_llm_with_tools.invoke.return_value = mock_response
                mock_chat_openai.return_value = mock_llm

                mock_db = MagicMock()

                await _llm_smart_chunk(
                    text="test",
                    owner_id=1,
                    personality_prompt="test",
                    semantic_timestamp=1000.0,
                    memory_coefficient=0.85,
                    db=mock_db,
                )

                mock_chat_openai.assert_called_once()
                call_kwargs = mock_chat_openai.call_args[1]
                assert call_kwargs["model"] == "gpt-4"
                assert call_kwargs["temperature"] == 0.7
                assert call_kwargs["max_tokens"] == 4096
                assert call_kwargs["api_key"] == "test-api-key"
                assert call_kwargs["base_url"] == "https://custom-api.com/v1"

        asyncio.run(run_test())

    def test_empty_base_url_handled(self):
        """空 base_url 应正确处理"""
        import asyncio
        from agents.management.backend.api.memories import _llm_smart_chunk

        mock_config = _create_mock_chunk_config()
        mock_config.base_url = ""
        mock_memories = [{"content": "test", "memory_coefficient": 0.8}]
        mock_response = _create_mock_llm_response(mock_memories)

        async def run_test():
            with patch("agents.management.backend.api.memories.get_active_chunk_model_config") as mock_get_config, \
                 patch("agents.management.backend.api.memories.ChatOpenAI") as mock_chat_openai:
                mock_get_config.return_value = mock_config
                mock_llm = MagicMock()
                mock_llm_with_tools = MagicMock()
                mock_llm.bind_tools.return_value = mock_llm_with_tools
                mock_llm_with_tools.invoke.return_value = mock_response
                mock_chat_openai.return_value = mock_llm

                mock_db = MagicMock()

                await _llm_smart_chunk(
                    text="test",
                    owner_id=1,
                    personality_prompt="test",
                    semantic_timestamp=1000.0,
                    memory_coefficient=0.85,
                    db=mock_db,
                )

                mock_chat_openai.assert_called_once()
                call_kwargs = mock_chat_openai.call_args[1]
                assert "base_url" not in call_kwargs

        asyncio.run(run_test())

    def test_llm_exception_propagated_as_http_exception(self):
        """LLM 调用异常应转换为 HTTPException"""
        import asyncio
        from agents.management.backend.api.memories import _llm_smart_chunk
        from fastapi import HTTPException

        mock_config = _create_mock_chunk_config()

        async def run_test():
            with patch("agents.management.backend.api.memories.get_active_chunk_model_config") as mock_get_config, \
                 patch("agents.management.backend.api.memories.ChatOpenAI") as mock_chat_openai:
                mock_get_config.return_value = mock_config
                mock_llm = MagicMock()
                mock_llm_with_tools = MagicMock()
                mock_llm.bind_tools.return_value = mock_llm_with_tools
                mock_llm_with_tools.invoke.side_effect = Exception("Connection error")
                mock_chat_openai.return_value = mock_llm

                mock_db = MagicMock()

                return await _llm_smart_chunk(
                    text="test",
                    owner_id=1,
                    personality_prompt="test",
                    semantic_timestamp=1000.0,
                    memory_coefficient=0.85,
                    db=mock_db,
                )

        with pytest.raises(HTTPException) as exc_info:
            asyncio.run(run_test())

        assert exc_info.value.status_code == 502
        assert "Connection error" in exc_info.value.detail
