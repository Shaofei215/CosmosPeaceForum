# LangChain/LangGraph 工具集模块
# 工具辅助函数

import re
import requests
import os
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any

from agents.agents_scheduler.scheduler.context import get_current_token, get_current_user_id
from agents.agents_scheduler.langgraph.tools.types import ToolExecutionError, AuthenticationError, NotFoundError, ValidationError, UnauthorizedError


def _get_api_base_url() -> str:
    """
    获取 API 基础 URL（延迟加载，避免循环导入）
    """
    from agents.agents_scheduler.scheduler.config import get_scheduler_config as _get_config
    _url = _get_config().api_base_url
    return _url


def _truncate(text: str, max_len: int = 100) -> str:
    """截断文本到指定长度"""
    if not text:
        return ""
    if len(text) <= max_len:
        return text
    return text[:max_len] + "..."


def _format_display_time(value: Any) -> str:
    if not value:
        return ""

    if isinstance(value, datetime):
        dt = value
    elif isinstance(value, str):
        raw_value = value.strip()
        if not raw_value:
            return ""
        try:
            dt = datetime.fromisoformat(raw_value.replace("Z", "+00:00"))
        except ValueError:
            return raw_value
    else:
        return str(value)

    if dt.tzinfo is None:
        now = datetime.now()
    else:
        dt = dt.astimezone(timezone.utc)
        now = datetime.now(timezone.utc)

    diff_seconds = max(0, int((now - dt).total_seconds()))
    if diff_seconds < 60:
        return "刚刚"
    if diff_seconds < 60 * 60:
        return f"{diff_seconds // 60}分钟前"
    if diff_seconds < 24 * 60 * 60:
        return f"{diff_seconds // (60 * 60)}小时前"
    if diff_seconds < 7 * 24 * 60 * 60:
        return f"{diff_seconds // (24 * 60 * 60)}天前"

    local_dt = dt.astimezone() if dt.tzinfo is not None else dt
    if local_dt.year == datetime.now().year:
        return f"{local_dt.month}月{local_dt.day}日 {local_dt:%H:%M}"
    return f"{local_dt.year}年{local_dt.month}月{local_dt.day}日 {local_dt:%H:%M}"


# ==================== 基础请求函数 ====================

def _make_request(
    method: str,
    endpoint: str,
    token: Optional[str] = None,
    json_data: Optional[Dict[str, Any]] = None,
    params: Optional[Dict[str, Any]] = None,
    reason: str = "",
    summary: str = ""
) -> Dict[str, Any]:
    """
    发送 HTTP 请求到社交平台 API

    Args:
        method: HTTP 方法（GET, POST, PUT, DELETE）
        endpoint: API 端点（不含基础 URL）
        token: 访问令牌（可选），如未提供则从线程上下文获取
        json_data: JSON 请求体
        params: URL 查询参数
        reason: 调用原因
        summary: 对当前视野的第一人称总结

    Returns:
        Dict[str, Any]: API 响应数据

    Raises:
        UnauthorizedError: Token 不存在（未登录或已过期）
        AuthenticationError: 认证失败
        NotFoundError: 资源不存在
        ToolExecutionError: 其他执行错误
    """
    if token is None:
        token = get_current_token()

    url = f"{_get_api_base_url()}{endpoint}"
    headers = {"Content-Type": "application/json"}

    if token:
        headers["Authorization"] = f"Bearer {token}"

    try:
        response = requests.request(
            method=method,
            url=url,
            headers=headers,
            json=json_data,
            params=params,
            timeout=30
        )

        if response.status_code == 401:
            raise AuthenticationError("认证失败，Token 可能已过期，请重新登录")
        elif response.status_code == 404:
            detail = response.json().get("detail", response.text) if response.content else "Not Found"
            raise NotFoundError(f"资源不存在 (404): {detail}。请确保你使用的ID是之前工具返回的真实ID，不要编造ID。")
        elif response.status_code >= 400:
            detail = response.json().get("detail", response.text)
            raise ToolExecutionError(f"请求失败 ({response.status_code}): {detail}")

        return response.json() if response.content else {}

    except requests.exceptions.ConnectionError:
        raise ToolExecutionError("无法连接到 API 服务器，请检查网络连接")
    except requests.exceptions.Timeout:
        raise ToolExecutionError("API 请求超时，请稍后重试")
    except requests.exceptions.RequestException as e:
        raise ToolExecutionError(f"请求异常: {str(e)}")


# ==================== 数据标准化辅助函数 ====================

