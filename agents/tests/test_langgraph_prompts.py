import pytest
from unittest.mock import patch, MagicMock

from agents.agents_scheduler.langgraph.prompts import (
    build_system_prompt,
    build_decision_prompt,
    build_summarize_system_prompt,
    build_summarize_prompt,
    _format_tool_result,
)


class TestBuildSystemPrompt:
    def test_build_system_prompt_basic(self):
        prompt = build_system_prompt(
            username="test_user",
            name="Test",
            personality_prompt="You are a test user",
            personal_signature="Test signature"
        )
        assert "Test" in prompt
        assert "test_user" in prompt
        assert "You are a test user" in prompt
        assert "Test signature" in prompt

    def test_build_system_prompt_contains_role(self):
        prompt = build_system_prompt(
            username="user1",
            name="Alice",
            personality_prompt="friendly",
            personal_signature="hello"
        )
        assert "角色背景" in prompt
        assert "行为准则" in prompt
        assert "工作记忆" in prompt
        assert "登出决策" in prompt

    def test_build_system_prompt_contains_guidelines(self):
        prompt = build_system_prompt(
            username="user1",
            name="Alice",
            personality_prompt="friendly",
            personal_signature="hello"
        )
        assert "保持角色一致性" in prompt
        assert "真实性" in prompt
        assert "选择性" in prompt


class TestBuildDecisionPrompt:
    def test_build_decision_prompt_first_decision(self):
        state = {
            "step_count": 0,
            "max_steps": 10,
            "current_location": "主页（信息流）",
            "action_history": [],
            "last_tool_result": None,
            "recalled_memories": "",
        }
        prompt = build_decision_prompt(state)
        assert "本次会话的开始" in prompt
        assert "get_global_feed" in prompt
        assert "已执行: 0 步" in prompt

    def test_build_decision_prompt_with_history(self):
        state = {
            "step_count": 2,
            "max_steps": 10,
            "current_location": "帖子详情页",
            "action_history": [
                {
                    "step": 1,
                    "summary": "看到了有趣帖子",
                    "action": "点赞了帖子",
                    "reason": "帖子很有趣",
                }
            ],
            "last_tool_result": {"post": {"content": "test"}},
            "recalled_memories": "",
        }
        prompt = build_decision_prompt(state)
        assert "工作记忆" in prompt
        assert "第 1 step" in prompt
        assert "上一步执行后当前查看的内容" in prompt

    def test_build_decision_prompt_remaining_steps(self):
        state = {
            "step_count": 5,
            "max_steps": 10,
            "current_location": "主页（信息流）",
            "action_history": [],
            "last_tool_result": None,
            "recalled_memories": "",
        }
        prompt = build_decision_prompt(state)
        assert "已执行: 5 步" in prompt

    def test_build_decision_prompt_with_memories(self):
        state = {
            "step_count": 1,
            "max_steps": 10,
            "current_location": "主页（信息流）",
            "action_history": [],
            "last_tool_result": None,
            "recalled_memories": "\n\n## 相关记忆\n[记忆片段]\n内容\n---",
        }
        prompt = build_decision_prompt(state)
        assert "相关记忆" in prompt


class TestBuildSummarizePrompt:
    def test_build_summarize_system_prompt(self):
        prompt = build_summarize_system_prompt(
            username="test_user",
            name="Test",
            personality_prompt="friendly",
            personal_signature="sig"
        )
        assert "Test" in prompt
        assert "test_user" in prompt

    def test_build_summarize_system_prompt_same_as_system(self):
        prompt1 = build_summarize_system_prompt("u", "n", "p", "s")
        prompt2 = build_system_prompt("u", "n", "p", "s")
        assert prompt1 == prompt2

    def test_build_summarize_prompt_no_history(self):
        state = {"username": "test_user", "action_history": []}
        prompt = build_summarize_prompt(state)
        assert "未执行任何操作" in prompt

    def test_build_summarize_prompt_with_history(self):
        state = {
            "username": "test_user",
            "action_history": [
                {
                    "step": 1,
                    "summary": "s1",
                    "action": "a1",
                    "reason": "r1",
                },
                {
                    "step": 2,
                    "summary": "s2",
                    "action": "a2",
                    "reason": "r2",
                },
            ],
        }
        prompt = build_summarize_prompt(state)
        assert "第 1 step" in prompt
        assert "第 2 step" in prompt
        assert "记忆写入指令" in prompt


class TestFormatToolResult:
    def test_format_none(self):
        assert _format_tool_result(None) == "无"

    def test_format_string(self):
        assert _format_tool_result("hello") == "hello"

    def test_format_empty_list(self):
        assert _format_tool_result([]) == "空列表"

    def test_format_post_result(self):
        result = {
            "post": {
                "id": 1,
                "author_username": "test_user",
                "author_bio": "bio",
                "content": "test content",
                "like_count": 5,
                "comment_count": 2,
                "is_liked": False,
                "created_at": "2024-01-01",
            },
            "comments": [],
            "total": 0,
        }
        formatted = _format_tool_result(result)
        assert "帖子详情" in formatted
        assert "test_user" in formatted
        assert "test content" in formatted

    def test_format_user_result(self):
        result = {
            "user_id": 1,
            "username": "test_user",
            "bio": "bio",
            "followers_count": 10,
            "following_count": 5,
        }
        formatted = _format_tool_result(result)
        assert "用户信息" in formatted
        assert "test_user" in formatted

    def test_format_list_with_items(self):
        result = [
            {"id": 1, "author_username": "user1", "content": "test1", "like_count": 1, "comment_count": 0, "is_liked": False, "author_id": 1},
            {"id": 2, "author_username": "user2", "content": "test2", "like_count": 2, "comment_count": 1, "is_liked": True, "author_id": 2},
        ]
        formatted = _format_tool_result({"data": result})
        assert "【信息列表】" in formatted
        assert "user1" in formatted

    def test_format_truncation(self):
        # Strings are returned as-is, truncation only applies to dict formatting
        long_string = "x" * 600
        formatted = _format_tool_result(long_string)
        assert len(formatted) == 600

    def test_format_dict_truncation(self):
        result = {"some_key": "some_value" * 100}
        formatted = _format_tool_result(result)
        assert len(formatted) <= 500

    def test_format_post_result_includes_repost_count(self):
        result = {
            "post": {
                "id": 1,
                "author_username": "test_user",
                "author_bio": "bio",
                "content": "test content",
                "like_count": 5,
                "comment_count": 2,
                "repost_count": 3,
                "is_liked": False,
                "created_at": "2024-01-01",
            },
            "comments": [],
            "total": 0,
        }
        formatted = _format_tool_result(result)
        assert "repost_count / repost count: 3" in formatted
