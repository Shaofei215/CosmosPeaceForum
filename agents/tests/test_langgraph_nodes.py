import pytest
from unittest.mock import AsyncMock, patch, MagicMock
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
    llm_decision_node,
    tool_execution_node,
    should_continue_edge,
    summarize_node,
    end_node,
)
from agents.agents_scheduler.langgraph.state import ExitReason


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

    def test_recall_memory_node_uses_current_context_as_query(self):
        """测试自动召回只使用当前视野和近期操作，不引入固定提示词。"""
        state = {
            "user_id": 1,
            "username": "test_user",
            "name": "Test",
            "personality_prompt": "你是一个测试角色",
            "personal_signature": "测试签名",
            "step_count": 2,
            "max_steps": 10,
            "action_history": [
                {"step": 1, "timestamp": "2024-01-01", "summary": "看到帖子", "action": "浏览了帖子", "reason": "感兴趣"},
            ],
            "current_location": "主页（信息流）",
            "last_tool_result": {
                "action": "查看了信息流",
                "data": {"posts": [{"content": "银狼发布了一篇技术帖"}]},
            },
            "recalled_memories": "上一轮已经召回的内容",
        }

        mock_config = MagicMock(memory_enabled=True, recall_limit=5)
        mock_chunk = MagicMock()
        mock_chunk.content = "这是一条测试记忆"
        mock_service = MagicMock()
        mock_service.recall_memories = AsyncMock(return_value=[(mock_chunk, "刚刚")])

        with patch("agents.agents_scheduler.langgraph.nodes.get_memory_config", return_value=mock_config):
            with patch("agents.agents_scheduler.langgraph.nodes.get_time_system") as mock_time:
                mock_time.return_value.get_scaled_timestamp.return_value = 12345.0
                with patch("agents.agents_scheduler.langgraph.nodes.get_memory_service", return_value=mock_service):
                    result = recall_memory_node(state)

                    # 验证记忆服务被调用
                    mock_service.recall_memories.assert_called_once()
                    call_kwargs = mock_service.recall_memories.call_args[1]

                    # 查询只包含当前语境，不包含固定角色信息或旧召回结果
                    query_context = call_kwargs["context"]
                    assert "银狼发布了一篇技术帖" in query_context
                    assert "看到帖子" in query_context
                    assert "你是一个测试角色" not in query_context
                    assert "测试签名" not in query_context
                    assert "上一轮已经召回的内容" not in query_context
                    assert "boost_on_recall" not in call_kwargs

                    # 验证召回的记忆被正确注入
                    assert result["recalled_memories"] != ""
                    assert "这是一条测试记忆" in result["recalled_memories"]
                    assert "相关记忆" in result["recalled_memories"]

    def test_recall_memory_node_no_memories_recalled(self):
        """测试没有召回记忆时的处理"""
        state = {
            "user_id": 1,
            "username": "test_user",
            "name": "Test",
            "personality_prompt": "测试角色",
            "personal_signature": "签名",
            "step_count": 0,
            "max_steps": 10,
            "action_history": [],
            "current_location": "主页（信息流）",
            "last_tool_result": None,
        }

        mock_config = MagicMock(memory_enabled=True, recall_limit=5)
        mock_service = MagicMock()
        mock_service.recall_memories = AsyncMock(return_value=[])

        with patch("agents.agents_scheduler.langgraph.nodes.get_memory_config", return_value=mock_config):
            with patch("agents.agents_scheduler.langgraph.nodes.get_time_system") as mock_time:
                mock_time.return_value.get_scaled_timestamp.return_value = 12345.0
                with patch("agents.agents_scheduler.langgraph.nodes.get_memory_service", return_value=mock_service):
                    result = recall_memory_node(state)

                    # 验证 recalled_memories 为空字符串
                    assert result["recalled_memories"] == ""
                    mock_service.recall_memories.assert_not_called()

    def test_recall_memory_node_exception_handling(self):
        """测试记忆召回异常时的处理"""
        state = {
            "user_id": 1,
            "username": "test_user",
            "name": "Test",
            "personality_prompt": "测试角色",
            "personal_signature": "签名",
            "step_count": 0,
            "max_steps": 10,
            "action_history": [],
            "current_location": "主页（信息流）",
            "last_tool_result": None,
        }

        mock_config = MagicMock(memory_enabled=True, recall_limit=5)

        with patch("agents.agents_scheduler.langgraph.nodes.get_memory_config", return_value=mock_config):
            with patch("agents.agents_scheduler.langgraph.nodes.get_time_system", side_effect=Exception("测试异常")):
                result = recall_memory_node(state)

                # 验证异常时 recalled_memories 为空字符串
                assert result["recalled_memories"] == ""


