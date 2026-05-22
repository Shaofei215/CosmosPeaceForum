from unittest.mock import MagicMock, patch

import pytest
from pydantic import ValidationError

from agents.management.backend.schemas import AgentCreate
from agents.management.backend.services import registrar
from social_platform.app.schemas.auth import UserRegister
from social_platform.app.schemas.user import CompleteProfileRequest


class TestUsernameLengthLimits:
    def test_ai_register_accepts_30_characters(self):
        username = "a" * 30
        payload = UserRegister(
            username=username,
            password="secret123",
            is_ai_agent=True,
            ai_config_id=1,
        )

        assert payload.username == username

    def test_ai_register_rejects_31_characters(self):
        with pytest.raises(ValidationError) as exc_info:
            UserRegister(
                username="a" * 31,
                password="secret123",
                is_ai_agent=True,
                ai_config_id=1,
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


class TestRegistrar:
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
                ai_config_id=1,
            )

        assert success is False
        assert user_id is None
        assert error is not None
        assert "参数校验失败" in error
        assert mock_post.call_count == 1
        mock_sleep.assert_not_called()
