import pytest
from agents.agents_scheduler.langgraph.tools.types import (
    ToolExecutionError,
    AuthenticationError,
    NotFoundError,
    ValidationError,
    UnauthorizedError,
    ToolResult,
)
from agents.agents_scheduler.langgraph.tools.utils import _truncate


class TestToolErrorTypes:
    def test_tool_execution_error_is_exception(self):
        assert issubclass(ToolExecutionError, Exception)

    def test_authentication_error_inherits_from_tool_execution_error(self):
        assert issubclass(AuthenticationError, ToolExecutionError)

    def test_not_found_error_inherits_from_tool_execution_error(self):
        assert issubclass(NotFoundError, ToolExecutionError)

    def test_validation_error_inherits_from_tool_execution_error(self):
        assert issubclass(ValidationError, ToolExecutionError)

    def test_unauthorized_error_inherits_from_tool_execution_error(self):
        assert issubclass(UnauthorizedError, ToolExecutionError)

    def test_raise_and_catch_authentication_error(self):
        with pytest.raises(ToolExecutionError):
            raise AuthenticationError("认证失败")

    def test_raise_and_catch_not_found_error(self):
        with pytest.raises(ToolExecutionError):
            raise NotFoundError("资源不存在")

    def test_catch_specific_error_types(self):
        with pytest.raises(AuthenticationError):
            raise AuthenticationError("token expired")

        with pytest.raises(NotFoundError):
            raise NotFoundError("not found")

        with pytest.raises(ValidationError):
            raise ValidationError("invalid param")

        with pytest.raises(UnauthorizedError):
            raise UnauthorizedError("unauthorized")


class TestToolResult:
    def test_tool_result_basic_structure(self):
        result = ToolResult(action="test action", data={"key": "value"})
        assert result["action"] == "test action"
        assert result["data"] == {"key": "value"}

    def test_tool_result_empty_data(self):
        result = ToolResult(action="empty action", data={})
        assert result["action"] == "empty action"
        assert result["data"] == {}

    def test_tool_result_with_complex_data(self):
        result = ToolResult(
            action="viewed profile",
            data={"user": {"id": 1, "name": "test"}, "posts": []}
        )
        assert result["data"]["user"]["id"] == 1

    def test_tool_result_action_is_string(self):
        result = ToolResult(action="", data={})
        assert isinstance(result["action"], str)

    def test_tool_result_data_is_dict(self):
        result = ToolResult(action="test", data={})
        assert isinstance(result["data"], dict)


class TestTruncate:
    def test_truncate_short_text(self):
        assert _truncate("hello") == "hello"

    def test_truncate_long_text(self):
        text = "x" * 200
        result = _truncate(text, max_len=100)
        assert len(result) == 103  # 100 chars + "..."
        assert result.endswith("...")

    def test_truncate_empty_text(self):
        assert _truncate("") == ""

    def test_truncate_none_text(self):
        assert _truncate(None) == ""

    def test_truncate_exact_length(self):
        text = "x" * 100
        result = _truncate(text, max_len=100)
        assert result == text

    def test_truncate_one_over_length(self):
        text = "x" * 101
        result = _truncate(text, max_len=100)
        assert result == "x" * 100 + "..."

    def test_truncate_custom_max_len(self):
        text = "hello world"
        result = _truncate(text, max_len=5)
        assert result == "hello..."
