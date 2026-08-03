"""角色配置导出 ZIP 的单元测试。"""

import asyncio
import json
import os
import zipfile
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from agents.management.backend.api import agents as agents_api
from agents.management.backend.models.agent_config import AgentConfig
from agents.management.backend.services import agent_service


def _mock_db_with_agents(agents: list[AgentConfig]) -> MagicMock:
    """构造返回指定角色列表的数据库会话。"""
    db = MagicMock()
    db.exec.return_value.all.return_value = agents
    return db


def _http_response(
    *,
    status_code: int = 200,
    json_data: object | None = None,
    content: bytes = b"",
    content_type: str = "",
) -> MagicMock:
    """构造 requests 响应替身。"""
    response = MagicMock()
    response.status_code = status_code
    response.json.return_value = json_data
    response.content = content
    response.headers = {"content-type": content_type}
    return response


def test_export_agents_to_zip_builds_import_compatible_archive() -> None:
    """导出包应从公开平台下载并去重头像，同时保留可导入字段。"""
    agents = [
        AgentConfig(
            id=1,
            name="共同头像",
            username="agent_one",
            monthly_logins=12,
            personal_signature="你好，宇宙。",
            personality_prompt="你是一位沉稳的观察者。",
            is_active=False,
            model_config_id=9,
            social_platform_user_id=101,
            knows_ids="[2]",
        ),
        AgentConfig(
            id=2,
            name="共同头像",
            username="agent_two",
            monthly_logins=48,
            personal_signature="第二位角色",
            personality_prompt="保持好奇。",
            social_platform_user_id=102,
        ),
        AgentConfig(
            id=3,
            name="没有头像",
            username="agent_three",
            monthly_logins=30,
            personal_signature="",
            personality_prompt="独立思考。",
        ),
    ]

    profile_response = _http_response(
        json_data={"avatar_url": "uploads/avatars/共同头像.png"},
    )
    avatar_response = _http_response(
        content=b"avatar-content",
        content_type="image/png",
    )
    with patch.object(
        agent_service.requests,
        "get",
        side_effect=[profile_response, avatar_response, profile_response, avatar_response],
    ) as request:
        result = agent_service.export_agents_to_zip(
            _mock_db_with_agents(agents),
            "http://social-platform:8000/api/v1",
        )

    try:
        assert result.agent_count == 3
        assert result.avatar_count == 1
        with zipfile.ZipFile(result.path) as archive:
            assert archive.namelist() == [
                "avatar/共同头像.png",
                "ai_users_config.json",
            ]
            config = json.loads(archive.read("ai_users_config.json").decode("utf-8"))
            assert config == {
                "ai_users": [
                    {
                        "name": "共同头像",
                        "username": "agent_one",
                        "monthly_logins": 12,
                        "personal_signature": "你好，宇宙。",
                        "personality_prompt": "你是一位沉稳的观察者。",
                        "avatar": "共同头像.png",
                    },
                    {
                        "name": "共同头像",
                        "username": "agent_two",
                        "monthly_logins": 48,
                        "personal_signature": "第二位角色",
                        "personality_prompt": "保持好奇。",
                        "avatar": "共同头像.png",
                    },
                    {
                        "name": "没有头像",
                        "username": "agent_three",
                        "monthly_logins": 30,
                        "personal_signature": "",
                        "personality_prompt": "独立思考。",
                    },
                ]
            }
            assert archive.read("avatar/共同头像.png") == b"avatar-content"
        assert request.call_args_list[0].args == (
            "http://social-platform:8000/api/v1/users/101",
        )
        assert request.call_args_list[1].args == (
            "http://social-platform:8000/uploads/avatars/共同头像.png",
        )
    finally:
        os.remove(result.path)


def test_export_agents_to_zip_rejects_empty_database(tmp_path: Path) -> None:
    """空数据库不能生成现有导入流程无法接受的配置包。"""
    with pytest.raises(ValueError, match="没有可导出的角色"):
        agent_service.export_agents_to_zip(
            _mock_db_with_agents([]),
            "http://social-platform:8000/api/v1",
        )


