"""热榜工具。

让内部 Agent 能查看平台公开热榜的完整内容。
"""

from langchain_core.tools import tool

from agents.agents_scheduler.langgraph.tools.support.shared_platform import run_shared_tool
from agents.agents_scheduler.langgraph.tools.types import ToolResult


@tool
def view_full_hot_topics(
    reason: str = "用户想查看更多热榜",
    summary: str = "",
) -> ToolResult:
    """
    查看更多热榜，包含每个热榜的标题、完整摘要和搜索关键词。

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

    result = run_shared_tool("view_full_hot_topics", {})
    return ToolResult(action=result.action, data=result.data)
