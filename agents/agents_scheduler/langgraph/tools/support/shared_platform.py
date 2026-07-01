"""内部 LangGraph 工具到共享平台工具核心的适配器。"""

from __future__ import annotations

from typing import Any

from agents.agents_scheduler.langgraph.tools.support.registry import get_relation_mapping_service
from agents.agents_scheduler.langgraph.tools.types import AuthenticationError, NotFoundError, ToolExecutionError
from agents.agents_scheduler.scheduler.context import get_current_token, get_current_user_id
from agents.agents_scheduler.langgraph.tools.support import platform as legacy_platform
from agents.platform_access import (
    PlatformAccessError,
    PlatformAuthenticationError,
    PlatformClient,
    PlatformConnectionError,
    PlatformNotFoundError,
    PlatformTimeoutError,
)
from agents.platform_tools import PlatformToolContext, PlatformToolError, PlatformToolResult, PresentationMode, execute_platform_tool


def _get_api_base_url() -> str:
    """延迟读取公开平台 API 根地址。"""

    from agents.agents_scheduler.scheduler.config import get_scheduler_config

    return get_scheduler_config().api_base_url


def _build_internal_context() -> PlatformToolContext:
    """构造内部 Agent 共享工具上下文。"""

    from agents.agents_scheduler.scheduler.config import get_scheduler_config

    config = get_scheduler_config()
    token = get_current_token()
    user_id = get_current_user_id()
    current_user = {"id": user_id} if user_id is not None else None
    return PlatformToolContext(
        client=PlatformClient(base_url=_get_api_base_url(), admin_key=config.admin_key),
        access_token=token,
        current_user=current_user,
        mode=PresentationMode.INTERNAL,
        cursor=_get_scroll_cursor(),
        relation_expander=get_relation_mapping_service(),
    )


def _get_scroll_cursor() -> dict[str, Any]:
    """读取当前 Agent 的浏览游标。"""

    return legacy_platform._get_scroll_cursor()


def _set_scroll_cursor(cursor: dict[str, Any] | None) -> None:
    """记录当前页面的下一次 scroll 目标。"""

    legacy_platform._set_scroll_cursor(cursor or {})


def run_shared_tool(name: str, arguments: dict[str, Any]) -> PlatformToolResult:
    """执行共享平台工具并映射为内部工具错误。"""

    try:
        result = execute_platform_tool(name, arguments, _build_internal_context())
    except PlatformToolError as exc:
        raise ToolExecutionError(str(exc)) from exc
    except PlatformAuthenticationError as exc:
        raise AuthenticationError(str(exc)) from exc
    except PlatformNotFoundError as exc:
        detail = exc.detail or "Not Found"
        raise NotFoundError(f"资源不存在 (404): {detail}。请确保你使用的ID是之前工具返回的真实ID，不要编造ID。") from exc
    except PlatformConnectionError as exc:
        raise ToolExecutionError("无法连接到 API 服务器，请检查网络连接") from exc
    except PlatformTimeoutError as exc:
        raise ToolExecutionError("API 请求超时，请稍后重试") from exc
    except PlatformAccessError as exc:
        detail = f": {exc.detail}" if exc.detail else ""
        raise ToolExecutionError(f"{exc}{detail}") from exc

    _set_scroll_cursor(result.cursor)
    return result
