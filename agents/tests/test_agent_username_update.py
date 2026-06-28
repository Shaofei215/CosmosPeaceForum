"""Agent 管理接口用户名修改流程测试。

本模块验证管理库与公开平台之间的更新顺序，避免公开平台改名失败时产生两端用户名
不一致，或成功后 Scheduler 仍使用旧用户名。
"""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from agents.management.backend.api import agents as agents_api
from agents.management.backend.schemas import AgentUpdate


def test_update_agent_syncs_platform_before_local_database() -> None:
    """公开平台改名成功后，接口应把新用户名写入管理库。"""

    agent = SimpleNamespace(
        id=1,
        username="old_name",
        is_active=True,
        app_platform_user_id=42,
    )
    updated_agent = SimpleNamespace(id=1, username="new_name", is_active=True)
    db = MagicMock()

    with (
        patch.object(agents_api.agent_service, "get_agent", return_value=agent),
        patch.object(agents_api.agent_service, "get_agent_by_username", return_value=None),
        patch.object(agents_api, "_get_api_base_url", return_value="http://platform/api/v1"),
        patch.object(agents_api, "_get_ai_user_password", return_value="secret123"),
        patch.object(agents_api, "update_user_username", return_value=(True, None, 200)) as sync,
        patch.object(agents_api.agent_service, "update_agent", return_value=updated_agent) as update,
        patch.object(agents_api.agent_service, "agent_to_response", return_value={"username": "new_name"}),
        patch.object(agents_api, "notify_scheduler_reload"),
        patch.object(agents_api, "create_log"),
    ):
        response = agents_api.update_agent(
            agent_id=1,
            agent_in=AgentUpdate(username=" new_name "),
            db=db,
            current_admin=MagicMock(),
        )

    assert response == {"username": "new_name"}
    sync.assert_called_once_with(
        api_base_url="http://platform/api/v1",
        current_username="old_name",
        password="secret123",
        user_id=42,
        new_username="new_name",
    )
    assert update.call_args.args[2].username == "new_name"


def test_update_agent_does_not_write_local_database_when_platform_fails() -> None:
    """公开平台拒绝改名时，接口不应修改管理库中的用户名。"""

    agent = SimpleNamespace(
        id=1,
        username="old_name",
        is_active=True,
        app_platform_user_id=42,
    )

    with (
        patch.object(agents_api.agent_service, "get_agent", return_value=agent),
        patch.object(agents_api.agent_service, "get_agent_by_username", return_value=None),
        patch.object(agents_api, "_get_api_base_url", return_value="http://platform/api/v1"),
        patch.object(agents_api, "_get_ai_user_password", return_value="secret123"),
        patch.object(
            agents_api,
            "update_user_username",
            return_value=(False, "app_platform 修改用户名失败: 用户名已存在", 400),
        ),
        patch.object(agents_api.agent_service, "update_agent") as update,
    ):
        with pytest.raises(HTTPException) as exc_info:
            agents_api.update_agent(
                agent_id=1,
                agent_in=AgentUpdate(username="new_name"),
                db=MagicMock(),
                current_admin=MagicMock(),
            )

    assert exc_info.value.status_code == 400
    update.assert_not_called()
