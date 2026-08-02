"""Scheduler 内部热更新接口单元测试。"""

from unittest.mock import MagicMock, patch

from agents.agents_scheduler.scheduler.internal_server import SchedulerInternalHandler


def test_reload_relations_only_rebuilds_mapping() -> None:
    """关系热更新不得触发任何角色启停或全量重启。"""
    handler = object.__new__(SchedulerInternalHandler)
    handler.scheduler_manager = MagicMock()
    handler._send_json_response = MagicMock()

    with patch(
        "agents.agents_scheduler.scheduler.relation_map.rebuild_relation_maps"
    ) as rebuild:
        handler._handle_reload_relations()

    rebuild.assert_called_once_with()
    handler.scheduler_manager.restart_agent.assert_not_called()
    handler.scheduler_manager.restart_all.assert_not_called()
    handler.scheduler_manager.request_restart_all.assert_not_called()
    handler._send_json_response.assert_called_once_with(
        200,
        {"message": "relations reloaded"},
    )


def test_reload_all_submits_coalesced_manager_request() -> None:
    """全量热更新应交给管理器协调器，而不是自行创建重启线程。"""
    handler = object.__new__(SchedulerInternalHandler)
    handler.scheduler_manager = MagicMock()
    handler.scheduler_manager.request_restart_all.return_value = True
    handler._send_json_response = MagicMock()
    memory_config = MagicMock()

    with (
        patch("agents.agents_scheduler.langgraph.config.reload_session_config"),
        patch(
            "agents.agents_scheduler.memory.config.MemoryConfig.from_db",
            return_value=memory_config,
        ),
        patch("agents.agents_scheduler.memory.config.reload_memory_config"),
        patch("agents.agents_scheduler.memory.embedding.reload_embedding_model"),
        patch("agents.agents_scheduler.memory.service.reload_memory_service"),
        patch("agents.agents_scheduler.scheduler.relation_map.rebuild_relation_maps"),
        patch("agents.agents_scheduler.langgraph.executor.reload_llm_registry"),
        patch("agents.agents_scheduler.scheduler.time_system.reload_time_scale"),
    ):
        handler._handle_reload_all()

    handler.scheduler_manager.request_restart_all.assert_called_once_with()
    handler.scheduler_manager.restart_all.assert_not_called()
    handler._send_json_response.assert_called_once_with(
        200,
        {"message": "all config reloaded"},
    )
