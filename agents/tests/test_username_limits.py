from unittest.mock import MagicMock, patch
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from agents.management.backend.schemas import AgentCreate, AgentUpdate
from agents.management.backend.services import registrar
from social_platform.app.schemas.auth import UserRegister
from social_platform.app.domains.user.schemas import CompleteProfileRequest


class TestUsernameLengthLimits:
    def test_ai_register_accepts_30_characters(self):
        username = "a" * 30
        payload = UserRegister(
            username=username,
            password="secret123",
        )

        assert payload.username == username

    def test_ai_register_rejects_31_characters(self):
        with pytest.raises(ValidationError) as exc_info:
            UserRegister(
                username="a" * 31,
                password="secret123",
            )

        assert exc_info.value.errors()[0]["type"] == "string_too_long"

    def test_complete_profile_accepts_30_chinese_characters(self):
        username = "星" * 30
        payload = CompleteProfileRequest(username=username)

        assert payload.username == username

    def test_complete_profile_rejects_31_characters(self):
        with pytest.raises(ValidationError) as exc_info:
            CompleteProfileRequest(username="星" * 31)

        assert exc_info.value.errors()[0]["type"] == "string_too_long"

    def test_management_agent_create_rejects_31_characters(self):
        with pytest.raises(ValidationError) as exc_info:
            AgentCreate(name="Test", username="a" * 31)

        assert exc_info.value.errors()[0]["type"] == "string_too_long"

    def test_management_agent_create_accepts_30_characters(self):
        username = "a" * 30
        agent = AgentCreate(name="Test", username=username)

        assert agent.username == username

    def test_management_agent_update_rejects_31_characters(self):
        with pytest.raises(ValidationError) as exc_info:
            AgentUpdate(username="a" * 31)

        assert exc_info.value.errors()[0]["type"] == "string_too_long"


class TestRegistrar:
    def test_update_user_username_uses_public_profile_api(self):
        mock_response = MagicMock(status_code=200)

        with (
            patch.object(registrar, "_login_user", return_value="access-token"),
            patch.object(registrar, "_get_user_id", return_value=42),
            patch.object(registrar.requests, "put", return_value=mock_response) as mock_put,
        ):
            success, error, status_code = registrar.update_user_username(
                api_base_url="http://localhost:8000/api/v1",
                current_username="old_name",
                password="secret123",
                user_id=42,
                new_username="new_name",
            )

        assert success is True
        assert error is None
        assert status_code == 200
        mock_put.assert_called_once_with(
            "http://localhost:8000/api/v1/users/42",
            json={"username": "new_name"},
            headers={
                "Authorization": "Bearer access-token",
                "Content-Type": "application/json",
            },
            timeout=10,
        )

    def test_update_user_username_rejects_mismatched_platform_account(self):
        with (
            patch.object(registrar, "_login_user", return_value="access-token"),
            patch.object(registrar, "_get_user_id", return_value=99),
            patch.object(registrar.requests, "put") as mock_put,
        ):
            success, error, status_code = registrar.update_user_username(
                api_base_url="http://localhost:8000/api/v1",
                current_username="old_name",
                password="secret123",
                user_id=42,
                new_username="new_name",
            )

        assert success is False
        assert error == "social_platform 账号映射不一致"
        assert status_code is None
        mock_put.assert_not_called()

    def test_register_agent_stops_retrying_on_422(self):
        mock_response = MagicMock(status_code=422, text='{"detail":"invalid"}')
        mock_response.json.return_value = {
            "detail": [
                {
                    "type": "string_too_long",
                    "loc": ["body", "username"],
                    "msg": "String should have at most 30 characters",
                }
            ]
        }

        with (
            patch(
                "agents.management.backend.services.registrar._get_ai_user_password",
                return_value="secret123",
            ),
            patch(
                "agents.management.backend.services.registrar._get_api_base_url",
                return_value="http://localhost:8000/api/v1",
            ),
            patch(
                "agents.management.backend.services.registrar._get_admin_key",
                return_value="admin-key",
            ),
            patch(
                "agents.management.backend.services.registrar.requests.post",
                return_value=mock_response,
            ) as mock_post,
            patch("agents.management.backend.services.registrar.time.sleep") as mock_sleep,
        ):
            success, user_id, error = registrar.register_agent(
                db=MagicMock(),
                username="a" * 31,
            )

        assert success is False
        assert user_id is None
        assert error is not None
        assert "参数校验失败" in error
        assert mock_post.call_count == 1
        mock_sleep.assert_not_called()

    def test_management_login_uses_admin_agent_login_without_service_identity(self):
        mock_response = MagicMock(status_code=200)
        mock_response.json.return_value = {
            "access_token": "access-token",
            "refresh_token": "refresh-token",
            "expires_in": 900,
            "refresh_expires_in": 43200,
            "session_id": "session-id",
        }

        with (
            patch(
                "agents.management.backend.services.registrar.get_config",
                return_value=SimpleNamespace(admin_key="admin-key"),
            ),
            patch(
                "agents.management.backend.services.registrar.requests.post",
                return_value=mock_response,
            ) as mock_post,
        ):
            token_response = registrar._login_user_response(
                "http://localhost:8000/api/v1",
                "agent_name",
                "secret123",
            )

        assert token_response == mock_response.json.return_value
        mock_post.assert_called_once_with(
            "http://localhost:8000/api/v1/auth/admin-agent-login",
            json={"username": "agent_name", "password": "secret123"},
            headers={
                "Content-Type": "application/json",
                "X-Admin-Key": "admin-key",
            },
            timeout=10,
        )