def test_export_agents_to_zip_skips_unavailable_remote_avatar() -> None:
    """公开平台头像请求失败时仍应生成不含头像的角色配置。"""
    agent = AgentConfig(
        id=1,
        name="离线角色",
        username="offline_agent",
        social_platform_user_id=7,
    )
    with patch.object(
        agent_service.requests,
        "get",
        return_value=_http_response(status_code=503),
    ):
        result = agent_service.export_agents_to_zip(
            _mock_db_with_agents([agent]),
            "http://social-platform:8000/api/v1",
        )

    try:
        assert result.avatar_count == 0
        with zipfile.ZipFile(result.path) as archive:
            assert archive.namelist() == ["ai_users_config.json"]
            config = json.loads(archive.read("ai_users_config.json"))
            assert "avatar" not in config["ai_users"][0]
    finally:
        os.remove(result.path)


def test_exported_archive_is_readable_by_existing_import_service(tmp_path: Path) -> None:
    """现有批量导入解析器应能直接读取新生成的导出包。"""
    agent = AgentConfig(
        id=1,
        name="回归角色",
        username="round_trip_agent",
        monthly_logins=24,
        personal_signature="导入导出回归",
        personality_prompt="保持配置一致。",
    )
    export_db = _mock_db_with_agents([agent])
    result = agent_service.export_agents_to_zip(
        export_db,
        "http://social-platform:8000/api/v1",
    )
    import_db = MagicMock()
    import_db.exec.return_value.first.return_value = None

    try:
        imported = agent_service.import_agents_from_zip(import_db, result.path)
    finally:
        os.remove(result.path)

    assert len(imported) == 1
    assert imported[0].name == agent.name
    assert imported[0].username == agent.username
    assert imported[0].monthly_logins == agent.monthly_logins
    assert imported[0].personal_signature == agent.personal_signature
    assert imported[0].personality_prompt == agent.personality_prompt


def test_export_agents_returns_zip_logs_and_removes_temporary_file(tmp_path: Path) -> None:
    """导出接口应返回带文件名的 ZIP，并在响应完成后清理临时文件。"""
    archive_path = tmp_path / "export.zip"
    archive_path.write_bytes(b"zip-content")
    export_archive = agent_service.AgentExportArchive(
        path=str(archive_path),
        agent_count=3,
        avatar_count=2,
    )
    db = MagicMock()
    admin = SimpleNamespace(id=7)

    with (
        patch.object(
            agents_api.agent_service,
            "export_agents_to_zip",
            return_value=export_archive,
        ) as export_mock,
        patch.object(
            agents_api,
            "_get_api_base_url",
            return_value="http://social-platform:8000/api/v1",
        ),
        patch.object(agents_api, "create_log") as create_log,
        patch.object(agents_api, "local_now", return_value=datetime(2026, 8, 4, 9, 8, 7)),
    ):
        response = agents_api.export_agents(db=db, current_admin=admin)

    assert response.media_type == "application/zip"
    assert response.headers["content-disposition"].endswith(
        'filename="agents_config_20260804_090807.zip"'
    )
    create_log.assert_called_once_with(
        db,
        admin,
        "export_agents",
        "agent",
        details={"count": 3, "avatar_count": 2},
    )
    export_mock.assert_called_once_with(
        db,
        "http://social-platform:8000/api/v1",
    )
    assert archive_path.exists()
    assert response.background is not None
    asyncio.run(response.background())
    assert not archive_path.exists()


def test_export_agents_maps_empty_database_to_bad_request() -> None:
    """导出服务的空库错误应转换为清晰的 HTTP 400。"""
    with patch.object(
        agents_api.agent_service,
        "export_agents_to_zip",
        side_effect=ValueError("当前数据库中没有可导出的角色"),
    ):
        with pytest.raises(HTTPException) as exc_info:
            agents_api.export_agents(db=MagicMock(), current_admin=MagicMock())

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "当前数据库中没有可导出的角色"
