import pytest
from unittest.mock import patch, MagicMock, AsyncMock

from agents.agents_scheduler.langgraph.tools.memory import write_memory


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
