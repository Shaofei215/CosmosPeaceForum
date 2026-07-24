"""Agent 删除时的记忆级联清理测试。"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest

from agents.management.backend.api import agents as agents_api


def test_clear_agent_memories_uses_social_platform_user_id() -> None:
    """记忆清理必须使用公开平台用户 ID，而不是管理端角色 ID。"""
    agent = SimpleNamespace(id=7, social_platform_user_id=42)
    memory_service = MagicMock()
    memory_service.clear_user_memories = AsyncMock(return_value=3)

    with patch(
        "agents.agents_scheduler.memory.service.get_memory_service",
        return_value=memory_service,
    ):
        count = agents_api._clear_agent_memories(agent)

    assert count == 3
    memory_service.clear_user_memories.assert_awaited_once_with(42)


def test_clear_agent_memories_skips_unregistered_agent() -> None:
    """尚无公开平台用户 ID 的角色不需要访问记忆服务。"""
    agent = SimpleNamespace(id=7, social_platform_user_id=None)

    with patch(
        "agents.agents_scheduler.memory.service.get_memory_service"
    ) as get_memory_service:
        count = agents_api._clear_agent_memories(agent)

    assert count == 0
    get_memory_service.assert_not_called()


def test_delete_agent_clears_memories_before_deleting_config() -> None:
    """单删必须先清理记忆，再删除角色配置。"""
    agent = SimpleNamespace(id=7, social_platform_user_id=42)
    db = MagicMock()
    events = []

    with (
        patch.object(agents_api.agent_service, "get_agent", return_value=agent),
        patch.object(
            agents_api,
            "notify_scheduler_reload",
            side_effect=lambda *args, **kwargs: events.append(("scheduler", args, kwargs)),
        ),
        patch.object(
            agents_api,
            "_clear_agent_memories",
            side_effect=lambda value: events.append(("clear", value)) or 3,
        ),
        patch.object(
            agents_api.agent_service,
            "delete_agent",
            side_effect=lambda *args: events.append(("delete", args)),
        ),
        patch.object(agents_api, "create_log") as create_log,
    ):
        response = agents_api.delete_agent(
            agent_id=7,
            db=db,
            current_admin=MagicMock(),
        )

    assert response.message == "Agent 已删除"
    assert events == [
        ("scheduler", ("agent", 7), {"action": "stop"}),
        ("clear", agent),
        ("delete", (db, 7)),
    ]
    create_log.assert_called_once()
    assert create_log.call_args.kwargs["details"] == {
        "social_platform_user_id": 42,
        "deleted_memory_count": 3,
    }


def test_delete_agent_keeps_config_when_memory_cleanup_fails() -> None:
    """记忆主数据清理失败时不得继续删除角色配置。"""
    agent = SimpleNamespace(id=7, social_platform_user_id=42)

    with (
        patch.object(agents_api.agent_service, "get_agent", return_value=agent),
        patch.object(agents_api, "notify_scheduler_reload"),
        patch.object(
            agents_api,
            "_clear_agent_memories",
            side_effect=RuntimeError("memory cleanup failed"),
        ),
        patch.object(agents_api.agent_service, "delete_agent") as delete_agent,
        patch.object(agents_api, "create_log") as create_log,
    ):
        with pytest.raises(RuntimeError, match="memory cleanup failed"):
            agents_api.delete_agent(
                agent_id=7,
                db=MagicMock(),
                current_admin=MagicMock(),
            )

    delete_agent.assert_not_called()
    create_log.assert_not_called()


def test_batch_delete_clears_each_agents_memories() -> None:
    """批量删除必须逐个清理角色对应的记忆。"""
    agents = {
        7: SimpleNamespace(id=7, social_platform_user_id=42),
        8: SimpleNamespace(id=8, social_platform_user_id=43),
    }
    db = MagicMock()

    with (
        patch.object(
            agents_api.agent_service,
            "get_agent",
            side_effect=lambda _db, agent_id: agents.get(agent_id),
        ),
        patch.object(agents_api, "notify_scheduler_reload"),
        patch.object(
            agents_api,
            "_clear_agent_memories",
            side_effect=[3, 5],
        ) as clear_memories,
        patch.object(agents_api.agent_service, "delete_agent") as delete_agent,
        patch.object(agents_api, "create_log") as create_log,
    ):
        response = agents_api.batch_delete_agents(
            agent_ids=[7, 999, 8],
            db=db,
            current_admin=MagicMock(),
        )

    assert response.message == "已批量删除 2 个 Agent"
    assert clear_memories.call_args_list == [call(agents[7]), call(agents[8])]
    assert delete_agent.call_args_list == [call(db, 7), call(db, 8)]
    assert create_log.call_args.kwargs["details"] == {
        "count": 2,
        "deleted_memory_count": 8,
    }
