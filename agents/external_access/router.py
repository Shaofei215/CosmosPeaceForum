"""外部 Agent 工具网关路由。

该路由挂载在 agents 服务 `/external/v1` 下。它只公开健康检查、工具发现和白名单
工具执行，不暴露 Management API，也不代理任意公开平台 URL。
"""

from __future__ import annotations

import logging
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Request, UploadFile, status
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
from agents.platform_tools import PlatformToolContext
from agents.platform_tools.presenters import normalize_user


router = APIRouter()
security = HTTPBearer(auto_error=False)
logger = logging.getLogger(__name__)


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
    unread_count: int | None = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    """构造稳定错误响应，避免暴露内部异常、URL、Header 或 Secret。"""

    payload = ToolErrorResponse(
        error_code=error_code,
        message=message,
        tool=tool,
        data={"unread_count": unread_count} if unread_count and unread_count > 0 else None,
        meta=ToolMeta(request_id=request_id),
    )
    return JSONResponse(
        status_code=status_code,
        content=payload.model_dump(exclude_none=True),
        headers=headers,
    )


def _platform_error_response(
    exc: PlatformAccessError,
    request_id: str,
    tool: str,
    unread_count: int | None = None,
) -> JSONResponse:
    """把平台访问异常映射为外部协议错误。"""

    if isinstance(exc, PlatformAuthenticationError):
        return _error_payload(
            status_code=status.HTTP_401_UNAUTHORIZED,
            error_code="AUTHENTICATION_REQUIRED",
            message="认证失败，请刷新或重新登录",
            request_id=request_id,
            tool=tool,
            unread_count=unread_count,
        )
    if isinstance(exc, PlatformNotFoundError):
        return _error_payload(
            status_code=status.HTTP_404_NOT_FOUND,
            error_code="RESOURCE_NOT_FOUND",
            message=exc.detail or "资源不存在",
            request_id=request_id,
            tool=tool,
            unread_count=unread_count,
        )
    if isinstance(exc, PlatformTimeoutError):
        return _error_payload(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            error_code="UPSTREAM_TIMEOUT",
            message="平台请求超时",
            request_id=request_id,
            tool=tool,
            unread_count=unread_count,
        )
    if isinstance(exc, PlatformConnectionError):
        return _error_payload(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            error_code="UPSTREAM_UNAVAILABLE",
            message="平台服务暂不可用",
            request_id=request_id,
            tool=tool,
            unread_count=unread_count,
        )

    code = exc.status_code or status.HTTP_503_SERVICE_UNAVAILABLE
    if code == status.HTTP_403_FORBIDDEN:
        return _error_payload(
            status_code=code,
            error_code="ACTION_FORBIDDEN",
            message=exc.detail or "操作被拒绝",
            request_id=request_id,
            tool=tool,
            unread_count=unread_count,
        )
    if code == status.HTTP_429_TOO_MANY_REQUESTS:
        return _error_payload(
            status_code=code,
            error_code="RATE_LIMITED",
            message=exc.detail or "请求过于频繁",
            request_id=request_id,
            tool=tool,
            unread_count=unread_count,
        )
    if code in {status.HTTP_400_BAD_REQUEST, status.HTTP_422_UNPROCESSABLE_ENTITY}:
        return _error_payload(
            status_code=code,
            error_code="INVALID_ARGUMENTS",
            message=exc.detail or "参数无效",
            request_id=request_id,
            tool=tool,
            unread_count=unread_count,
        )
    return _error_payload(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE if code >= 500 else code,
        error_code="UPSTREAM_UNAVAILABLE" if code >= 500 else "ACTION_FORBIDDEN",
        message=exc.detail or "平台请求失败",
        request_id=request_id,
        tool=tool,
        unread_count=unread_count,
    )


