import pytest
from unittest.mock import patch, MagicMock

from agents.agents_scheduler.scheduler.context import (
    AgentContext,
    get_current_context,
    set_current_context,
    clear_current_context,
    get_current_token,
    get_current_user_id,
    get_current_username,
    get_current_agent_id,
)


class TestAgentContext:
    def test_agent_context_init(self):
        ctx = AgentContext(
            user_id=1,
            username="test_user",
            agent_id=100,
            token="test_token",
            user_config={"key": "value"},
        )
        assert ctx.user_id == 1
        assert ctx.username == "test_user"
        assert ctx.agent_id == 100
        assert ctx.token == "test_token"
        assert ctx.user_config == {"key": "value"}
        assert ctx.coin_balance == 0

    def test_agent_context_defaults(self):
        ctx = AgentContext()
        assert ctx.user_id is None
        assert ctx.username is None
        assert ctx.agent_id is None
        assert ctx.token is None
        assert ctx.user_config == {}
        assert ctx.coin_balance == 0

    def test_agent_context_keeps_login_coin_balance(self):
        ctx = AgentContext(coin_balance=7)

        assert ctx.coin_balance == 7


class TestThreadLocalContext:
    def test_set_and_get_context(self):
        ctx = AgentContext(user_id=1, username="test", token="token")
        set_current_context(ctx)
        result = get_current_context()
        assert result is ctx
        clear_current_context()

    def test_get_current_context_none(self):
        clear_current_context()
        result = get_current_context()
        assert result is None

    def test_get_current_token(self):
        ctx = AgentContext(token="my_token")
        set_current_context(ctx)
        assert get_current_token() == "my_token"
        clear_current_context()

    def test_get_current_token_no_context(self):
        clear_current_context()
        assert get_current_token() is None

    def test_get_current_user_id(self):
        ctx = AgentContext(user_id=42)
        set_current_context(ctx)
        assert get_current_user_id() == 42
        clear_current_context()

    def test_get_current_user_id_no_context(self):
        clear_current_context()
        assert get_current_user_id() is None

    def test_get_current_username(self):
        ctx = AgentContext(username="test_user")
        set_current_context(ctx)
        assert get_current_username() == "test_user"
        clear_current_context()

    def test_get_current_username_no_context(self):
        clear_current_context()
        assert get_current_username() is None

    def test_get_current_agent_id(self):
        ctx = AgentContext(agent_id=123)
        set_current_context(ctx)
        assert get_current_agent_id() == 123
        clear_current_context()

    def test_get_current_agent_id_no_context(self):
        clear_current_context()
        assert get_current_agent_id() is None

    def test_clear_current_context(self):
        ctx = AgentContext(user_id=1)
        set_current_context(ctx)
        clear_current_context()
        assert get_current_context() is None
