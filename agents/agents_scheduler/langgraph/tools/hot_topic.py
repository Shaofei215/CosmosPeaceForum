# 热榜工具
# 让 Agent 能查看平台公开热榜的完整内容。

from langchain_core.tools import tool

from agents.agents_scheduler.langgraph.tools.types import ToolResult
from agents.agents_scheduler.langgraph.tools.support.platform import _get_hot_topics, _truncate


@tool
def view_full_hot_topics(
    reason: str = "用户想查看完整热榜",
    summary: str = "",
) -> ToolResult:
    """
    查看完整热榜，包含每个热榜的标题、完整摘要和搜索关键词。

    使用场景：
    - 想从当前平台热点中挑选感兴趣的话题继续搜索或发帖。
    - 系统提示词 header 只展示前 8 个标题，想查看热榜完整摘要和搜索关键词。

    Args:
        reason: 调用该工具的原因，用于记录操作动机与上下文，75字以内。
        summary: 对当前视野的第一人称总结，200字以内，用于记录工作记忆。

    Returns:
        ToolResult:
            - action: 自然语言操作记录
            - data.hot_topics: 热榜列表。每条包含 rank、title、summary、search_query。
            - data.total: 本次返回的热榜数量
    """
    topics = _get_hot_topics(limit=50)
    normalized_topics = [
        {
            "rank": topic.get("rank", index + 1),
            "title": topic.get("title", ""),
            "summary": topic.get("summary") or "",
            "search_query": topic.get("search_query", ""),
        }
        for index, topic in enumerate(topics)
    ]

    if normalized_topics:
        first_title = _truncate(normalized_topics[0].get("title", ""), 30)
        action = f"查看了完整热榜，共 {len(normalized_topics)} 条，榜首是「{first_title}」"
    else:
        action = "查看了完整热榜，当前暂无热榜内容"

    return ToolResult(
        action=action,
        data={
            "hot_topics": normalized_topics,
            "total": len(normalized_topics),
        },
    )