class TestLlmDecisionNode:
    def setup_method(self):
        self.base_state = {
            "user_id": 1,
            "username": "test_user",
            "name": "Test",
            "personality_prompt": "测试角色",
            "personal_signature": "测试签名",
            "step_count": 0,
            "max_steps": 10,
            "action_history": [],
            "current_location": "主页（信息流）",
            "last_tool_result": None,
            "pending_tool": None,
            "pending_tools": None,
            "last_error": None,
            "summary": None,
            "recalled_memories": "",
        }

    def test_llm_decision_node_uses_recalled_memories(self):
        """测试 llm_decision_node 使用已召回的记忆，不再执行查询"""
        state = {
            **self.base_state,
            "recalled_memories": "\n\n## 相关记忆\n[记忆片段 - 刚刚]\n这是一条测试记忆\n---",
        }

        mock_response = MagicMock()
        mock_response.tool_calls = None
        mock_response.content = "我决定做某事"

        mock_llm_invoker = MagicMock(return_value=mock_response)

        result = llm_decision_node(state, mock_llm_invoker)

        # 验证 LLM 被调用
        mock_llm_invoker.assert_called_once()
        system_prompt = mock_llm_invoker.call_args[0][0]
        user_prompt = mock_llm_invoker.call_args[0][1]

        # 验证 prompt 构建正确
        assert "你是Test" in system_prompt
        assert "相关记忆" in user_prompt

    def test_llm_decision_node_no_memory_query_logic(self):
        """测试 llm_decision_node 不再包含记忆查询逻辑"""
        state = {
            **self.base_state,
            "recalled_memories": "",
        }

        mock_response = MagicMock()
        mock_response.tool_calls = None
        mock_response.content = ""

        mock_llm_invoker = MagicMock(return_value=mock_response)

        with patch("agents.agents_scheduler.memory.service.get_memory_service") as mock_get_service:
            llm_decision_node(state, mock_llm_invoker)

            # 验证记忆服务没有被调用（因为查询逻辑已移到 recall_memory_node）
            mock_get_service.assert_not_called()


