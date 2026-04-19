import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime

from agents.agents_scheduler.langgraph.nodes import (
    TOOL_TO_LOCATION,
    TOOLS_WITH_RETURN_VALUE,
    TOOL_NO_RETURN_VALUE,
    _get_location_after_tool,
    parse_tool_calls,
    _normalize_tool_calls_for_batch,
    start_node,
    recall_memory_node,
    tool_execution_node,
    should_continue_edge,
    end_node,
)
from agents.agents_scheduler.langgraph.state import ExitReason


class TestToolLocationMapping:
    def test_get_location_after_tool_known(self):
        assert _get_location_after_tool("get_global_feed") == "主页（信息流）"
        assert _get_location_after_tool("expand_post") == "帖子详情页"
        assert _get_location_after_tool("expand_comments") == "评论页"
        assert _get_location_after_tool("get_user_profile") == "用户主页"

    def test_get_location_after_tool_unknown(self):
        assert _get_location_after_tool("unknown_tool") is None
        assert _get_location_after_tool("logout") is None
        assert _get_location_after_tool("toggle_post_like") is None

    def test_get_location_after_tool_case_insensitive(self):
        assert _get_location_after_tool("Get_Global_Feed") == "主页（信息流）"
        assert _get_location_after_tool("GET_GLOBAL_FEED") == "主页（信息流）"

    def test_tools_with_return_value(self):
        assert "get_profile" in TOOLS_WITH_RETURN_VALUE
        assert "get_global_feed" in TOOLS_WITH_RETURN_VALUE
        assert "logout" not in TOOLS_WITH_RETURN_VALUE

    def test_tools_no_return_value(self):
        assert "logout" in TOOL_NO_RETURN_VALUE
        assert "toggle_post_like" in TOOL_NO_RETURN_VALUE
        assert "get_global_feed" not in TOOL_NO_RETURN_VALUE


class TestParseToolCalls:
    def test_parse_tool_calls_empty(self):
        response = MagicMock()
        response.tool_calls = None
        assert parse_tool_calls(response) == []

    def test_parse_tool_calls_no_attribute(self):
        response = MagicMock(spec=[])
        assert parse_tool_calls(response) == []

    def test_parse_tool_calls_single(self):
        response = MagicMock()
        response.tool_calls = [
            {"name": "get_global_feed", "args": {"reason": "test"}}
        ]
        result = parse_tool_calls(response)
        assert len(result) == 1
        assert result[0]["name"] == "get_global_feed"
        assert result[0]["args"] == {"reason": "test"}

    def test_parse_tool_calls_multiple(self):
        response = MagicMock()
        response.tool_calls = [
            {"name": "toggle_post_like", "args": {"post_id": 1}},
            {"name": "get_global_feed", "args": {"reason": "test"}},
        ]
        result = parse_tool_calls(response)
        assert len(result) == 2
        assert result[0]["name"] == "toggle_post_like"
        assert result[1]["name"] == "get_global_feed"


class TestNormalizeToolCallsForBatch:
    def test_normalize_single_tool(self):
        tool_calls = [{"name": "get_global_feed", "args": {}}]
        result = _normalize_tool_calls_for_batch(tool_calls)
        assert len(result) == 1

    def test_normalize_multiple_return_value_tools(self):
        tool_calls = [
            {"name": "get_global_feed", "args": {}},
            {"name": "get_user_profile", "args": {"user_id": 1}},
            {"name": "toggle_post_like", "args": {"post_id": 1}},
        ]
        result = _normalize_tool_calls_for_batch(tool_calls)
        return_value_tools = [tc for tc in result if tc["name"].lower() in TOOLS_WITH_RETURN_VALUE]
        assert len(return_value_tools) == 1

    def test_normalize_no_return_value_tools_all_kept(self):
        tool_calls = [
            {"name": "toggle_post_like", "args": {"post_id": 1}},
            {"name": "toggle_follow", "args": {"user_id": 2}},
        ]
        result = _normalize_tool_calls_for_batch(tool_calls)
        assert len(result) == 2

    def test_normalize_mixed_tools(self):
        tool_calls = [
            {"name": "get_global_feed", "args": {}},
            {"name": "toggle_post_like", "args": {"post_id": 1}},
            {"name": "get_user_profile", "args": {"user_id": 1}},
        ]
        result = _normalize_tool_calls_for_batch(tool_calls)
        return_value_tools = [tc for tc in result if tc["name"].lower() in TOOLS_WITH_RETURN_VALUE]
        no_return_tools = [tc for tc in result if tc["name"].lower() in TOOL_NO_RETURN_VALUE]
        assert len(return_value_tools) == 1
        assert len(no_return_tools) == 1


