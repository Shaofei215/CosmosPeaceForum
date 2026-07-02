"""外部 Agent 工具注册与执行适配层。

外部网关只处理 HTTP 协议、v1 白名单、签名滚动游标和错误映射。工具参数、
平台调用、内容构建与 action 文案统一复用 `agents.platform_tools` 共享核心。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from agents.external_access.cursor import CursorError, decode_cursor, encode_cursor
from agents.platform_access import PlatformClient
from agents.platform_tools import (
    PLATFORM_TOOLS,
    PlatformToolContext,
    PlatformToolError,
    PlatformToolResult,
    execute_platform_tool,
)
from agents.platform_tools.registry import PlatformToolDefinition


class ExternalToolError(Exception):
    """外部工具参数或游标错误。"""


@dataclass
class ExternalToolContext:
    """单次外部工具调用上下文。

    Args:
        client: 显式 Token 平台客户端。
        access_token: 当前普通账号 access token。
        current_user: `/auth/me` 预检返回的账号信息。
        cursor_secret: 滚动游标签名密钥。
    """

    client: PlatformClient
    access_token: str
    current_user: dict[str, Any]
    cursor_secret: str


@dataclass
class ExternalToolResult:
    """外部工具执行结果。"""

    action: str
    data: dict[str, Any]
    scroll_cursor: str | None = None


class ExternalToolDefinition:
    """外部工具注册表条目。"""

    def __init__(self, definition: PlatformToolDefinition) -> None:
        self.name = definition.name
        self.description = definition.description
        self.kind = definition.kind
        self.args_model = definition.args_model
        self._definition = definition

    def input_schema(self) -> dict[str, Any]:
        """返回工具参数 JSON Schema。"""

        schema = self.args_model.model_json_schema()
        if self.name == "scroll":
            properties = dict(schema.get("properties") or {})
            properties["scroll_cursor"] = {
                "title": "Scroll Cursor",
                "type": "string",
                "minLength": 16,
            }
            required = list(schema.get("required") or [])
            if "scroll_cursor" not in required:
                required.append("scroll_cursor")
            return {**schema, "properties": properties, "required": required}
        return schema


TOOLS: dict[str, ExternalToolDefinition] = {
    name: ExternalToolDefinition(definition)
    for name, definition in PLATFORM_TOOLS.items()
    if definition.external_public
}


def execute_tool(name: str, arguments: dict[str, Any], context: ExternalToolContext) -> ExternalToolResult:
    """校验参数并执行外部 v1 白名单工具。

    Args:
        name: 工具名。
        arguments: JSON 参数；`scroll` 的签名游标仍按外部协议放在这里。
        context: 单次调用上下文。

    Returns:
        ExternalToolResult: 外部网关成功响应需要的数据。

    Raises:
        KeyError: 工具不存在。
        ExternalToolError: 参数或游标不合法。
    """

    cursor: dict[str, Any] | None = None
    shared_arguments = dict(arguments)
    if name == "scroll":
        raw_cursor = shared_arguments.pop("scroll_cursor", None)
        if not raw_cursor:
            raise ExternalToolError("scroll_cursor 不能为空")
        try:
            cursor = decode_cursor(str(raw_cursor), context.cursor_secret)
        except CursorError as exc:
            raise ExternalToolError(str(exc)) from exc

    shared_context = PlatformToolContext(
        client=context.client,
        access_token=context.access_token,
        current_user=context.current_user,
        cursor=cursor,
    )
    try:
        result: PlatformToolResult = execute_platform_tool(name, shared_arguments, shared_context)
    except PlatformToolError as exc:
        raise ExternalToolError(str(exc)) from exc

    scroll_cursor = encode_cursor(result.cursor, context.cursor_secret) if result.cursor else None
    return ExternalToolResult(
        action=result.action,
        data=result.data,
        scroll_cursor=scroll_cursor,
    )
