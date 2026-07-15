import pytest
from unittest.mock import patch, MagicMock
import threading
import builtins
import sys
import types
from typing import Any

from agents.agents_scheduler.langgraph.executor import (
    ExecutionResult,
    SessionExecutor,
    LLMRegistry,
    reload_llm_registry,
    create_llm_invoker,
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
            "agent_id": 1,
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
            "agent_id": 1,
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
                agent_id=1,
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
                agent_id=1,
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
                agent_id=1,
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
                agent_id=1,
                personality_prompt="prompt",
                personal_signature="sig",
            )

            mock_graph = MagicMock()
            mock_graph.invoke.return_value = {
                "user_id": 1,
                "username": "test_user",
                "name": "Test",
                "agent_id": 1,
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

    def test_executor_run_with_summarize_llm_invoker(self):
        """测试 executor.run 能正确传递 summarize_llm_invoker"""
        with patch("agents.agents_scheduler.langgraph.executor.get_default_config") as mock_config:
            mock_config.return_value = SessionConfig()
            executor = SessionExecutor(
                user_id=1,
                username="test_user",
                agent_id=1,
                personality_prompt="prompt",
                personal_signature="sig",
            )

            mock_graph = MagicMock()
            mock_graph.invoke.return_value = {
                "user_id": 1,
                "username": "test_user",
                "name": "Test",
                "agent_id": 1,
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

            mock_llm_invoker = MagicMock()
            mock_summarize_llm_invoker = MagicMock()

            with patch("agents.agents_scheduler.langgraph.executor.build_session_graph", return_value=mock_graph) as mock_build:
                result = executor.run(
                    llm_invoker=mock_llm_invoker,
                    summarize_llm_invoker=mock_summarize_llm_invoker
                )

                # 验证 build_session_graph 接收了两个 invoker
                mock_build.assert_called_once()
                call_kwargs = mock_build.call_args[1]
                assert "summarize_llm_invoker" in call_kwargs
                assert call_kwargs["summarize_llm_invoker"] is mock_summarize_llm_invoker

                assert result.success is True

    def test_executor_run_reports_error_exit_as_failure(self):
        """测试图以错误原因结束时执行结果标记为失败。"""
        with patch("agents.agents_scheduler.langgraph.executor.get_default_config") as mock_config:
            mock_config.return_value = SessionConfig()
            executor = SessionExecutor(
                user_id=1,
                username="test_user",
                agent_id=1,
                personality_prompt="prompt",
                personal_signature="sig",
            )
            final_state = {
                **executor.initial_state,
                "exit_reason": ExitReason.ERROR,
                "last_error": "LLM 决策失败: timeout",
                "summary": "会话因错误结束。",
            }
            mock_graph = MagicMock()
            mock_graph.invoke.return_value = final_state

            with patch("agents.agents_scheduler.langgraph.executor.build_session_graph", return_value=mock_graph):
                result = executor.run(llm_invoker=MagicMock())

        assert result.success is False
        assert result.error_message == "LLM 决策失败: timeout"
        assert result.final_state is final_state

    def test_executor_summary_maps_action_record_fields(self):
        """测试 executor 输出摘要时保留节点记录的真实动作与视野总结。"""
        with patch("agents.agents_scheduler.langgraph.executor.get_default_config") as mock_config:
            mock_config.return_value = SessionConfig()
            executor = SessionExecutor(
                user_id=1,
                username="test_user",
                agent_id=1,
                personality_prompt="prompt",
                personal_signature="sig",
            )

            mock_graph = MagicMock()
            mock_graph.invoke.return_value = {
                "user_id": 1,
                "username": "test_user",
                "name": "Test",
                "agent_id": 1,
                "personality_prompt": "prompt",
                "personal_signature": "sig",
                "step_count": 1,
                "max_steps": 10,
                "exit_reason": ExitReason.USER_CHOICE,
                "action_history": [
                    {
                        "step": 1,
                        "timestamp": "2024-01-01T00:00:00",
                        "summary": "我看到了主页信息流",
                        "action": "浏览了主页信息流",
                        "reason": "先了解平台动态",
                    }
                ],
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

            assert result.summary is not None
            action = result.summary["actions"][0]
            assert action["tool_name"] == "浏览了主页信息流"
            assert action["result_summary"] == "我看到了主页信息流"
            assert action["action"] == "浏览了主页信息流"
            assert action["summary"] == "我看到了主页信息流"

    def test_executor_run_failure(self):
        with patch("agents.agents_scheduler.langgraph.executor.get_default_config") as mock_config:
            mock_config.return_value = SessionConfig()
            executor = SessionExecutor(
                user_id=1,
                username="test_user",
                agent_id=1,
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
                agent_id=1,
                personality_prompt="prompt",
                personal_signature="sig",
            )
            repr_str = repr(executor)
            assert "SessionExecutor" in repr_str
            assert "test_user" in repr_str


class TestCreateLLMInvoker:
    def test_openai_provider_requires_openai_package(self, monkeypatch):
        """OpenAI provider 缺少 langchain-openai 时，应抛出明确的导入错误。"""
        fake_anthropic_module = types.ModuleType("langchain_anthropic")
        fake_anthropic_module.ChatAnthropic = MagicMock()
        monkeypatch.setitem(sys.modules, "langchain_anthropic", fake_anthropic_module)
        monkeypatch.delitem(sys.modules, "langchain_openai", raising=False)

        real_import = builtins.__import__

        def fake_import(
            name: str,
            globals: dict[str, Any] | None = None,
            locals: dict[str, Any] | None = None,
            fromlist: tuple[str, ...] = (),
            level: int = 0,
        ) -> Any:
            """模拟 langchain-openai 缺失，其余导入保持真实行为。"""
            if name == "langchain_openai":
                raise ImportError("No module named 'langchain_openai'")
            return real_import(name, globals, locals, fromlist, level)

        monkeypatch.setattr(builtins, "__import__", fake_import)

        config = SessionConfig(
            llm_provider="openai",
            openai_api_key="test_key",
            openai_model_name="gpt-test",
        )

        with pytest.raises(ImportError, match="langchain-openai"):
            create_llm_invoker(config)


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
