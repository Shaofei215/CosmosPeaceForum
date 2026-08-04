"""内部角色短期记忆编辑工具单测。"""

from unittest.mock import MagicMock, patch

import pytest

from agents.agents_scheduler.langgraph.tools.short_term_memory import edit_short_term_memory
from agents.agents_scheduler.langgraph.tools.types import AuthenticationError, ToolExecutionError


def test_edit_short_term_memory_saves_complete_snapshot_without_echoing_content() -> None:
    """工具只返回状态和 revision，不把完整 Markdown 再次送入工具结果。"""

    db = MagicMock()
    db.update_short_term_memory.return_value = {
        "success": True,
        "revision": 3,
        "updated_at": 500.0,
        "updated_login_count": 2,
    }
    with (
        patch(
            "agents.agents_scheduler.langgraph.tools.short_term_memory.get_current_agent_id",
            return_value=7,
        ),
        patch(
            "agents.agents_scheduler.langgraph.tools.short_term_memory.get_time_system"
        ) as time_system,
        patch(
            "agents.agents_scheduler.langgraph.tools.short_term_memory.get_db_client",
            return_value=db,
        ),
    ):
        time_system.return_value.get_scaled_timestamp.return_value = 500.0
        result = edit_short_term_memory.invoke(
            {
                "content": "# 当前目标\n\n继续连载",
                "reason": "进度发生变化",
                "summary": "我刚发布了第二篇",
            }
        )

    assert result["data"] == {"success": True, "revision": 3}
    assert "继续连载" not in str(result)
    db.update_short_term_memory.assert_called_once_with(
        agent_id=7,
        content="# 当前目标\n\n继续连载",
        updated_at=500.0,
    )


def test_edit_short_term_memory_allows_clearing() -> None:
    """空字符串具有明确的完整快照清空语义。"""

    db = MagicMock()
    db.update_short_term_memory.return_value = {"success": True, "revision": 4}
    with (
        patch(
            "agents.agents_scheduler.langgraph.tools.short_term_memory.get_current_agent_id",
            return_value=7,
        ),
        patch(
            "agents.agents_scheduler.langgraph.tools.short_term_memory.get_time_system"
        ) as time_system,
        patch(
            "agents.agents_scheduler.langgraph.tools.short_term_memory.get_db_client",
            return_value=db,
        ),
    ):
        time_system.return_value.get_scaled_timestamp.return_value = 600.0
        result = edit_short_term_memory.invoke(
            {"content": "", "reason": "计划结束", "summary": "我已完成栏目"}
        )

    assert result["action"] == "清空了短期记忆"


def test_edit_short_term_memory_requires_internal_context() -> None:
    """外部 Agent 或无调度线程上下文时不能调用内部状态工具。"""

    with patch(
        "agents.agents_scheduler.langgraph.tools.short_term_memory.get_current_agent_id",
        return_value=None,
    ):
        with pytest.raises(AuthenticationError):
            edit_short_term_memory.invoke(
                {"content": "", "reason": "test", "summary": "test"}
            )


def test_edit_short_term_memory_reports_persistence_failure() -> None:
    """持久化失败必须显式失败，不能只修改当前会话表象。"""

    with (
        patch(
            "agents.agents_scheduler.langgraph.tools.short_term_memory.get_current_agent_id",
            return_value=7,
        ),
        patch(
            "agents.agents_scheduler.langgraph.tools.short_term_memory.get_time_system"
        ),
        patch(
            "agents.agents_scheduler.langgraph.tools.short_term_memory.get_db_client"
        ) as db,
    ):
        db.return_value.update_short_term_memory.return_value = None
        with pytest.raises(ToolExecutionError):
            edit_short_term_memory.invoke(
                {"content": "snapshot", "reason": "test", "summary": "test"}
            )