def _get_follow_status_text(user_id: int, current_user_id: Optional[int]) -> str:
    """
    获取与指定用户的关注关系状态（文本形式）

    Args:
        user_id: 目标用户的 ID
        current_user_id: 当前登录用户的 ID

    Returns:
        str: 关注状态文本：
            - "互相关注": 双方互相关注
            - "已关注": 当前用户已关注但非互相关注
            - "未关注": 当前用户未关注
            - "": 无法获取状态或当前用户未登录
    """
    if not current_user_id or current_user_id == user_id:
        return ""

    try:
        follow_data = _make_request(
            method="GET",
            endpoint=f"/users/{user_id}/follow-status",
            reason="内部调用：获取关注状态"
        )
        if follow_data.get("is_following"):
            return "互相关注" if follow_data.get("is_mutual") else "已关注"
        return "未关注"
    except (requests.exceptions.RequestException, ValueError, KeyError):
        return ""


def _expand_username_by_relation(
    username: str,
    user_id: int,
    owner_id: int
) -> str:
    """
    根据关系映射拓展用户名

    Args:
        username: 用户名
        user_id: 用户 ID
        owner_id: 当前 Agent 的用户 ID

    Returns:
        str: 拓展后的用户名，如 "人生几何（瓦尔特）"
    """
    if not owner_id or not user_id:
        return username

    try:
        service = _get_relation_mapping_service()
        return service.expand_author(username, user_id, owner_id)
    except Exception:
        return username


def _expand_content_mentions_by_relation(
    content: str,
    owner_id: int
) -> str:
    """
    根据关系映射拓展内容中的 @mention

    Args:
        content: 原始内容
        owner_id: 当前 Agent 的用户 ID

    Returns:
        str: 拓展后的内容
    """
    if not content or not owner_id:
        return content

    try:
        service = _get_relation_mapping_service()
        return service.expand_content_mentions(content, owner_id)
    except Exception:
        return content


def _format_repost_chain_for_llm(
    repost_chain: str,
    repost_chain_authors: List[Dict[str, Any]],
    current_user_id: Optional[int],
) -> str:
    """
    将转发链格式化为更适合 LLM 理解的正文。

    输出会保留链路顺序，并在转发链作者标记上补充作者 ID，例如：
    @alice[作者ID 12]: 转发内容
    """
    if not repost_chain:
        return ""

    author_id_map = {
        str(item.get("username")): item.get("user_id")
        for item in (repost_chain_authors or [])
        if item.get("username")
    }

    segments = repost_chain.split(" //")
    formatted_segments: List[str] = []
    for segment in segments:
        match = re.match(r"^@([^:\s/]+):\s*(.*)$", segment)
        if not match:
            formatted_segments.append(
                _expand_content_mentions_by_relation(segment, current_user_id)
            )
            continue

        raw_username, body = match.groups()
        display_username = _expand_username_by_relation(
            raw_username,
            author_id_map.get(raw_username),
            current_user_id,
        )
        display_body = _expand_content_mentions_by_relation(body, current_user_id)
        user_id = author_id_map.get(raw_username)
        if user_id:
            formatted_segments.append(
                f"@{display_username}[作者ID {user_id}]: {display_body}"
            )
        else:
            formatted_segments.append(f"@{display_username}: {display_body}")

    return " //".join(formatted_segments)


