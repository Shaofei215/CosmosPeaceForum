import pytest
from unittest.mock import patch, MagicMock, AsyncMock

from agents.agents_scheduler.langgraph.tools.memory import (
    format_merged_recall_memory_result,
    merge_recall_memory_result,
    recall_memory,
    write_memory,
)


class TestRecallMemory:
    @patch("agents.agents_scheduler.langgraph.tools.memory.get_current_user_id")
    @patch("agents.agents_scheduler.langgraph.tools.memory.get_memory_config")
    def test_recall_memory_disabled(self, mock_config, mock_user_id):
        mock_user_id.return_value = 1
        mock_config.return_value = MagicMock(memory_enabled=False)

        result = recall_memory.invoke({"query": "银狼"})

        assert result["action"] == "记忆系统未启用，无法回想"
        assert result["data"]["memories"] == []

    @patch("agents.agents_scheduler.langgraph.tools.memory.get_time_system")
    @patch("agents.agents_scheduler.langgraph.tools.memory.get_current_user_id")
    @patch("agents.agents_scheduler.langgraph.tools.memory.get_memory_config")
    @patch("agents.agents_scheduler.langgraph.tools.memory.get_memory_service")
    def test_recall_memory_success(self, mock_service, mock_config, mock_user_id, mock_time_system):
        mock_user_id.return_value = 1
        mock_config.return_value = MagicMock(memory_enabled=True, recall_limit=5)
        mock_time_system.return_value.get_scaled_timestamp.return_value = 1000.0

        chunk = MagicMock()
        chunk.id = "mem-id-1"
        chunk.content = "我之前关注过银狼的技术帖。"
        chunk.memory_coefficient = 0.9

        mock_service_instance = MagicMock()
        mock_service_instance.recall_memories = AsyncMock(return_value=[(chunk, "刚刚")])
        mock_service.return_value = mock_service_instance

        result = recall_memory.invoke({"query": "银狼 技术帖"})

        assert result["action"] == "回想了与「银狼 技术帖」相关的1条记忆"
        assert result["data"]["query"] == "银狼 技术帖"
        assert result["data"]["total"] == 1
        assert result["data"]["memories"][0]["content"] == "我之前关注过银狼的技术帖。"
        mock_service_instance.recall_memories.assert_called_once_with(
            owner_id=1,
            context="银狼 技术帖",
            current_time=1000.0,
            limit=5,
        )

    def test_recall_memory_tool_name(self):
        assert recall_memory.name == "recall_memory"


class TestRecallMemoryResultHelpers:
    def test_merge_recall_memory_result_wraps_previous_result(self):
        previous = {"post": {"id": 1, "content": "hello"}}
        recall = {"query": "hello", "memories": [{"content": "old hello"}], "total": 1}

        result = merge_recall_memory_result(previous, recall)

        assert result["current_view"] == previous
        assert result["explicit_recalls"] == [recall]

    def test_merge_recall_memory_result_keeps_existing_recalls(self):
        previous = {
            "current_view": {"post": {"id": 1}},
            "explicit_recalls": [{"query": "first", "memories": [], "total": 0}],
        }
        recall = {"query": "second", "memories": [], "total": 0}

        result = merge_recall_memory_result(previous, recall)

        assert result["current_view"] == {"post": {"id": 1}}
        assert [item["query"] for item in result["explicit_recalls"]] == ["first", "second"]

    def test_format_merged_recall_memory_result(self):
        result = {
            "current_view": {"post": {"id": 1}},
            "explicit_recalls": [
                {
                    "query": "hello",
                    "memories": [{"content": "old hello", "time_description": "刚刚"}],
                    "total": 1,
                }
            ],
        }

        formatted = format_merged_recall_memory_result(
            result,
            lambda current_view: f"view={current_view['post']['id']}",
        )

        assert "view=1" in formatted
        assert "主动回想" in formatted
        assert "old hello" in formatted


