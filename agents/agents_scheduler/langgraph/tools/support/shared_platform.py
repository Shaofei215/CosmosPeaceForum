"""内部 LangGraph 到共享平台核心的会话适配层。

本模块负责构造显式工具上下文、保存浏览游标，并读取系统 Prompt 所需的平台摘要；
平台工具契约、执行和内容构建仍统一归属 ``agents.platform_tools``。
"""

from __future__ import annotations

import threading
from typing import Any

from agents.agents_scheduler.langgraph.tools.support.registry import get_relation_mapping_service
from agents.agents_scheduler.langgraph.tools.types import AuthenticationError, NotFoundError, ToolExecutionError
from agents.agents_scheduler.scheduler.context import get_current_context, get_current_token, get_current_user_id
from agents.platform_access import (
    PlatformAccessError,
    PlatformAuthenticationError,
    PlatformClient,
    PlatformConnectionError,
    PlatformNotFoundError,
    PlatformTimeoutError,
)
from agents.platform_tools import PlatformToolContext, PlatformToolError, PlatformToolResult, execute_platform_tool

_scroll_cursor_fallback = threading.local()


def _build_platform_client() -> PlatformClient:
    """使用 Scheduler 配置构造公开平台客户端。"""

    from agents.agents_scheduler.scheduler.config import get_scheduler_config

    config = get_scheduler_config()
    return PlatformClient(base_url=config.api_base_url, admin_key=config.admin_key)


def _build_internal_context() -> PlatformToolContext:
    """构造内部 Agent 共享工具上下文。"""

    token = get_current_token()
    user_id = get_current_user_id()
    agent_context = get_current_context()
    current_user = (
        {
            "id": user_id,
            "username": agent_context.username if agent_context else None,
            "bio": agent_context.personal_signature if agent_context else None,
        }
        if user_id is not None
        else None
    )
    return PlatformToolContext(
        client=_build_platform_client(),
        access_token=token,
        current_user=current_user,
        cursor=get_scroll_cursor(),
        relation_expander=get_relation_mapping_service(),
        profile_sync=agent_context.profile_sync if agent_context else None,
    )


def get_scroll_cursor() -> dict[str, Any]:
    """读取当前 Agent 的浏览游标。"""

    context = get_current_context()
    if context is not None:
        return getattr(context, "_scroll_cursor", {}) or {}
    return getattr(_scroll_cursor_fallback, "cursor", {}) or {}


def set_scroll_cursor(cursor: dict[str, Any] | None) -> None:
    """记录当前页面的下一次 scroll 目标。"""

    context = get_current_context()
    if context is not None:
        setattr(context, "_scroll_cursor", cursor or {})
        return
    _scroll_cursor_fallback.cursor = cursor or {}


def clear_scroll_cursor() -> None:
    """清空当前 Agent 的浏览游标。"""

    set_scroll_cursor({})


def _request_platform(endpoint: str, *, params: dict[str, Any] | None = None) -> Any:
    """使用当前 Scheduler 会话凭据读取公开平台辅助数据。"""

    return _build_platform_client().request(
        "GET",
        endpoint,
        access_token=get_current_token(),
        params=params,
    )


def get_notification_summary() -> dict[str, Any]:
    """获取账号关注与未读消息计数，平台不可用时返回空计数。"""

    empty_summary = {"following_count": 0, "followers_count": 0, "unread_count": 0}
    if not get_current_token():
        return empty_summary
    try:
        data = _request_platform("/notifications/summary")
    except PlatformAccessError:
        return empty_summary
    return data if isinstance(data, dict) else empty_summary


def get_hot_topics(limit: int = 20) -> list[dict[str, Any]]:
    """读取公开热榜。"""

    safe_limit = max(1, min(int(limit), 50))
    data = _request_platform("/hot-topics", params={"limit": safe_limit})
    return data if isinstance(data, list) else []


def get_trending_topics(limit: int = 20) -> list[dict[str, Any]]:
    """读取公开话题。"""

    safe_limit = max(1, min(int(limit), 50))
    data = _request_platform("/topics/trending", params={"limit": safe_limit})
    return data if isinstance(data, list) else []


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

    set_scroll_cursor(result.cursor)
    return result
