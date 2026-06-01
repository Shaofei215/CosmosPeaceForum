# LangChain/LangGraph 工具注册
# 集中维护决策节点和总结节点可绑定的工具列表。

from typing import List

_base_social_tools = None
_relation_map_override = None


def get_social_tools(relation_map=None) -> List:
    """
    获取所有决策节点可用工具的列表（不包含 write_memory）。

    write_memory 工具应仅在总结节点中单独绑定给 LLM。recall_memory 和 web_search
    是决策节点可用的主动查询工具，会在工具执行节点中合并进 last_tool_result。
    """
    global _base_social_tools, _relation_map_override

    if relation_map is not None:
        _relation_map_override = relation_map

    if _base_social_tools is None:
        from agents.agents_scheduler.langgraph.tools.social import (
            search_platform,
            view_notifications,
            view_notification_origin,
            toggle_post_like,
            toggle_comment_like,
            create_comment,
            repost,
            toggle_follow,
            create_post,
            delete_content,
            logout,
            get_user_profile,
        )
        from agents.agents_scheduler.langgraph.tools.feed import (
            get_global_feed,
            expand_post,
            view_post_comments,
            expand_comment,
            scroll,
        )
        from agents.agents_scheduler.langgraph.tools.memory import recall_memory
        from agents.agents_scheduler.langgraph.tools.hot_topic import view_full_hot_topics

        _base_social_tools = [
            search_platform,
            view_notifications,
            view_notification_origin,
            view_full_hot_topics,
            toggle_post_like,
            toggle_comment_like,
            create_comment,
            repost,
            toggle_follow,
            create_post,
            delete_content,
            logout,
            get_user_profile,
            get_global_feed,
            expand_post,
            view_post_comments,
            expand_comment,
            scroll,
            recall_memory,
        ]

    try:
        from agents.agents_scheduler.langgraph.config import get_session_config
        config = get_session_config()
        if config.web_search_enabled:
            from agents.agents_scheduler.langgraph.tools.web_search import web_search
            return [*_base_social_tools, web_search]
    except Exception:
        pass

    return _base_social_tools


def get_all_tools_for_summarize() -> List:
    """
    获取总结节点使用的所有工具（仅包含 write_memory）。

    总结节点只允许 LLM 调用 write_memory，不绑定其他社交工具。
    """
    from agents.agents_scheduler.langgraph.tools.memory import write_memory
    return [write_memory]


def get_relation_mapping_service():
    """获取关系映射服务，优先使用会话级覆盖。"""
    if _relation_map_override is not None:
        return _relation_map_override
    from agents.agents_scheduler.scheduler.relation_map import get_relation_mapping_service as _get_service
    return _get_service()
