"""内部 LangChain 工具描述回归测试。

内部 Agent 依赖 LangChain 从 `@tool` 函数 docstring 中提取工具用途和参数说明。
共享核心抽离时不能把这些说明压缩成一句话。
"""

from __future__ import annotations

from agents.agents_scheduler.langgraph.tools.support.registry import get_social_tools


def _description_by_name() -> dict[str, str]:
    """返回内部决策节点工具名到 LangChain 描述的映射。"""

    return {tool.name: tool.description for tool in get_social_tools()}


def test_create_comment_description_preserves_parent_id_instruction() -> None:
    """回复评论的 parent_id 规则必须继续暴露给内部 Agent。"""

    descriptions = _description_by_name()

    assert "parent_id" in descriptions["create_comment"]
    assert "必须把该评论 ID 填入 parent_id" in descriptions["create_comment"]
    assert "不要省略" in descriptions["create_comment"]


def test_scroll_description_preserves_contextual_page_rules() -> None:
    """scroll 的自动延续页面规则必须继续暴露给内部 Agent。"""

    descriptions = _description_by_name()

    assert "get_global_feed 之后继续加载主页信息流" in descriptions["scroll"]
    assert "view_post_comments 之后继续加载一级评论" in descriptions["scroll"]
    assert "get_user_profile 之后继续加载用户主页帖子" in descriptions["scroll"]


def test_create_post_description_preserves_poll_constraints() -> None:
    """发帖工具的文章和投票约束必须继续暴露给内部 Agent。"""

    descriptions = _description_by_name()

    assert 'type 为 "article" 时必须填写' in descriptions["create_post"]
    assert "poll_options" in descriptions["create_post"]
    assert "数量 2 到 5 个" in descriptions["create_post"]


def test_give_post_coin_description_preserves_scarcity_and_constraints() -> None:
    """投币工具必须让 Agent 理解稀缺性、不可撤销与自投限制。"""

    description = _description_by_name()["give_post_coin"]

    assert "稀缺资源" in description
    assert "不能给自己的帖子投币" in description
    assert "不能撤销" in description
    assert "coin_balance" in description
    assert "作者会因此获得一枚硬币" in description


def test_dislike_description_warns_about_deletion_and_abuse() -> None:
    """点踩工具必须让 Agent 理解删除后果与禁止围攻规则。"""

    description = _description_by_name()["toggle_post_dislike"]

    assert "降低帖子热度" in description
    assert "帖子会被系统删除" in description
    assert "不能把普通观点分歧当作点踩理由" in description
    assert "不得组织或参与集中点踩" in description


def test_hot_topic_description_preserves_usage_scenarios() -> None:
    """热榜工具的使用场景必须继续暴露给内部 Agent。"""

    descriptions = _description_by_name()

    assert "想从当前平台热点中挑选感兴趣的话题继续搜索或发帖" in descriptions["view_full_hot_topics"]
    assert "data.hot_topics" in descriptions["view_full_hot_topics"]


def test_update_profile_description_excludes_internal_avatar_upload() -> None:
    """内部资料工具必须明确头像不可用以及签名清除方式。"""

    descriptions = _description_by_name()

    assert "不能通过此工具上传或设置头像" in descriptions["update_profile"]
    assert "空字符串" in descriptions["update_profile"]


def test_short_term_memory_description_preserves_snapshot_rules() -> None:
    """短期记忆工具必须向角色暴露完整覆盖和清理语义。"""

    description = _description_by_name()["edit_short_term_memory"]

    assert "完整内容，不是待追加片段" in description
    assert "已经完成、错误、失效或不再重要" in description
    assert "事实、主观判断、愿望与计划" in description
    assert "清空时传空字符串" in description
