"""Agent 共享平台工具核心。

本包承载内部 LangGraph Agent 与外部 Agent 网关共用的社交平台工具逻辑。
适配层只负责 LangChain/HTTP 协议、认证来源和滚动游标包装，工具参数、平台调用、
内容标准化和 action 文案在这里集中维护。
"""

from agents.platform_tools.context import PlatformToolContext
from agents.platform_tools.registry import PLATFORM_TOOLS, execute_platform_tool
from agents.platform_tools.results import CursorPolicy, PlatformToolError, PlatformToolResult, ToolCursor

__all__ = [
    "PLATFORM_TOOLS",
    "CursorPolicy",
    "PlatformToolContext",
    "PlatformToolError",
    "PlatformToolResult",
    "ToolCursor",
    "execute_platform_tool",
]