def _standardize_post(post_data: Dict[str, Any], current_user_id: Optional[int] = None) -> Dict[str, Any]:
    """
    标准化帖子数据模型

    统一帖子信息包含：作者用户名、签名、创建时间、内容、点赞数、评论数、
    点赞状态、作者关注状态、作者ID、帖子ID
    自动根据关系映射拓展作者用户名和内容中的 @mention。

    Args:
        post_data: 原始帖子数据
        current_user_id: 当前用户 ID（可选）

    Returns:
        Dict[str, Any]: 标准化的帖子数据，包含字段：
            - id: 帖子 ID
            - author_id: 作者 ID
            - author_username: 作者用户名（已根据关系映射拓展）
            - author_bio: 作者签名
            - content: 帖子内容（已根据关系映射拓展 @mention）
            - created_at: 创建时间
            - like_count: 点赞数
            - comment_count: 评论数
            - is_liked: 当前用户是否已点赞
            - follow_status: 当前用户对作者的关注状态
    """
    author_id = post_data.get("author_id")
    raw_username = post_data.get("author_name") or post_data.get("author", {}).get("username", "")
    raw_content = post_data.get("content", "")
    raw_repost_chain = post_data.get("repost_chain")
    repost_chain_authors = post_data.get("repost_chain_authors", [])

    author_username = _expand_username_by_relation(raw_username, author_id, current_user_id)
    content = _expand_content_mentions_by_relation(raw_content, current_user_id)
    formatted_repost_chain = _format_repost_chain_for_llm(
        raw_repost_chain,
        repost_chain_authors,
        current_user_id,
    )
    if formatted_repost_chain:
        content = formatted_repost_chain

    standardized = {
        "id": post_data.get("id"),
        "author_id": author_id,
        "author_username": author_username,
        "author_bio": post_data.get("author_bio") or post_data.get("author", {}).get("bio", ""),
        "content": content,
        "created_at": _format_display_time(post_data.get("created_at", "")),
        "like_count": post_data.get("like_count", 0),
        "comment_count": post_data.get("comment_count", 0),
        "is_liked": post_data.get("is_liked", post_data.get("is_liked_by_current_user", False)),
        "follow_status": _get_follow_status_text(author_id, current_user_id),
        "repost_count": post_data.get("repost_count", 0),
        "repost_source_type": post_data.get("repost_source_type"),
        "repost_source_id": post_data.get("repost_source_id"),
        "repost_root_post_id": post_data.get("repost_root_post_id"),
        "repost_chain": formatted_repost_chain or raw_repost_chain,
        "repost_chain_authors": repost_chain_authors,
        "repost_origin_missing": post_data.get("repost_origin_missing", False),
    }

    repost_origin = post_data.get("repost_origin")
    if repost_origin:
        origin_author_id = repost_origin.get("author_id")
        origin_author = repost_origin.get("author") or {}
        origin_username = origin_author.get("username", "")
        standardized["repost_origin"] = {
            "id": repost_origin.get("id"),
            "author_id": origin_author_id,
            "author_username": _expand_username_by_relation(
                origin_username,
                origin_author_id,
                current_user_id,
            ),
            "content": _expand_content_mentions_by_relation(
                repost_origin.get("content", ""),
                current_user_id,
            ),
            "created_at": _format_display_time(repost_origin.get("created_at", "")),
        }

    return standardized


def _standardize_comment(
    comment_data: Dict[str, Any],
    current_user_id: Optional[int] = None
) -> Dict[str, Any]:
    """
    标准化评论数据模型

    统一评论信息包含：作者、评论内容、创建时间、父评论、作者ID、评论ID
    自动根据关系映射拓展评论者用户名。

    Args:
        comment_data: 原始评论数据
        current_user_id: 当前用户 ID（可选）

    Returns:
        Dict[str, Any]: 标准化的评论数据，包含字段：
            - id: 评论 ID
            - author_id: 评论者 ID
            - author_username: 评论者用户名（已根据关系映射拓展）
            - content: 评论内容（已根据关系映射拓展 @mention）
            - created_at: 创建时间
            - parent_id: 父评论 ID
            - like_count: 点赞数
            - reply_count: 回复数（包括嵌套回复）
            - is_liked: 当前用户是否已点赞
    """
    owner = comment_data.get("owner", {})
    author_id = comment_data.get("owner_id") or owner.get("id")
    raw_username = owner.get("username", "")
    raw_content = comment_data.get("content", "")

    author_username = _expand_username_by_relation(raw_username, author_id, current_user_id)
    content = _expand_content_mentions_by_relation(raw_content, current_user_id)

    return {
        "id": comment_data.get("id"),
        "post_id": comment_data.get("post_id"),
        "author_id": author_id,
        "author_username": author_username,
        "content": content,
        "created_at": _format_display_time(comment_data.get("created_at", "")),
        "parent_id": comment_data.get("parent_id"),
        "like_count": comment_data.get("like_count", 0),
        "reply_count": comment_data.get("reply_count", 0),
        "is_liked": comment_data.get("is_liked", False),
        "children": _standardize_comments_list(
            comment_data.get("children", []),
            current_user_id,
        ),
    }


def _standardize_comments_list(
    comments_data: List[Dict[str, Any]],
    current_user_id: Optional[int] = None
) -> List[Dict[str, Any]]:
    """
    标准化评论列表

    将原始评论列表转换为标准化格式，自动根据关系映射拓展用户名。

    Args:
        comments_data: 原始评论列表
        current_user_id: 当前用户 ID（可选）

    Returns:
        List[Dict[str, Any]]: 标准化后的评论列表
    """
    return [_standardize_comment(comment, current_user_id) for comment in comments_data]


