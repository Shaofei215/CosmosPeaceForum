"""可信 Agent 操作来源依赖测试。"""

from types import SimpleNamespace
from unittest.mock import MagicMock

from social_platform.app.api import deps
from social_platform.app.api.routers import auth
from social_platform.app.schemas.auth import InternalAgentLoginRequest, UserLogin, UserRegister
from social_platform.app.schemas.auth import AgentLoginContext


def test_agent_operation_source_requires_matching_source_and_token(monkeypatch) -> None:
    """只有固定来源值和常量时间校验通过的 ADMIN_KEY 才能标记 Agent 来源。"""

    monkeypatch.setattr(deps.get_settings(), "ADMIN_KEY", "shared-secret")

    assert deps.get_agent_operation_source("agent", "shared-secret") is True
    assert deps.get_agent_operation_source("agent", "wrong-secret") is False
    assert deps.get_agent_operation_source("browser", "shared-secret") is False
    assert deps.get_agent_operation_source(None, None) is False


def test_agent_operation_source_is_disabled_without_deployment_secret(monkeypatch) -> None:
    """平台未配置部署 Secret 时任何 Header 都不能伪造 Agent 来源。"""

    monkeypatch.setattr(deps.get_settings(), "ADMIN_KEY", "")

    assert deps.get_agent_operation_source("agent", "anything") is False


def test_admin_agent_login_uses_admin_key_without_agent_service_identity(monkeypatch) -> None:
    """管理后台进入角色账号应由 ADMIN_KEY 授权，而不是依赖 agents 服务身份。"""

    db = MagicMock()
    user = SimpleNamespace(id=7, password_hash="hashed")
    db.query.return_value.filter.return_value.first.return_value = user
    request = SimpleNamespace(headers={}, client=SimpleNamespace(host="127.0.0.1"))
    token_pair = {
        "access_token": "access",
        "refresh_token": "refresh",
        "token_type": "bearer",
        "expires_in": 900,
        "refresh_expires_in": 43200,
        "session_id": "sid",
    }
    create_session = MagicMock(return_value=token_pair)

    monkeypatch.setattr(auth, "verify_admin_key", lambda value: value == "admin-key")
    monkeypatch.setattr(auth, "verify_password", lambda plain, hashed: plain == "secret123")
    monkeypatch.setattr(auth.session_service, "create_session_token_pair", create_session)

    response = auth.admin_agent_login(
        InternalAgentLoginRequest(username="agent-name", password="secret123"),
        request,
        x_admin_key="admin-key",
        db=db,
    )

    assert response.access_token == "access"
    create_session.assert_called_once_with(
        db=db,
        account_id=7,
        scope="user",
        client_type="desktop",
        remember_me=False,
        user_agent=None,
        ip_address="127.0.0.1",
        revoke_same_client=False,
    )


def test_human_login_honors_agent_client_type(monkeypatch) -> None:
    """普通账号登录声明 client_type=agent 时应创建 agent 分组 session。"""

    db = MagicMock()
    user = SimpleNamespace(id=8, password_hash="hashed")
    db.query.return_value.filter.return_value.first.return_value = user
    request = SimpleNamespace(headers={}, client=SimpleNamespace(host="127.0.0.1"))
    token_pair = {
        "access_token": "access",
        "refresh_token": "refresh",
        "token_type": "bearer",
        "expires_in": 900,
        "refresh_expires_in": 43200,
        "session_id": "sid",
    }
    create_session = MagicMock(return_value=token_pair)

    monkeypatch.setattr(auth, "verify_password", lambda plain, hashed: plain == "secret123")
    monkeypatch.setattr(auth.session_service, "create_session_token_pair", create_session)
    agent_context = AgentLoginContext(
        platform_user_id=8,
        following_count=2,
        followers_count=3,
        unread_count=4,
        hot_topic_titles=["热榜"],
        topic_titles=["话题"],
    )
    monkeypatch.setattr(auth, "_build_agent_login_context", lambda _db, _user: agent_context)

    response = auth.login(
        UserLogin(email="agent@example.com", password="secret123", client_type="agent"),
        request,
        db=db,
    )

    assert response.access_token == "access"
    assert response.agent_context == agent_context
    create_session.assert_called_once_with(
        db=db,
        account_id=8,
        scope="user",
        client_type="agent",
        remember_me=False,
        user_agent=None,
        ip_address="127.0.0.1",
        revoke_same_client=True,
    )


def test_human_registration_detects_client_type_when_omitted(monkeypatch) -> None:
    """真人注册未声明 client_type 时应按请求信息创建 Session，不能在注册后抛异常。"""

    db = MagicMock()
    user = SimpleNamespace(id=9, username="用户_9")
    request = SimpleNamespace(
        headers={"user-agent": "Mozilla/5.0"},
        client=SimpleNamespace(host="127.0.0.1"),
    )
    token_pair = {
        "access_token": "access",
        "refresh_token": "refresh",
        "token_type": "bearer",
        "expires_in": 900,
        "refresh_expires_in": 43200,
        "session_id": "sid",
    }
    create_session = MagicMock(return_value=token_pair)

    monkeypatch.setattr(
        auth.identity_service,
        "register_human_user_with_code",
        lambda *_args, **_kwargs: user,
    )
    monkeypatch.setattr(auth.session_service, "create_session_token_pair", create_session)

    response = auth.verify_and_register(
        UserRegister(email="user@example.com", password="secret123"),
        request,
        code="123456",
        db=db,
    )

    assert response.access_token == "access"
    create_session.assert_called_once_with(
        db=db,
        account_id=9,
        scope="user",
        client_type="desktop",
        remember_me=False,
        user_agent="Mozilla/5.0",
        ip_address="127.0.0.1",
        revoke_same_client=True,
    )


def test_agent_login_context_uses_platform_state_without_login_stats(monkeypatch) -> None:
    """外部 Agent 登录上下文只返回当前平台状态，不混入未定义的登录统计。"""

    user = SimpleNamespace(id=8)
    db = MagicMock()
    monkeypatch.setattr(
        auth.notification_service,
        "get_summary",
        lambda _db, _user_id: {
            "following_count": 2,
            "followers_count": 3,
            "unread_count": 4,
        },
    )
    monkeypatch.setattr(
        auth.hot_topic_service,
        "list_public_hot_topics",
        lambda _db, limit: [SimpleNamespace(title="热榜一"), SimpleNamespace(title="热榜二")],
    )
    monkeypatch.setattr(
        auth.topic_service,
        "list_trending_topics",
        lambda _db, limit: [SimpleNamespace(name="话题一")],
    )

    context = auth._build_agent_login_context(db, user)
    payload = context.model_dump(exclude_none=True, by_alias=True)

    assert payload == {
        "platform_user_id": 8,
        "following_count": 2,
        "followers_count": 3,
        "unread_count": 4,
        "大家都在聊": ["热榜一", "热榜二"],
        "话题": ["话题一"],
    }
    assert "total_login_count" not in payload
    assert "last_login" not in payload
