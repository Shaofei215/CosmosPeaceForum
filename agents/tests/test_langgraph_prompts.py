import json

import pytest
from unittest.mock import patch, MagicMock

from agents.agents_scheduler.langgraph.prompts import (
    build_system_prompt,
    build_decision_prompt,
    build_summarize_system_prompt,
    build_summarize_prompt,
    _format_tool_result,
    _build_attention_header,
)
from agents.agents_scheduler.scheduler.context import (
    AgentContext,
    clear_current_context,
    set_current_context,
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

    def test_build_system_prompt_with_session_prompt_injection(self):
        prompt = build_system_prompt(
            username="test_user",
            name="Test",
            personality_prompt="friendly",
            personal_signature="sig",
            session_prompt_injection="今天重点关注活动通知",
        )
        assert "临时提示词注入" in prompt
        assert "今天重点关注活动通知" in prompt
        assert prompt.index("个人签名") < prompt.index("临时提示词注入") < prompt.index("行为准则")

    def test_build_system_prompt_renders_hot_topics_through_template(self):
        with patch(
            "agents.agents_scheduler.langgraph.prompts._get_configured_prompt_template",
            return_value="账号状态\n大家都在聊：{hot_topic_titles}",
        ), patch(
            "agents.agents_scheduler.langgraph.tools.support.platform._get_notification_summary",
            return_value={
                "following_count": 0,
                "followers_count": 0,
                "unread_count": 0,
            },
        ), patch(
            "agents.agents_scheduler.langgraph.tools.support.platform._get_hot_topics",
            return_value=[
                {"title": "第一条热榜"},
                {"title": "第二条热榜"},
            ],
        ):
            prompt = build_system_prompt(
                username="test_user",
                name="Test",
                personality_prompt="friendly",
                personal_signature="sig",
            )

        assert prompt == "账号状态\n大家都在聊：1. 第一条热榜；2. 第二条热榜"


class TestBuildDecisionPrompt:
    def teardown_method(self):
        clear_current_context()

    def test_attention_header_includes_login_stats(self):
        set_current_context(AgentContext(user_config={
            "total_login_count": 3,
            "previous_last_login_timestamp": 60.0,
        }))

        mock_time_system = MagicMock()
        mock_time_system.get_scaled_timestamp.return_value = 3600.0

        with patch(
            "agents.agents_scheduler.langgraph.tools.support.platform._get_notification_summary",
            return_value={
                "following_count": 1,
                "followers_count": 2,
                "unread_count": 3,
            },
        ), patch(
            "agents.agents_scheduler.memory.utils.get_time_system",
            return_value=mock_time_system,
        ):
            header = _build_attention_header()

        assert "关注：1" in header
        assert "被关注：2" in header
        assert "消息：3" in header
        assert "总登录：3" in header
        assert "上次登录：" in header

    def test_attention_header_includes_hot_topic_titles(self):
        topics = [{"title": f"热榜{i}", "rank": i} for i in range(1, 10)]
        with patch(
            "agents.agents_scheduler.langgraph.tools.support.platform._get_notification_summary",
            return_value={
                "following_count": 0,
                "followers_count": 0,
                "unread_count": 0,
            },
        ), patch(
            "agents.agents_scheduler.langgraph.tools.support.platform._get_hot_topics",
            return_value=topics,
        ):
            header = _build_attention_header()

        assert "大家都在聊：1. 热榜1" in header
        assert "8. 热榜8" in header
        assert "热榜9" not in header

    def test_attention_header_includes_trending_topic_titles(self):
        topics = [{"name": f"话题{i}"} for i in range(1, 10)]
        with patch(
            "agents.agents_scheduler.langgraph.tools.support.platform._get_notification_summary",
            return_value={
                "following_count": 0,
                "followers_count": 0,
                "unread_count": 0,
            },
        ), patch(
            "agents.agents_scheduler.langgraph.tools.support.platform._get_hot_topics",
            return_value=[],
        ), patch(
            "agents.agents_scheduler.langgraph.tools.support.platform._get_trending_topics",
            return_value=topics,
        ):
            header = _build_attention_header()

        assert "话题：#话题1#" in header
        assert "#话题8#" in header
        assert "话题9" not in header

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
        assert "你进行到了第 1 step，你看到了：s1，你 a1，原因是：r1" in prompt
        assert "你进行到了第 2 step，你看到了：s2，你 a2，原因是：r2" in prompt
        assert "基于以上记忆，继续做出你的下一步决策" not in prompt
        assert "本次会话工具调用统计" not in prompt
        assert "记忆写入指令" in prompt


class TestFormatToolResult:
    def test_serializes_json_scalars(self):
        assert json.loads(_format_tool_result(None)) is None
        assert json.loads(_format_tool_result("hello")) == "hello"
        assert json.loads(_format_tool_result([])) == []

    def test_preserves_complete_shared_tool_result(self):
        result = {
            "posts": [
                {
                    "id": 1,
                    "author_username": "test_user",
                    "created_by_agent": True,
                    "poll": {
                        "post_id": 1,
                        "options": [{"id": 11, "text": "选项一"}],
                    },
                    "repost_chain": [{"id": 2}],
                }
            ],
            "unread_count": 3,
        }

        assert json.loads(_format_tool_result(result)) == result
    def test_does_not_truncate_unknown_or_long_fields(self):
        result = {"future_field": "值" * 1000}

        assert json.loads(_format_tool_result(result)) == result

    def test_preserves_merged_page_and_recall_context(self):
        result = {
            "current_view": {"post": {"id": 1, "content": "test content"}},
            "explicit_recalls": [
                {
                    "query": "test content",
                    "memories": [{"content": "我以前见过类似内容。", "time_description": "刚刚"}],
                }
            ],
            "web_searches": [],
        }

        assert json.loads(_format_tool_result(result)) == result
