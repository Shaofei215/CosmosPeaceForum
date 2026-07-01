"""共享平台工具结果与错误类型。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

ToolCursor = dict[str, Any]


class PlatformToolError(Exception):
    """共享工具参数、游标或业务前置校验错误。"""


@dataclass
class PlatformToolResult:
    """共享平台工具执行结果。

    Args:
        action: 自然语言操作记录。
        data: 工具返回给 Agent 的结构化数据。
        cursor: 下一次 `scroll` 使用的未签名游标状态。
    """

    action: str
    data: dict[str, Any]
    cursor: ToolCursor | None = None
