"""角色关系更新的 Scheduler 通知边界测试。"""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from agents.management.backend.api import agents as agents_api
from agents.management.backend.schemas import AgentRelationUpdate


def test_relation_update_uses_relation_only_reload() -> None:
    """保存角色关系只能请求关系映射热更新，不能触发全量重启。"""
    agent = SimpleNamespace(id=7)
    updated = SimpleNamespace(id=7)
    with (
        patch.object(agents_api.agent_service, "get_agent", return_value=agent),
        patch.object(agents_api.agent_service, "update_agent_knows", return_value=updated),
        patch.object(
            agents_api.agent_service,
            "agent_to_response",
            return_value={"id": 7, "knows_ids": [8]},
        ),
        patch.object(agents_api, "notify_scheduler_reload") as notify,
        patch.object(agents_api, "create_log"),
    ):
        response = agents_api.update_agent_relation(
            agent_id=7,
            relation_in=AgentRelationUpdate(knows_ids=[8]),
            db=MagicMock(),
            current_admin=MagicMock(),
        )

    assert response == {"id": 7, "knows_ids": [8]}
    notify.assert_called_once_with("relations")