class TestStartNode:
    def test_start_node_resets_state(self):
        state = {
            "username": "test_user",
            "step_count": 5,
            "exit_reason": ExitReason.USER_CHOICE,
            "action_history": [{"step": 1, "timestamp": "2024-01-01", "summary": "s", "action": "a", "reason": "r"}],
            "current_location": "帖子详情页",
            "last_tool_result": {"data": "test"},
            "pending_tool": {"tool_name": "test", "args": {}},
            "pending_tools": [{"name": "test2", "args": {}}],
            "last_error": "some error",
            "summary": "old summary",
            "recalled_memories": "old memories",
        }
        result = start_node(state)
        assert result["step_count"] == 0
        assert result["exit_reason"] is None
        assert result["action_history"] == []
        assert result["current_location"] == "主页（信息流）"
        assert result["last_tool_result"] is None
        assert result["pending_tool"] is None
        assert result["pending_tools"] is None
        assert result["last_error"] is None
        assert result["summary"] is None
        assert result["recalled_memories"] == ""

    def test_start_node_preserves_identity(self):
        state = {
            "username": "test_user",
            "user_id": 42,
            "name": "Test",
            "ai_config_id": 1,
            "personality_prompt": "prompt",
            "personal_signature": "sig",
            "step_count": 5,
            "max_steps": 10,
            "exit_reason": None,
            "action_history": [],
            "current_location": "主页",
            "last_tool_result": None,
            "pending_tool": None,
            "pending_tools": None,
            "last_error": None,
            "summary": None,
            "recalled_memories": "",
        }
        result = start_node(state)
        assert result["username"] == "test_user"
        assert result["user_id"] == 42
        assert result["name"] == "Test"
        assert result["ai_config_id"] == 1


class TestRecallMemoryNode:
    def test_recall_memory_node_disabled(self):
        state = {
            "user_id": 1,
            "username": "test_user",
        }
        with patch("agents.agents_scheduler.langgraph.nodes.get_memory_config") as mock_config:
            mock_config.return_value = MagicMock(memory_enabled=False)
            result = recall_memory_node(state)
            assert result is state

    def test_recall_memory_node_no_user_id(self):
        state = {
            "user_id": None,
            "username": "test_user",
        }
        with patch("agents.agents_scheduler.langgraph.nodes.get_memory_config") as mock_config:
            mock_config.return_value = MagicMock(memory_enabled=True)
            result = recall_memory_node(state)
            assert result is state


class TestToolExecutionNode:
    def test_tool_execution_node_no_pending(self):
        state = {
            "username": "test_user",
            "step_count": 0,
            "pending_tool": None,
            "pending_tools": None,
        }
        result = tool_execution_node(state)
        assert result["step_count"] == 1

    def test_tool_execution_node_logout(self):
        state = {
            "username": "test_user",
            "step_count": 5,
            "pending_tool": {"tool_name": "logout", "args": {"reason": "主动结束会话"}},
            "pending_tools": None,
        }
        result = tool_execution_node(state)
        assert result["exit_reason"] == ExitReason.USER_CHOICE
        assert result["pending_tool"] is None
        assert result["pending_tools"] is None

    def test_tool_execution_node_pending_tools_next(self):
        state = {
            "username": "test_user",
            "step_count": 0,
            "pending_tool": None,
            "pending_tools": [{"name": "get_global_feed", "args": {"reason": "test"}}],
        }
        result = tool_execution_node(state)
        assert result["pending_tool"]["tool_name"] == "get_global_feed"
        # Code sets remaining_tools to None when empty
        assert result["pending_tools"] is None

    def test_tool_execution_node_unknown_tool(self):
        state = {
            "username": "test_user",
            "step_count": 0,
            "max_steps": 10,
            "exit_reason": None,
            "action_history": [],
            "current_location": "主页（信息流）",
            "last_tool_result": None,
            "pending_tool": {"tool_name": "nonexistent_tool", "args": {"reason": "test", "summary": "test"}},
            "pending_tools": None,
            "last_error": None,
            "summary": None,
            "recalled_memories": "",
        }
        with patch("agents.agents_scheduler.langgraph.nodes.get_social_tools") as mock_tools:
            mock_tools.return_value = []
            result = tool_execution_node(state)
            assert result["last_error"] is None


class TestShouldContinueEdge:
    def test_should_continue_with_exit_reason(self):
        state = {
            "username": "test_user",
            "step_count": 5,
            "max_steps": 10,
            "exit_reason": ExitReason.USER_CHOICE,
            "pending_tools": None,
        }
        assert should_continue_edge(state) == "summarize"

    def test_should_continue_with_pending_tools(self):
        state = {
            "username": "test_user",
            "step_count": 5,
            "max_steps": 10,
            "exit_reason": None,
            "pending_tools": [{"name": "test", "args": {}}],
        }
        assert should_continue_edge(state) == "tool_execution"

    def test_should_continue_max_steps(self):
        state = {
            "username": "test_user",
            "step_count": 10,
            "max_steps": 10,
            "exit_reason": None,
            "pending_tools": None,
        }
        assert should_continue_edge(state) == "summarize"

    def test_should_continue_recall_memory(self):
        state = {
            "username": "test_user",
            "step_count": 3,
            "max_steps": 10,
            "exit_reason": None,
            "pending_tools": None,
        }
        assert should_continue_edge(state) == "recall_memory"


class TestEndNode:
    def test_end_node_returns_state_unchanged(self):
        state = {
            "username": "test_user",
            "step_count": 5,
            "summary": "Test summary",
        }
        result = end_node(state)
        assert result is state
