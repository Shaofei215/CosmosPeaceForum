import pytest
from datetime import datetime
from pydantic import ValidationError

from agents.management.backend.schemas import (
    LoginRequest,
    LoginResponse,
    AdminUserResponse,
    UpdateProfileRequest,
    AgentCreate,
    AgentUpdate,
    AgentResponse,
    AgentListResponse,
    AgentRelationUpdate,
    ModelConfigCreate,
    ModelConfigUpdate,
    ModelConfigResponse,
    SystemConfigResponse,
    SystemConfigUpdate,
    OperationLogResponse,
    OperationLogListResponse,
    MessageResponse,
)


class TestAuthSchemas:
    def test_login_request(self):
        req = LoginRequest(username="admin", password="password")
        assert req.username == "admin"
        assert req.password == "password"

    def test_login_response(self):
        resp = LoginResponse(access_token="token")
        assert resp.access_token == "token"
        assert resp.token_type == "bearer"

    def test_admin_user_response(self):
        resp = AdminUserResponse(
            id=1,
            username="admin",
            created_at=datetime.now(),
            last_login=datetime.now(),
        )
        assert resp.id == 1
        assert resp.username == "admin"

    def test_update_profile_request(self):
        req = UpdateProfileRequest(current_password="old")
        assert req.current_password == "old"
        assert req.username is None

        req2 = UpdateProfileRequest(
            username="newname",
            current_password="old",
            new_password="new",
        )
        assert req2.username == "newname"
        assert req2.new_password == "new"


class TestAgentSchemas:
    def test_agent_create(self):
        agent = AgentCreate(
            name="Test",
            username="test_user",
            monthly_logins=50,
        )
        assert agent.name == "Test"
        assert agent.username == "test_user"
        assert agent.monthly_logins == 50
        assert agent.is_active is True

    def test_agent_update(self):
        update = AgentUpdate(name="NewName")
        assert update.name == "NewName"
        assert update.monthly_logins is None

    def test_agent_response(self):
        resp = AgentResponse(
            id=1,
            name="Test",
            username="test_user",
            monthly_logins=30,
            personal_signature="sig",
            personality_prompt="prompt",
            knows_ids=[1, 2],
            is_active=True,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )
        assert resp.id == 1
        assert resp.knows_ids == [1, 2]

    def test_agent_list_response(self):
        items = [
            AgentResponse(
                id=1,
                name="Test1",
                username="user1",
                monthly_logins=30,
                personal_signature="",
                personality_prompt="",
                knows_ids=[],
                is_active=True,
                created_at=datetime.now(),
                updated_at=datetime.now(),
            )
        ]
        resp = AgentListResponse(items=items, total=1)
        assert resp.total == 1
        assert len(resp.items) == 1

    def test_agent_relation_update(self):
        update = AgentRelationUpdate(knows_ids=[1, 2], bidirectional=True)
        assert update.knows_ids == [1, 2]
        assert update.bidirectional is True


class TestModelConfigSchemas:
    def test_model_config_create(self):
        config = ModelConfigCreate(
            name="GPT-4",
            provider="openai",
            api_key="sk-xxx",
            model_name="gpt-4",
        )
        assert config.name == "GPT-4"
        assert config.provider == "openai"
        assert config.is_active is True
        assert config.max_token == 4096

    def test_model_config_update(self):
        update = ModelConfigUpdate(temperature=1.5)
        assert update.temperature == 1.5
        assert update.name is None

    def test_model_config_response(self):
        resp = ModelConfigResponse(
            id=1,
            name="GPT-4",
            provider="openai",
            base_url="",
            model_name="gpt-4",
            temperature=1.0,
            is_active=True,
            max_token=4096,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )
        assert resp.id == 1
        assert resp.provider == "openai"


class TestSystemConfigSchemas:
    def test_system_config_response(self):
        resp = SystemConfigResponse(
            id=1,
            key="TEST_KEY",
            value="test_value",
            description="Test",
            updated_at=datetime.now(),
        )
        assert resp.key == "TEST_KEY"
        assert resp.value == "test_value"

    def test_system_config_update(self):
        update = SystemConfigUpdate(value="new_value")
        assert update.value == "new_value"


class TestOperationLogSchemas:
    def test_operation_log_response(self):
        resp = OperationLogResponse(
            id=1,
            operator_id=1,
            action="create_agent",
            target_type="agent",
            target_id=1,
            details="",
            created_at=datetime.now(),
        )
        assert resp.action == "create_agent"
        assert resp.target_type == "agent"

    def test_operation_log_list_response(self):
        items = [
            OperationLogResponse(
                id=1,
                operator_id=1,
                action="test",
                target_type="test",
                target_id=None,
                details="",
                created_at=datetime.now(),
            )
        ]
        resp = OperationLogListResponse(items=items, total=1)
        assert resp.total == 1


class TestMessageResponse:
    def test_message_response(self):
        resp = MessageResponse(message="Success")
        assert resp.message == "Success"
