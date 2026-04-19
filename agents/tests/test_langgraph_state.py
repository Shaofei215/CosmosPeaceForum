import pytest
from unittest.mock import patch, MagicMock, PropertyMock
from datetime import datetime

from agents.agents_scheduler.langgraph.state import SessionState, SessionSummary, ExitReason, ActionRecord


class TestExitReason:
    def test_exit_reason_values(self):
        assert ExitReason.USER_CHOICE.value == "user_choice"
        assert ExitReason.MAX_STEPS_REACHED.value == "max_steps"
        assert ExitReason.ERROR.value == "error"

    def test_exit_reason_is_string(self):
        assert isinstance(ExitReason.USER_CHOICE, str)
        assert isinstance(ExitReason.MAX_STEPS_REACHED, str)
        assert isinstance(ExitReason.ERROR, str)

    def test_exit_reason_comparison(self):
        reason = ExitReason.USER_CHOICE
        assert reason == "user_choice"
        assert reason.value == "user_choice"


class TestActionRecord:
    def test_action_record_typed_dict(self):
        record: ActionRecord = {
            "step": 1,
            "timestamp": "2024-01-01T00:00:00",
            "summary": "test summary",
            "action": "test action",
            "reason": "test reason",
        }
        assert record["step"] == 1
        assert record["timestamp"] == "2024-01-01T00:00:00"
        assert record["summary"] == "test summary"
        assert record["action"] == "test action"
        assert record["reason"] == "test reason"

    def test_action_record_all_fields(self):
        record: ActionRecord = {
            "step": 5,
            "timestamp": "2024-06-15T10:30:00",
            "summary": "我看到了一个有趣的帖子",
            "action": "点赞了 @user 的帖子",
            "reason": "帖子内容很有趣",
        }
        assert isinstance(record["step"], int)
        assert isinstance(record["timestamp"], str)
        assert isinstance(record["summary"], str)
        assert isinstance(record["action"], str)
        assert isinstance(record["reason"], str)


class TestSessionState:
    def test_session_state_typed_dict(self):
        state: SessionState = {
            "user_id": 1,
            "username": "test_user",
            "name": "Test",
            "ai_config_id": 1,
            "personality_prompt": "You are a test user",
            "personal_signature": "Test signature",
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
        assert state["user_id"] == 1
        assert state["username"] == "test_user"
        assert state["step_count"] == 0
        assert state["max_steps"] == 10
        assert state["exit_reason"] is None
        assert len(state["action_history"]) == 0
        assert state["current_location"] == "主页（信息流）"

    def test_session_state_with_values(self):
        state: SessionState = {
            "user_id": 42,
            "username": "test_user",
            "name": "Test",
            "ai_config_id": 1,
            "personality_prompt": "prompt",
            "personal_signature": "sig",
            "step_count": 5,
            "max_steps": 20,
            "exit_reason": ExitReason.USER_CHOICE,
            "action_history": [{"step": 1, "timestamp": "2024-01-01", "summary": "s", "action": "a", "reason": "r"}],
            "current_location": "帖子详情页",
            "last_tool_result": {"data": "test"},
            "pending_tool": None,
            "pending_tools": None,
            "last_error": None,
            "summary": "Test summary",
            "recalled_memories": "",
        }
        assert state["step_count"] == 5
        assert state["exit_reason"] == ExitReason.USER_CHOICE
        assert len(state["action_history"]) == 1
        assert state["summary"] == "Test summary"


class TestSessionSummary:
    def test_session_summary_typed_dict(self):
        summary: SessionSummary = {
            "session_id": "test-session-id",
            "user_id": 1,
            "username": "test_user",
            "ai_config_id": 1,
            "start_time": "2024-01-01T00:00:00",
            "end_time": "2024-01-01T01:00:00",
            "duration_seconds": 3600.0,
            "step_count": 10,
            "exit_reason": "user_choice",
            "actions": [{"step": 1, "tool_name": "test", "reason": "test", "result_summary": "test"}],
            "narrative": "Test narrative",
        }
        assert summary["session_id"] == "test-session-id"
        assert summary["user_id"] == 1
        assert summary["step_count"] == 10
        assert summary["exit_reason"] == "user_choice"
        assert len(summary["actions"]) == 1
        assert summary["narrative"] == "Test narrative"

    def test_session_summary_empty_actions(self):
        summary: SessionSummary = {
            "session_id": "test-session-id",
            "user_id": 1,
            "username": "test_user",
            "ai_config_id": 1,
            "start_time": "2024-01-01T00:00:00",
            "end_time": "2024-01-01T01:00:00",
            "duration_seconds": 3600.0,
            "step_count": 0,
            "exit_reason": "max_steps",
            "actions": [],
            "narrative": "No actions performed",
        }
        assert len(summary["actions"]) == 0
        assert summary["step_count"] == 0
