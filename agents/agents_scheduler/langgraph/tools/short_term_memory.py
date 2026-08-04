"""内部角色维护自身短期记忆的独占工具。"""

from langchain_core.tools import tool

from agents.agents_scheduler.langgraph.tools.types import (
    AuthenticationError,
    ToolExecutionError,
    ToolResult,
)
from agents.agents_scheduler.scheduler.context import get_current_agent_id
from agents.agents_scheduler.scheduler.time_system import get_time_system
from agents.management.backend.db_client import get_db_client


@tool
def edit_short_term_memory(content: str, reason: str, summary: str) -> ToolResult:
    """完整覆盖你当前的短期记忆 Markdown 快照。

    短期记忆用于保存你目前仍然认可、希望跨登录继续推进的目标、创作连载、进度与
    下一步、重要关系变化、事件脉络、舆论追踪、承诺和安排。它不是不断追加的流水
    账：状态变化时应改写旧内容；已经完成、错误、失效或不再重要的事项应从新快照
    删除。添加计划时尽量写清当前进度和下一步，并区分事实、主观判断、愿望与计划。

    ``content`` 必须是保存后的完整内容，不是待追加片段。修改局部内容时要保留其余
    仍有效部分；删除某项时在新内容中移除；清空时传空字符串。请使用 Markdown 语法排版。

    Args:
        content: 编辑完成后要保存的完整 Markdown，允许为空字符串。
        reason: 为什么这次需要更新当前认知状态。
        summary: 对当前视野的第一人称摘要，供工作记忆和登出总结使用。

    Returns:
        ToolResult: 只返回成功状态与新 revision，不重复返回整篇 Markdown。

    Raises:
        AuthenticationError: 当前执行线程没有有效的内部角色 ID。
        ToolExecutionError: 数据库更新失败。
    """

    agent_id = get_current_agent_id()
    if agent_id is None:
        raise AuthenticationError("无法确认当前内部角色身份")

    updated = get_db_client().update_short_term_memory(
        agent_id=agent_id,
        content=content,
        updated_at=get_time_system().get_scaled_timestamp(),
    )
    if updated is None:
        raise ToolExecutionError("短期记忆保存失败")

    revision = int(updated["revision"])
    action = "清空了短期记忆" if content == "" else "更新了短期记忆"
    return ToolResult(
        action=action,
        data={"success": True, "revision": revision},
    )