class TestSummarizeNode:
    def test_summarize_node_no_action_history(self):
        """测试没有操作历史时的处理"""
        state = {
            "user_id": 1,
            "username": "test_user",
            "action_history": [],
        }

        mock_llm_invoker = MagicMock()
        result = summarize_node(state, mock_llm_invoker)

        # 验证没有调用 LLM
        mock_llm_invoker.assert_not_called()
        assert "未执行任何操作" in result["summary"]

    def test_summarize_node_with_write_memory_tool(self):
        """测试总结节点能正确调用 write_memory 工具"""
        state = {
            "user_id": 1,
            "username": "test_user",
            "name": "Test",
            "personality_prompt": "测试角色",
            "personal_signature": "签名",
            "action_history": [
                {"step": 1, "timestamp": "2024-01-01", "summary": "看到帖子", "action": "浏览了帖子", "reason": "感兴趣"},
            ],
        }

        # 模拟 LLM 返回工具调用
        mock_tool_call = {
            "name": "write_memory",
            "args": {
                "memories": [{"content": "我今天浏览了一个帖子", "memory_coefficient": 0.85}],
                "reason": "记录浏览经历",
            },
        }

        mock_response = MagicMock()
        mock_response.tool_calls = [mock_tool_call]
        mock_response.content = "我总结了今天的会话内容，浏览了一些有趣的帖子。"

        mock_tool = MagicMock()
        mock_tool.name = "write_memory"
        mock_tool.invoke = MagicMock(return_value=MagicMock(action="将1条记忆写入长期记忆库"))

        mock_llm_invoker = MagicMock(return_value=mock_response)

        with patch("agents.agents_scheduler.langgraph.nodes.get_all_tools_for_summarize", return_value=[mock_tool]):
            result = summarize_node(state, mock_llm_invoker)

            # 验证 LLM 被调用
            mock_llm_invoker.assert_called_once()

            # 验证 write_memory 工具被调用
            mock_tool.invoke.assert_called_once()

            # 验证总结被正确设置
            assert result["summary"] == "我总结了今天的会话内容，浏览了一些有趣的帖子。"

    def test_summarize_node_empty_summary_uses_default(self):
        """测试当 LLM 返回空总结时使用默认总结"""
        state = {
            "user_id": 1,
            "username": "test_user",
            "name": "Test",
            "personality_prompt": "测试角色",
            "personal_signature": "签名",
            "action_history": [
                {"step": 1, "timestamp": "2024-01-01", "summary": "看到帖子", "action": "浏览了帖子", "reason": "感兴趣"},
            ],
        }

        mock_response = MagicMock()
        mock_response.tool_calls = None
        mock_response.content = ""  # 空总结

        mock_llm_invoker = MagicMock(return_value=mock_response)

        result = summarize_node(state, mock_llm_invoker)

        # 验证使用了默认总结
        assert "执行了 1 个操作" in result["summary"]


class TestToolLocationMapping:
    def test_get_location_after_tool_known(self):
        assert _get_location_after_tool("get_global_feed") == "主页（信息流）"
        assert _get_location_after_tool("expand_post") == "帖子详情页"
        assert _get_location_after_tool("expand_comment") == "评论页"
        assert _get_location_after_tool("view_post_comments") == "评论页"
        assert _get_location_after_tool("get_user_profile") == "用户主页"

    def test_get_location_after_tool_unknown(self):
        assert _get_location_after_tool("unknown_tool") is None
        assert _get_location_after_tool("logout") is None
        assert _get_location_after_tool("toggle_post_like") is None

    def test_get_location_after_tool_case_insensitive(self):
        assert _get_location_after_tool("Get_Global_Feed") == "主页（信息流）"
        assert _get_location_after_tool("GET_GLOBAL_FEED") == "主页（信息流）"

    def test_tools_with_return_value(self):
        assert "get_profile" not in TOOLS_WITH_RETURN_VALUE
        assert "get_global_feed" in TOOLS_WITH_RETURN_VALUE
        assert "scroll" in TOOLS_WITH_RETURN_VALUE
        assert "recall_memory" in TOOLS_WITH_RETURN_VALUE
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
            "agent_id": 1,
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
        assert result["agent_id"] == 1


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

    def test_tool_execution_node_recall_memory_appends_to_last_result(self):
        state = {
            "username": "test_user",
            "step_count": 0,
            "max_steps": 10,
            "exit_reason": None,
            "action_history": [],
            "current_location": "帖子详情页",
            "last_tool_result": {"post": {"id": 1, "content": "hello"}},
            "pending_tool": {"tool_name": "recall_memory", "args": {"query": "hello", "reason": "test", "summary": "test"}},
            "pending_tools": None,
            "last_error": None,
            "summary": None,
            "recalled_memories": "",
        }
        mock_tool = MagicMock()
        mock_tool.name = "recall_memory"
        mock_tool.invoke.return_value = {
            "action": "回想了与「hello」相关的1条记忆",
            "data": {"query": "hello", "memories": [{"content": "old hello"}], "total": 1},
        }

        with patch("agents.agents_scheduler.langgraph.nodes.get_social_tools", return_value=[mock_tool]):
            result = tool_execution_node(state)

        assert result["last_tool_result"]["current_view"] == {"post": {"id": 1, "content": "hello"}}
        assert result["last_tool_result"]["explicit_recalls"][0]["query"] == "hello"
        assert result["current_location"] == "帖子详情页"


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
