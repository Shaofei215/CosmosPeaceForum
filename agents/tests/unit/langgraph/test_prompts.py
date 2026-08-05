import json
from unittest.mock import patch

import pytest

from agents.agents_scheduler.langgraph import prompts as prompt_module
from agents.agents_scheduler.langgraph.prompts import (
    build_system_prompt,
    build_decision_prompt,
    build_summarize_system_prompt,
    build_summarize_prompt,
    _format_tool_result,
)
from agents.agents_scheduler.scheduler.context import (
    clear_current_context,
)
from agents.prompt_templates import PROMPT_TEMPLATE_DEFINITIONS, get_default_prompt_template


@pytest.fixture(autouse=True)
def use_default_prompt_templates(monkeypatch: pytest.MonkeyPatch) -> None:
    """固定使用内置模板，避免本地管理数据库配置污染 Prompt 单测。"""

    monkeypatch.setattr(
        prompt_module,
        "_get_configured_prompt_template",
        get_default_prompt_template,
    )


def test_default_prompt_templates_use_markdown_layout():
    """默认提示词统一使用 Markdown 排版，不再混用方头括号标题。"""

    for definition in PROMPT_TEMPLATE_DEFINITIONS:
        assert "## " in definition.default_value
        assert "【" not in definition.default_value
        assert "】" not in definition.default_value


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
        assert "角色设定" in prompt
        assert "平台个人签名" in prompt
        assert "决策核心" in prompt
        assert "工作记忆" in prompt
        assert "登出" in prompt

    def test_build_system_prompt_contains_guidelines(self):
        prompt = build_system_prompt(
            username="user1",
            name="Alice",
            personality_prompt="friendly",
            personal_signature="hello"
        )
        assert "先成为角色，再决定行动" in prompt
        assert "以自身生活和职责为中心" in prompt
        assert "互动应产生新东西" in prompt
        assert "事实与边界" in prompt

    def test_build_system_prompt_with_session_prompt_injection(self):
        prompt = build_system_prompt(
            username="test_user",
            name="Test",
            personality_prompt="friendly",
            personal_signature="sig",
            session_prompt_injection="今天重点关注活动通知",
        )
        assert "本次临时关注" in prompt
        assert "今天重点关注活动通知" in prompt
        assert (
            prompt.index("## 平台个人签名")
            < prompt.index("## 短期记忆")
            < prompt.index("## 本次临时关注")
            < prompt.index("## 决策核心")
        )

    def test_build_system_prompt_injects_current_short_term_memory_with_scaled_age(self):
        """当前快照应按更新时间与登录次数稳定注入，并优先于临时提示。"""

        with patch(
            "agents.agents_scheduler.short_term_memory.clock.describe_short_term_memory_age",
            return_value="3天前",
        ):
            prompt = build_system_prompt(
                username="observer",
                name="观察者",
                personality_prompt="持续观察社区规范",
                personal_signature="记录变化",
                session_prompt_injection="今天查看新投票",
                short_term_memory="# 社区观察手记\n\n下一篇关注 AI 创作署名争论。",
                short_term_memory_revision=5,
                short_term_memory_updated_at=500.0,
                short_term_memory_updated_login_count=12,
            )

        assert "你在3天前，第12次登录时更新了短期记忆" in prompt
        assert "下一篇关注 AI 创作署名争论" in prompt
        assert "发生冲突时" in prompt
        assert "当前短期记忆为准" in prompt
        assert (
            prompt.index("## 平台个人签名")
            < prompt.index("## 短期记忆")
            < prompt.index("## 本次临时关注")
            < prompt.index("## 决策核心")
            < prompt.index("## 工作记忆")
        )

    def test_build_system_prompt_keeps_explicit_empty_short_term_memory_state(self):
        """新角色也必须知道短期记忆存在并可开始建立。"""

        prompt = build_system_prompt("new", "新人", "好奇", "你好")

        assert "## 短期记忆" in prompt
        assert "目前还没有建立短期记忆" in prompt
        assert "edit_short_term_memory" in prompt

    def test_build_system_prompt_uses_product_labels_without_duplicate_queries(self):
        with patch(
            "agents.agents_scheduler.langgraph.tools.support.shared_platform.get_notification_summary",
            return_value={
                "following_count": 1,
                "followers_count": 2,
                "unread_count": 3,
            },
        ) as summary_mock, patch(
            "agents.agents_scheduler.langgraph.tools.support.shared_platform.get_hot_topics",
            return_value=[{"title": "第一条热榜"}],
        ) as hot_topics_mock, patch(
            "agents.agents_scheduler.langgraph.tools.support.shared_platform.get_trending_topics",
            return_value=[{"name": "示例话题"}],
        ) as topics_mock, patch(
            "agents.agents_scheduler.langgraph.prompts._build_login_stats_summary",
            return_value={"total_login_count": 0, "last_login_timestamp": None},
        ):
            prompt = build_system_prompt(
                username="test_user",
                name="Test",
                personality_prompt="friendly",
                personal_signature="sig",
            )

        context_text = prompt.split("## 当前账号状态\n", 1)[1].split("\n\n你是", 1)[0]
        assert json.loads(context_text) == {
            "platform_user_id": "unknown",
            "coin_balance": 0,
            "关注": 1,
            "被关注": 2,
            "消息": 3,
            "大家都在聊": ["第一条热榜"],
            "话题": ["示例话题"],
        }
        summary_mock.assert_called_once_with()
        hot_topics_mock.assert_called_once_with(limit=8)
        topics_mock.assert_called_once_with(limit=8)


class TestBuildDecisionPrompt:
    def teardown_method(self):
        clear_current_context()

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
        assert "This is first decision in this session" in prompt
        assert '"step_count": 0' in prompt
        assert '"action_history": []' in prompt

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
        assert "action_history" in prompt
        assert '"step": 1' in prompt
        assert '"summary": "看到了有趣帖子"' in prompt
        assert '"action": "点赞了帖子"' in prompt
        assert '"reason": "帖子很有趣"' in prompt
        assert "Platform content obtained after last tool call" in prompt

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
        assert '"step_count": 5' in prompt
        assert '"remaining_steps": 5' in prompt

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
        assert '"step": 1' in prompt
        assert '"summary": "s1"' in prompt
        assert '"action": "a1"' in prompt
        assert '"reason": "r1"' in prompt
        assert '"step": 2' in prompt
        assert '"summary": "s2"' in prompt
        assert '"action": "a2"' in prompt
        assert '"reason": "r2"' in prompt
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