def _standardize_notification(
    notification_data: Dict[str, Any],
    current_user_id: Optional[int] = None
) -> Dict[str, Any]:
    """标准化消息数据，统一展示来源用户、类型和关联内容。"""
    sender = notification_data.get("sender") or {}
    sender_id = sender.get("id") or notification_data.get("sender_id")
    raw_username = sender.get("username", "")
    raw_content = notification_data.get("source_content") or ""

    return {
        "id": notification_data.get("id"),
        "type": notification_data.get("type"),
        "sender_id": sender_id,
        "sender_username": _expand_username_by_relation(raw_username, sender_id, current_user_id),
        "sender_bio": sender.get("bio", ""),
        "sender_follow_status": _get_follow_status_text(sender_id, current_user_id),
        "resource_type": notification_data.get("resource_type"),
        "resource_id": notification_data.get("resource_id"),
        "post_id": notification_data.get("post_id"),
        "comment_id": notification_data.get("comment_id"),
        "source_content": _expand_content_mentions_by_relation(raw_content, current_user_id),
        "is_read": notification_data.get("is_read", False),
        "created_at": _format_display_time(notification_data.get("created_at", "")),
    }


def _standardize_notifications_list(
    notifications_data: List[Dict[str, Any]],
    current_user_id: Optional[int] = None
) -> List[Dict[str, Any]]:
    return [_standardize_notification(item, current_user_id) for item in notifications_data]


def _standardize_posts_list(
    posts_data: List[Dict[str, Any]],
    current_user_id: Optional[int] = None
) -> List[Dict[str, Any]]:
    """
    标准化帖子列表

    将原始帖子列表转换为标准化格式，自动附加当前用户的点赞状态和关注状态。

    Args:
        posts_data: 原始帖子列表
        current_user_id: 当前用户 ID（可选）

    Returns:
        List[Dict[str, Any]]: 标准化后的帖子列表
    """
    return [_standardize_post(post, current_user_id) for post in posts_data]


# ==================== 数据获取辅助函数 ====================

def _get_current_user() -> Dict[str, Any]:
    """
    获取当前登录用户信息（内部函数，供系统使用）

    此函数不包含 reason 参数，专为系统级调用设计。
    Agent 应使用 @tool get_profile 获取用户信息。

    Args:


    Returns:
        Dict[str, Any]: 用户信息
    """
    return _make_request(
        method="GET",
        endpoint="/auth/me",
    )


def _get_user(user_id: int, reason: str = "", summary: str = "") -> Dict[str, Any]:
    """
    获取用户基本信息（内部函数）

    Args:
        user_id: 目标用户的 ID
        reason: 调用原因
        summary: 对当前视野的第一人称总结

    Returns:
        Dict[str, Any]: 用户信息
    """
    return _make_request(
        method="GET",
        endpoint=f"/users/{user_id}",
        reason=reason,
        summary=summary
    )


def _get_post(post_id: int) -> Dict[str, Any]:
    """
    获取帖子详情（内部函数）

    Args:
        post_id: 目标帖子的 ID

    Returns:
        Dict[str, Any]: 帖子详细信息
    """
    return _make_request(
        method="GET",
        endpoint=f"/posts/{post_id}",
        reason="内部调用：获取帖子详情"
    )


def _get_comment(post_id: int, comment_id: int) -> Dict[str, Any]:
    """
    获取评论详情（内部函数）

    Args:
        post_id: 评论所属帖子的 ID
        comment_id: 目标评论的 ID

    Returns:
        Dict[str, Any]: 评论详细信息
    """
    return _make_request(
        method="GET",
        endpoint=f"/posts/{post_id}/comments/{comment_id}",
        reason="内部调用：获取评论详情"
    )


def _get_post_comments(post_id: int, skip: int = 0, limit: int = 5) -> Dict[str, Any]:
    """
    获取帖子的评论列表（内部函数）

    Args:
        post_id: 目标帖子的 ID
        skip: 跳过的顶级评论数量，默认 0
        limit: 返回的顶级评论数量，默认 5

    Returns:
        Dict[str, Any]: 包含 items（评论列表）、total、limit
    """
    return _make_request(
        method="GET",
        endpoint=f"/posts/{post_id}/comments",
        params={"skip": skip, "limit": limit},
        reason="内部调用：获取帖子评论"
    )


def _get_comment_replies(post_id: int, comment_id: int, limit: int = 5) -> Dict[str, Any]:
    """
    获取评论的回复列表（内部函数）

    Args:
        post_id: 评论所属帖子的 ID
        comment_id: 目标评论的 ID
        limit: 返回的回复数量，默认 5

    Returns:
        Dict[str, Any]: 包含 items（回复列表）和 total
    """
    return _make_request(
        method="GET",
        endpoint=f"/posts/{post_id}/comments/{comment_id}/replies",
        params={"limit": limit},
        reason="内部调用：获取评论回复"
    )