class TestWriteMemory:
    @patch("agents.agents_scheduler.langgraph.tools.memory.get_current_user_id")
    @patch("agents.agents_scheduler.langgraph.tools.memory.get_memory_config")
    def test_write_memory_disabled(self, mock_config, mock_user_id):
        mock_user_id.return_value = 1
        mock_config.return_value = MagicMock(memory_enabled=False)

        result = write_memory.invoke({"memories": [{"content": "test", "memory_coefficient": 0.85}]})
        assert result["action"] == "记忆系统未启用，无法写入"
        assert result["data"]["memory_ids"] == []

    @patch("agents.agents_scheduler.langgraph.tools.memory.get_current_user_id")
    @patch("agents.agents_scheduler.langgraph.tools.memory.get_memory_config")
    @patch("agents.agents_scheduler.langgraph.tools.memory.get_memory_service")
    def test_write_memory_success_single(self, mock_service, mock_config, mock_user_id):
        mock_user_id.return_value = 1
        mock_config.return_value = MagicMock(memory_enabled=True)
        mock_service_instance = MagicMock()
        mock_service_instance.write_memory = AsyncMock(return_value="mem-id-1")
        mock_service.return_value = mock_service_instance

        result = write_memory.invoke({
            "memories": [{"content": "test memory", "memory_coefficient": 0.85}]
        })

        assert result["action"] == "将1条记忆写入长期记忆库"
        assert result["data"]["memory_ids"] == ["mem-id-1"]
        mock_service_instance.write_memory.assert_called_once()

    @patch("agents.agents_scheduler.langgraph.tools.memory.get_current_user_id")
    @patch("agents.agents_scheduler.langgraph.tools.memory.get_memory_config")
    @patch("agents.agents_scheduler.langgraph.tools.memory.get_memory_service")
    def test_write_memory_success_multiple(self, mock_service, mock_config, mock_user_id):
        mock_user_id.return_value = 1
        mock_config.return_value = MagicMock(memory_enabled=True)
        mock_service_instance = MagicMock()
        mock_service_instance.write_memory = AsyncMock(side_effect=["mem-id-1", "mem-id-2", "mem-id-3"])
        mock_service.return_value = mock_service_instance

        result = write_memory.invoke({
            "memories": [
                {"content": "memory 1", "memory_coefficient": 0.9},
                {"content": "memory 2", "memory_coefficient": 0.8},
                {"content": "memory 3", "memory_coefficient": 0.95},
            ]
        })

        assert result["action"] == "将3条记忆写入长期记忆库"
        assert result["data"]["memory_ids"] == ["mem-id-1", "mem-id-2", "mem-id-3"]
        assert mock_service_instance.write_memory.call_count == 3

    @patch("agents.agents_scheduler.langgraph.tools.memory.get_current_user_id")
    @patch("agents.agents_scheduler.langgraph.tools.memory.get_memory_config")
    @patch("agents.agents_scheduler.langgraph.tools.memory.get_memory_service")
    def test_write_memory_skips_empty_content(self, mock_service, mock_config, mock_user_id):
        mock_user_id.return_value = 1
        mock_config.return_value = MagicMock(memory_enabled=True)
        mock_service_instance = MagicMock()
        mock_service_instance.write_memory = AsyncMock(return_value="mem-id-1")
        mock_service.return_value = mock_service_instance

        result = write_memory.invoke({
            "memories": [
                {"content": "", "memory_coefficient": 0.85},
                {"content": "valid memory", "memory_coefficient": 0.85},
                {"content": "", "memory_coefficient": 0.85},
            ]
        })

        assert result["action"] == "将1条记忆写入长期记忆库"
        assert result["data"]["memory_ids"] == ["mem-id-1"]
        mock_service_instance.write_memory.assert_called_once()

    @patch("agents.agents_scheduler.langgraph.tools.memory.get_current_user_id")
    @patch("agents.agents_scheduler.langgraph.tools.memory.get_memory_config")
    @patch("agents.agents_scheduler.langgraph.tools.memory.get_memory_service")
    def test_write_memory_all_empty_content(self, mock_service, mock_config, mock_user_id):
        mock_user_id.return_value = 1
        mock_config.return_value = MagicMock(memory_enabled=True)
        mock_service_instance = MagicMock()
        mock_service.return_value = mock_service_instance

        result = write_memory.invoke({
            "memories": [
                {"content": "", "memory_coefficient": 0.85},
                {"content": "", "memory_coefficient": 0.85},
            ]
        })

        assert result["action"] == "将0条记忆写入长期记忆库"
        assert result["data"]["memory_ids"] == []
        mock_service_instance.write_memory.assert_not_called()

    @patch("agents.agents_scheduler.langgraph.tools.memory.get_current_user_id")
    @patch("agents.agents_scheduler.langgraph.tools.memory.get_memory_config")
    @patch("agents.agents_scheduler.langgraph.tools.memory.get_memory_service")
    def test_write_memory_exception_handling(self, mock_service, mock_config, mock_user_id):
        mock_user_id.return_value = 1
        mock_config.return_value = MagicMock(memory_enabled=True)
        mock_service_instance = MagicMock()
        mock_service_instance.write_memory = AsyncMock(side_effect=Exception("DB error"))
        mock_service.return_value = mock_service_instance

        result = write_memory.invoke({
            "memories": [{"content": "test", "memory_coefficient": 0.85}]
        })

        assert "记忆写入失败" in result["action"]
        assert result["data"]["memory_ids"] == []

    @patch("agents.agents_scheduler.langgraph.tools.memory.get_current_user_id")
    @patch("agents.agents_scheduler.langgraph.tools.memory.get_memory_config")
    @patch("agents.agents_scheduler.langgraph.tools.memory.get_memory_service")
    def test_write_memory_uses_default_coefficient(self, mock_service, mock_config, mock_user_id):
        mock_user_id.return_value = 1
        mock_config.return_value = MagicMock(memory_enabled=True)
        mock_service_instance = MagicMock()
        mock_service_instance.write_memory = AsyncMock(return_value="mem-id-1")
        mock_service.return_value = mock_service_instance

        write_memory.invoke({
            "memories": [{"content": "test"}]
        })

        call_kwargs = mock_service_instance.write_memory.call_args[1]
        assert call_kwargs["memory_coefficient"] == 0.85

    def test_write_memory_tool_name(self):
        assert write_memory.name == "write_memory"

    def test_write_memory_tool_description(self):
        assert "长期记忆" in write_memory.description
