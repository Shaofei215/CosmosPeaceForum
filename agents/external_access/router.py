"""外部 Agent 工具网关路由。

该路由挂载在 agents 服务 `/external/v1` 下。它只公开健康检查、工具发现和白名单
工具执行，不暴露 Management API，也不代理任意公开平台 URL。
"""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from agents.external_access.schemas import (
    ToolDefinition,
    ToolErrorResponse,
    ToolExecutionRequest,
    ToolExecutionResponse,
    ToolListResponse,
    ToolMeta,
)
from agents.external_access.tools import (
    TOOLS,
    ExternalToolContext,
    ExternalToolError,
    execute_tool,
)
from agents.management.backend.core.config import get_config
from agents.platform_access import (
    PlatformAccessError,
    PlatformAuthenticationError,
    PlatformClient,
    PlatformConnectionError,
    PlatformNotFoundError,
    PlatformTimeoutError,
)


router = APIRouter()
security = HTTPBearer(auto_error=False)


def _request_id(request: Request) -> str:
    """读取或生成请求 ID。"""

    return request.headers.get("x-request-id") or uuid4().hex


def _error_payload(
    *,
    status_code: int,
    error_code: str,
    message: str,
    request_id: str,
    tool: str | None = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    """构造稳定错误响应，避免暴露内部异常、URL、Header 或 Secret。"""

    payload = ToolErrorResponse(
        error_code=error_code,
        message=message,
        tool=tool,
        meta=ToolMeta(request_id=request_id),
    )
    return JSONResponse(
        status_code=status_code,
        content=payload.model_dump(),
        headers=headers,
    )


def _platform_error_response(exc: PlatformAccessError, request_id: str, tool: str) -> JSONResponse:
    """把平台访问异常映射为外部协议错误。"""

    if isinstance(exc, PlatformAuthenticationError):
        return _error_payload(
            status_code=status.HTTP_401_UNAUTHORIZED,
            error_code="AUTHENTICATION_REQUIRED",
            message="认证失败，请刷新或重新登录",
            request_id=request_id,
            tool=tool,
        )
    if isinstance(exc, PlatformNotFoundError):
        return _error_payload(
            status_code=status.HTTP_404_NOT_FOUND,
            error_code="RESOURCE_NOT_FOUND",
            message=exc.detail or "资源不存在",
            request_id=request_id,
            tool=tool,
        )
    if isinstance(exc, PlatformTimeoutError):
        return _error_payload(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            error_code="UPSTREAM_TIMEOUT",
            message="平台请求超时",
            request_id=request_id,
            tool=tool,
        )
    if isinstance(exc, PlatformConnectionError):
        return _error_payload(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            error_code="UPSTREAM_UNAVAILABLE",
            message="平台服务暂不可用",
            request_id=request_id,
            tool=tool,
        )

    code = exc.status_code or status.HTTP_503_SERVICE_UNAVAILABLE
    if code == status.HTTP_403_FORBIDDEN:
        return _error_payload(
            status_code=code,
            error_code="ACTION_FORBIDDEN",
            message=exc.detail or "操作被拒绝",
            request_id=request_id,
            tool=tool,
        )
    if code == status.HTTP_429_TOO_MANY_REQUESTS:
        return _error_payload(
            status_code=code,
            error_code="RATE_LIMITED",
            message=exc.detail or "请求过于频繁",
            request_id=request_id,
            tool=tool,
        )
    if code in {status.HTTP_400_BAD_REQUEST, status.HTTP_422_UNPROCESSABLE_ENTITY}:
        return _error_payload(
            status_code=code,
            error_code="INVALID_ARGUMENTS",
            message=exc.detail or "参数无效",
            request_id=request_id,
            tool=tool,
        )
    return _error_payload(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE if code >= 500 else code,
        error_code="UPSTREAM_UNAVAILABLE" if code >= 500 else "ACTION_FORBIDDEN",
        message=exc.detail or "平台请求失败",
        request_id=request_id,
        tool=tool,
    )


def _output_schema() -> dict[str, Any]:
    """返回工具成功响应的 JSON Schema。"""

    return ToolExecutionResponse.model_json_schema()


@router.get("/health")
def health() -> dict[str, str]:
    """外部网关健康检查。"""

    return {"status": "healthy", "schema_version": "1"}


@router.get("/tools", response_model=ToolListResponse)
def list_tools() -> ToolListResponse:
    """返回外部 Agent 可用工具白名单与参数 Schema。"""

    common_errors = [
        "INVALID_ARGUMENTS",
        "AUTHENTICATION_REQUIRED",
        "ACTION_FORBIDDEN",
        "RESOURCE_NOT_FOUND",
        "RATE_LIMITED",
        "UPSTREAM_UNAVAILABLE",
        "UPSTREAM_TIMEOUT",
    ]
    return ToolListResponse(
        tools=[
            ToolDefinition(
                name=definition.name,
                description=definition.description,
                kind=definition.kind,  # type: ignore[arg-type]
                input_schema=definition.input_schema(),
                output_schema=_output_schema(),
                error_codes=common_errors,
            )
            for definition in TOOLS.values()
        ]
    )


@router.post("/tools/{tool_name}", response_model=ToolExecutionResponse)
def run_tool(
    tool_name: str,
    payload: ToolExecutionRequest,
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> ToolExecutionResponse | JSONResponse:
    """执行单个外部工具。

    Args:
        tool_name: 白名单工具名。
        payload: 工具参数包装对象。
        request: 当前 HTTP 请求，用于请求 ID 和错误响应。
        access_token: 当前普通账号 access token。

    Returns:
        ToolExecutionResponse | JSONResponse: 成功响应或稳定错误响应。
    """

    request_id = _request_id(request)
    if credentials is None or credentials.scheme.lower() != "bearer":
        return _error_payload(
            status_code=status.HTTP_401_UNAUTHORIZED,
            error_code="AUTHENTICATION_REQUIRED",
            message="需要 Bearer Access Token",
            request_id=request_id,
            tool=tool_name,
        )

    access_token = credentials.credentials
    if tool_name not in TOOLS:
        return _error_payload(
            status_code=status.HTTP_404_NOT_FOUND,
            error_code="TOOL_NOT_FOUND",
            message="工具不存在",
            request_id=request_id,
            tool=tool_name,
        )

    config = get_config()
    cursor_secret = config.jwt_secret_key
    client = PlatformClient(
        base_url=config.social_platform_api_base_url,
        admin_key=config.admin_key,
    )

    try:
        current_user = client.request("GET", "/auth/me", access_token=access_token)
        context = ExternalToolContext(
            client=client,
            access_token=access_token,
            current_user=current_user,
            cursor_secret=cursor_secret,
        )
        result = execute_tool(tool_name, payload.arguments, context)
    except ExternalToolError as exc:
        return _error_payload(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            error_code="INVALID_ARGUMENTS",
            message=str(exc),
            request_id=request_id,
            tool=tool_name,
        )
    except PlatformAccessError as exc:
        return _platform_error_response(exc, request_id, tool_name)

    return ToolExecutionResponse(
        tool=tool_name,
        action=result.action,
        data=result.data,
        meta=ToolMeta(
            request_id=request_id,
            scroll_cursor=result.scroll_cursor,
        ),
    )