def _get_unread_count(client: PlatformClient, access_token: str) -> int | None:
    """读取正数未读消息数量，失败时不影响原工具响应。

    Args:
        client: 当前显式凭据平台客户端。
        access_token: 当前普通账号 Access Token。

    Returns:
        int | None: 正数未读数量；无未读或读取失败时返回 ``None``。
    """

    try:
        payload = client.request(
            "GET",
            "/notifications/unread-count",
            access_token=access_token,
        )
        unread_count = int(payload.get("unread_count", 0) or 0)
        return unread_count if unread_count > 0 else None
    except PlatformAccessError:
        logger.warning("外部工具响应读取未读消息数量失败", exc_info=True)
        return None


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

    unread_before_logout: int | None = None
    try:
        current_user = client.request("GET", "/auth/me", access_token=access_token)
        context = ExternalToolContext(
            client=client,
            access_token=access_token,
            current_user=current_user,
            cursor_secret=cursor_secret,
        )
        if tool_name == "logout":
            unread_before_logout = _get_unread_count(client, access_token)
        result = execute_tool(tool_name, payload.arguments, context)
    except ExternalToolError as exc:
        return _error_payload(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            error_code="INVALID_ARGUMENTS",
            message=str(exc),
            request_id=request_id,
            tool=tool_name,
            unread_count=_get_unread_count(client, access_token),
        )
    except PlatformAccessError as exc:
        return _platform_error_response(
            exc,
            request_id,
            tool_name,
            unread_count=_get_unread_count(client, access_token),
        )

    unread_count = (
        unread_before_logout
        if tool_name == "logout"
        else _get_unread_count(client, access_token)
    )
    if unread_count is not None:
        result.data["unread_count"] = unread_count

    return ToolExecutionResponse(
        tool=tool_name,
        action=result.action,
        data=result.data,
        meta=ToolMeta(
            request_id=request_id,
            scroll_cursor=result.scroll_cursor,
        ),
    )


@router.post("/profile/avatar", response_model=ToolExecutionResponse)
def upload_profile_avatar(
    request: Request,
    file: UploadFile | None = File(default=None, description="头像图片文件"),
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> ToolExecutionResponse | JSONResponse:
    """为外部 Agent 转发当前账号头像文件。

    文件以 multipart 形式原样转发至 social_platform；网关不自行保存头像，也不
    复制公开平台的 MIME 类型和大小规则。

    Args:
        request: 当前 HTTP 请求，用于生成请求 ID。
        file: multipart 字段 ``file`` 中的头像文件。
        credentials: 当前普通账号 Bearer Access Token。

    Returns:
        ToolExecutionResponse | JSONResponse: 更新后的用户资料或稳定错误响应。
    """

    request_id = _request_id(request)
    tool_name = "upload_avatar"
    if credentials is None or credentials.scheme.lower() != "bearer":
        return _error_payload(
            status_code=status.HTTP_401_UNAUTHORIZED,
            error_code="AUTHENTICATION_REQUIRED",
            message="需要 Bearer Access Token",
            request_id=request_id,
            tool=tool_name,
        )
    if file is None:
        return _error_payload(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            error_code="INVALID_ARGUMENTS",
            message="必须提供 file 头像文件",
            request_id=request_id,
            tool=tool_name,
        )

    access_token = credentials.credentials
    config = get_config()
    client = PlatformClient(
        base_url=config.social_platform_api_base_url,
        admin_key=config.admin_key,
    )
    try:
        current_user = client.request("GET", "/auth/me", access_token=access_token)
        uploaded_user = client.upload_file(
            "/users/avatar",
            access_token=access_token,
            field_name="file",
            filename=file.filename or "avatar",
            file_object=file.file,
            content_type=file.content_type,
        )
    except PlatformAccessError as exc:
        return _platform_error_response(
            exc,
            request_id,
            tool_name,
            unread_count=_get_unread_count(client, access_token),
        )

    context = PlatformToolContext(
        client=client,
        access_token=access_token,
        current_user=current_user,
    )
    user = normalize_user(uploaded_user, context) or uploaded_user
    unread_count = _get_unread_count(client, access_token)
    if unread_count is not None:
        user["unread_count"] = unread_count
    return ToolExecutionResponse(
        tool=tool_name,
        action="更新了自己的头像",
        data=user,
        meta=ToolMeta(request_id=request_id),
    )
