import pytest
from unittest.mock import patch, MagicMock
import threading

from agents.agents_scheduler.langgraph.executor import (
    ExecutionResult,
    SessionExecutor,
    LLMRegistry,
    reload_llm_registry,
)
from agents.agents_scheduler.langgraph.state import SessionState, ExitReason, SessionSummary
from agents.agents_scheduler.langgraph.config import SessionConfig


class TestExecutionResult:
    def test_execution_result_basic(self):
        from datetime import datetime
        start = datetime.now()
        end = datetime.now()

        state: SessionState = {
            "user_id": 1,
            "username": "test_user",
            "name": "Test",
            "ai_config_id": 1,
            "personality_prompt": "prompt",
            "personal_signature": "sig",
            "step_count": 5,
            "max_steps": 10,
            "exit_reason": ExitReason.USER_CHOICE,
            "action_history": [],
            "current_location": "主页（信息流）",
            "last_tool_result": None,
            "pending_tool": None,
            "pending_tools": None,
            "last_error": None,
            "summary": None,
            "recalled_memories": "",
        }

        result = ExecutionResult(
            session_id="test-session",
            success=True,
            final_state=state,
            summary=None,
            error_message=None,
            start_time=start,
            end_time=end,
            duration_seconds=60.0,
        )
        assert result.session_id == "test-session"
        assert result.success is True
        assert result.step_count == 5
        assert result.exit_reason == "user_choice"

    def test_execution_result_error(self):
        from datetime import datetime
        start = datetime.now()
        end = datetime.now()

        state: SessionState = {
            "user_id": 1,
            "username": "test_user",
            "name": "Test",
            "ai_config_id": 1,
            "personality_prompt": "prompt",
            "personal_signature": "sig",
            "step_count": 0,
            "max_steps": 10,
            "exit_reason": None,
            "action_history": [],
            "current_location": "主页（信息流）",
            "last_tool_result": None,
            "pending_tool": None,
            "pending_tools": None,
            "last_error": None,
            "summary": None,
            "recalled_memories": "",
        }

        result = ExecutionResult(
            session_id="test-session",
            success=False,
            final_state=state,
            summary=None,
            error_message="Test error",
            start_time=start,
            end_time=end,
            duration_seconds=10.0,
        )
        assert result.success is False
        assert result.error_message == "Test error"
        assert result.exit_reason is None


class TestSessionExecutor:
    def test_executor_init(self):
        with patch("agents.agents_scheduler.langgraph.executor.get_default_config") as mock_config:
            mock_config.return_value = SessionConfig()
            executor = SessionExecutor(
                user_id=1,
                username="test_user",
                ai_config_id=1,
                personality_prompt="prompt",
                personal_signature="sig",
            )
            assert executor.username == "test_user"
            assert executor.config is not None
            assert executor.session_id is not None

    def test_executor_init_with_name(self):
        with patch("agents.agents_scheduler.langgraph.executor.get_default_config") as mock_config:
            mock_config.return_value = SessionConfig()
            executor = SessionExecutor(
                user_id=1,
                username="test_user",
                ai_config_id=1,
                personality_prompt="prompt",
                personal_signature="sig",
                name="DisplayName",
            )
            assert executor.name == "DisplayName"

    def test_executor_init_default_name(self):
        with patch("agents.agents_scheduler.langgraph.executor.get_default_config") as mock_config:
            mock_config.return_value = SessionConfig()
            executor = SessionExecutor(
                user_id=1,
                username="test_user",
                ai_config_id=1,
                personality_prompt="prompt",
                personal_signature="sig",
            )
            assert executor.name == "test_user"

    def test_executor_run_success(self):
        with patch("agents.agents_scheduler.langgraph.executor.get_default_config") as mock_config:
            mock_config.return_value = SessionConfig()
            executor = SessionExecutor(
                user_id=1,
                username="test_user",
                ai_config_id=1,
                personality_prompt="prompt",
                personal_signature="sig",
            )

            mock_graph = MagicMock()
            mock_graph.invoke.return_value = {
                "user_id": 1,
                "username": "test_user",
                "name": "Test",
                "ai_config_id": 1,
                "personality_prompt": "prompt",
                "personal_signature": "sig",
                "step_count": 5,
                "max_steps": 10,
                "exit_reason": ExitReason.USER_CHOICE,
                "action_history": [],
                "current_location": "主页（信息流）",
                "last_tool_result": None,
                "pending_tool": None,
                "pending_tools": None,
                "last_error": None,
                "summary": "Test summary",
                "recalled_memories": "",
            }

            with patch("agents.agents_scheduler.langgraph.executor.build_session_graph", return_value=mock_graph):
                result = executor.run(llm_invoker=MagicMock())
                assert result.success is True
                assert result.error_message is None

    def test_executor_run_failure(self):
        with patch("agents.agents_scheduler.langgraph.executor.get_default_config") as mock_config:
            mock_config.return_value = SessionConfig()
            executor = SessionExecutor(
                user_id=1,
                username="test_user",
                ai_config_id=1,
                personality_prompt="prompt",
                personal_signature="sig",
            )

            with patch("agents.agents_scheduler.langgraph.executor.build_session_graph", side_effect=Exception("Test error")):
                result = executor.run(llm_invoker=MagicMock())
                assert result.success is False
                assert result.error_message is not None

    def test_executor_repr(self):
        with patch("agents.agents_scheduler.langgraph.executor.get_default_config") as mock_config:
            mock_config.return_value = SessionConfig(max_steps=20)
            executor = SessionExecutor(
                user_id=1,
                username="test_user",
                ai_config_id=1,
                personality_prompt="prompt",
                personal_signature="sig",
            )
            repr_str = repr(executor)
            assert "SessionExecutor" in repr_str
            assert "test_user" in repr_str


class TestLLMRegistry:
    def test_get_invoker_cache(self):
        config = SessionConfig(
            llm_provider="openai",
            openai_api_key="test_key",
            openai_model_name="gpt-4",
            temperature=1.0,
        )
        LLMRegistry.clear_cache()

        with patch("agents.agents_scheduler.langgraph.executor.create_llm_invoker") as mock_invoker:
            mock_invoker.return_value = MagicMock()
            invoker1 = LLMRegistry.get_invoker(config)
            invoker2 = LLMRegistry.get_invoker(config)
            assert invoker1 is invoker2
            assert mock_invoker.call_count == 1

    def test_clear_cache(self):
        config = SessionConfig(
            llm_provider="openai",
            openai_api_key="test_key",
            openai_model_name="gpt-4",
            temperature=1.0,
        )
        LLMRegistry.clear_cache()

        with patch("agents.agents_scheduler.langgraph.executor.create_llm_invoker") as mock_invoker:
            mock_invoker.return_value = MagicMock()
            LLMRegistry.get_invoker(config)
            LLMRegistry.clear_cache()
            LLMRegistry.get_invoker(config)
            assert mock_invoker.call_count == 2

    def test_reload_llm_registry(self):
        reload_llm_registry()
        assert len(LLMRegistry._cache) == 0
