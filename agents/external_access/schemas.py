"""外部 Agent 工具协议模型。

这些模型只定义 `/external/v1` 的稳定 HTTP 请求、发现和响应结构。具体工具
参数模型由 `agents.platform_tools.schemas` 统一维护，避免内部与外部契约漂移。
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class ToolExecutionRequest(BaseModel):
    """工具执行请求体。

    Args:
        arguments: 当前工具的 JSON 参数。Token、当前用户、来源证明和 Prompt 原因都不允许放入这里。
    """

    arguments: dict[str, Any] = Field(default_factory=dict)


class ToolMeta(BaseModel):
    """工具响应元信息。

    Args:
        request_id: 当前网关请求 ID。
        schema_version: 外部工具协议版本。
        scroll_cursor: 下一次 `scroll` 可使用的签名游标。
    """

    request_id: str
    schema_version: str = "1"
    scroll_cursor: str | None = None


class ToolExecutionResponse(BaseModel):
    """工具执行成功响应。"""

    ok: bool = True
    tool: str
    action: str
    data: dict[str, Any]
    meta: ToolMeta


class ToolErrorResponse(BaseModel):
    """工具执行失败响应。"""

    ok: bool = False
    error_code: str
    message: str
    tool: str | None = None
    data: dict[str, Any] | None = None
    meta: ToolMeta


class ToolDefinition(BaseModel):
    """工具发现接口返回的单个工具定义。"""

    name: str
    description: str
    kind: Literal["read", "write"]
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]
    error_codes: list[str]


class ToolListResponse(BaseModel):
    """工具发现接口响应。"""

    schema_version: str = "1"
    tools: list[ToolDefinition]
