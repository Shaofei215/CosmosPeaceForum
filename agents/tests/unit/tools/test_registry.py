"""LangGraph 工具注册表测试。"""

from unittest.mock import MagicMock, patch

from agents.agents_scheduler.langgraph.tools.support.registry import (
    get_all_tools_for_summarize,
    get_social_tools,
)


class TestGetSocialTools:
    """验证决策节点使用的工具集合。"""

    def test_get_social_tools_returns_list(self) -> None:
        tools = get_social_tools()
        assert isinstance(tools, list)
        assert tools

    def test_get_social_tools_does_not_contain_write_memory(self) -> None:
        tool_names = [tool.name.lower() for tool in get_social_tools()]
        assert "write_memory" not in tool_names

    def test_get_social_tools_contains_expected_tools(self) -> None:
        tool_names = [tool.name.lower() for tool in get_social_tools()]
        expected_names = [
            "view_full_hot_topics",
            "toggle_post_like",
            "toggle_comment_like",
            "create_comment",
            "toggle_follow",
            "create_post",
            "logout",
            "delete_content",
            "report_content",
            "get_user_profile",
            "get_global_feed",
            "expand_post",
            "view_post_comments",
            "expand_comment",
            "scroll",
            "recall_memory",
            "edit_short_term_memory",
        ]
        for name in expected_names:
            assert name in tool_names, f"Missing tool: {name}"

    def test_short_term_memory_is_not_a_shared_platform_tool(self) -> None:
        """短期记忆只能属于内部决策工具集合，不能暴露给外部 Agent。"""

        from agents.platform_tools.registry import PLATFORM_TOOLS

        assert "edit_short_term_memory" not in PLATFORM_TOOLS

    def test_get_social_tools_contains_web_search_when_enabled(self) -> None:
        with patch("agents.agents_scheduler.langgraph.config.get_session_config") as mock_config:
            mock_config.return_value = MagicMock(web_search_enabled=True)
            tools = get_social_tools()

        assert "web_search" in [tool.name.lower() for tool in tools]

    def test_get_social_tools_caching(self) -> None:
        assert get_social_tools() is get_social_tools()

    def test_get_social_tools_with_relation_map(self) -> None:
        tools = get_social_tools(relation_map=MagicMock())
        assert isinstance(tools, list)
        assert tools


class TestGetAllToolsForSummarize:
    """验证总结节点只允许写入记忆。"""

    def test_get_all_tools_for_summarize_returns_list(self) -> None:
        tools = get_all_tools_for_summarize()
        assert isinstance(tools, list)
        assert tools

    def test_get_all_tools_for_summarize_only_contains_write_memory(self) -> None:
        tool_names = [tool.name.lower() for tool in get_all_tools_for_summarize()]
        assert tool_names == ["write_memory"]