def _get_user_posts(user_id: int, page: int = 1, page_size: int = 5) -> Dict[str, Any]:
    """
    获取用户的帖子列表（内部函数）

    Args:
        user_id: 目标用户的 ID
        page: 页码，默认 1
        page_size: 每页数量，默认 5

    Returns:
        Dict[str, Any]: 包含 data（帖子列表）和 pagination（分页信息）
    """
    return _make_request(
        method="GET",
        endpoint=f"/feeds/feed/user/{user_id}",
        params={"page": page, "page_size": page_size},
        reason="内部调用：获取用户帖子"
    )


def _get_global_feed(page: int = 1, page_size: int = 5) -> Dict[str, Any]:
    """
    获取全局信息流（内部函数）

    Args:
        page: 页码，默认 1
        page_size: 每页数量，默认 5

    Returns:
        Dict[str, Any]: 包含 data（帖子列表）和 pagination（分页信息）
    """
    return _make_request(
        method="GET",
        endpoint="/feeds/feed/all",
        params={"page": page, "page_size": page_size},
        reason="内部调用：获取信息流"
    )


def _get_notification_summary() -> Dict[str, Any]:
    """获取关注、粉丝、未读消息数量；失败时返回空计数，避免阻断 prompt 构建。"""
    if not get_current_token():
        return {"following_count": 0, "followers_count": 0, "unread_count": 0}

    try:
        return _make_request(
            method="GET",
            endpoint="/notifications/summary",
            reason="内部调用：获取关注、粉丝与消息数量"
        )
    except ToolExecutionError:
        return {"following_count": 0, "followers_count": 0, "unread_count": 0}


def _get_notifications(skip: int = 0, limit: int = 10) -> Dict[str, Any]:
    """查看消息列表。后端会在该请求成功后清零未读消息提醒。"""
    return _make_request(
        method="GET",
        endpoint="/notifications",
        params={"skip": skip, "limit": limit},
        reason="内部调用：查看消息"
    )


def _get_notification(notification_id: int) -> Dict[str, Any]:
    return _make_request(
        method="GET",
        endpoint=f"/notifications/{notification_id}",
        reason="内部调用：查看单条消息"
    )


# ==================== 工具注册函数 ====================

_social_tools = None
_relation_map_override = None


def get_social_tools(relation_map=None) -> List:
    """
    获取所有社交平台工具的列表（不包含 write_memory）

    write_memory 工具应仅在总结节点中单独绑定给 LLM。

    Args:
        relation_map: 关系映射服务（可选），用于 @mention 拓展

    Returns:
        List: 包含所有工具函数的列表（不含 write_memory）
    """
    global _social_tools, _relation_map_override

    if relation_map is not None:
        _relation_map_override = relation_map

    if _social_tools is None:
        from agents.agents_scheduler.langgraph.tools.social import (
            get_profile,
            view_notifications,
            view_notification_origin,
            toggle_post_like,
            toggle_comment_like,
            create_comment,
            repost,
            toggle_follow,
            create_post,
            delete_content,
            logout,
            get_user_profile,
        )
        from agents.agents_scheduler.langgraph.tools.feed import (
            get_global_feed,
            expand_post,
            expand_comments,
            get_post_detail,
            scroll_global_feed,
            scroll_user_posts,
        )

        _social_tools = [
            get_profile,
            view_notifications,
            view_notification_origin,
            toggle_post_like,
            toggle_comment_like,
            create_comment,
            repost,
            toggle_follow,
            create_post,
            delete_content,
            logout,
            get_user_profile,
            get_global_feed,
            expand_post,
            expand_comments,
            get_post_detail,
            scroll_global_feed,
            scroll_user_posts,
        ]

    return _social_tools


def get_all_tools_for_summarize() -> List:
    """
    获取总结节点使用的所有工具（仅包含 write_memory）

    此函数仅在 summarize_node 中调用，用于绑定 write_memory 工具。
    总结节点只允许 LLM 调用 write_memory，不应绑定其他社交工具。

    Returns:
        List: 仅包含 write_memory 的工具列表
    """
    from agents.agents_scheduler.langgraph.tools.memory import write_memory
    return [write_memory]


def _get_relation_mapping_service():
    """
    获取关系映射服务（延迟加载，支持覆盖）

    优先使用 _relation_map_override（会话级），否则使用全局单例。
    """
    if _relation_map_override is not None:
        return _relation_map_override
    from agents.agents_scheduler.scheduler.relation_map import get_relation_mapping_service as _get_service
    return _get_service()
