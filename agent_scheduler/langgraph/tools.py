# LangChain/LangGraph 工具集模块
# 为 AI Agent 提供社交平台操作的工具函数，符合 LangChain 工具标准格式
import re
import requests
import os
from typing import Optional, List, Dict, Any, TypedDict
from langchain_core.tools import tool

from agent_scheduler.scheduler.context import get_current_token, get_current_user_id
from agent_scheduler.memory.service import get_memory_service
from agent_scheduler.memory.config import get_memory_config


def _get_api_base_url() -> str:
    """
    获取 API 基础 URL（延迟加载，避免循环导入）
    """
    from agent_scheduler.scheduler.config import get_scheduler_config as _get_config
    _url = _get_config().api_base_url
    return _url


def _get_relation_mapping_service():
    """
    获取关系映射服务（延迟加载，避免循环导入）
    """
    from agent_scheduler.scheduler.relation_map import get_relation_mapping_service as _get_service
    return _get_service()


# ==================== 工具函数错误类型 ====================

class ToolExecutionError(Exception):
    """工具执行错误基类"""
    pass


class AuthenticationError(ToolExecutionError):
    """认证错误"""
    pass


class NotFoundError(ToolExecutionError):
    """资源不存在错误"""
    pass


class ValidationError(ToolExecutionError):
    """参数验证错误"""
    pass


class UnauthorizedError(ToolExecutionError):
    """未授权错误，Token 不存在或已过期"""
    pass


# ==================== 统一工具返回值结构 ====================

class ToolResult(TypedDict):
    """
    统一工具返回值结构

    所有 @tool 装饰的函数都应返回此结构。

    设计要点：
    - action: 自然语言格式的动作描述，描述"你做了什么"
    - data: 工具返回的原始数据，供 LLM 下次决策使用

    Example:
        return ToolResult(
            action="点赞了 @景元 的帖子：今天入手了新角色...",
            data={"post": {...}, "comments": [...]}
        )
    """
    action: str                              # 自然语言格式的动作描述
    data: Dict[str, Any]                     # 工具返回的原始数据


def _truncate(text: str, max_len: int = 100) -> str:
    """截断文本到指定长度"""
    if not text:
        return ""
    if len(text) <= max_len:
        return text
    return text[:max_len] + "..."


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
    except:
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

    author_username = _expand_username_by_relation(raw_username, author_id, current_user_id)
    content = _expand_content_mentions_by_relation(raw_content, current_user_id)

    standardized = {
        "id": post_data.get("id"),
        "author_id": author_id,
        "author_username": author_username,
        "author_bio": post_data.get("author_bio") or post_data.get("author", {}).get("bio", ""),
        "content": content,
        "created_at": post_data.get("created_at", ""),
        "like_count": post_data.get("like_count", 0),
        "comment_count": post_data.get("comment_count", 0),
        "is_liked": post_data.get("is_liked", False),
        "follow_status": _get_follow_status_text(author_id, current_user_id)
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
        "author_id": author_id,
        "author_username": author_username,
        "content": content,
        "created_at": comment_data.get("created_at", ""),
        "parent_id": comment_data.get("parent_id"),
        "like_count": comment_data.get("like_count", 0),
        "reply_count": comment_data.get("reply_count", 0),
        "is_liked": comment_data.get("is_liked", False)
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


# ==================== Agent 可调用的工具函数定义 ====================

@tool
def get_profile(
    reason: str = "用户想要查看自己的个人资料",
    summary: str = ""
) -> ToolResult:
    """
    获取当前登录用户的个人资料信息

    返回当前 Agent 用户的核心信息，包括用户名、个人签名、粉丝数量、关注数量等，
    以及自己发布的最新 3 条帖子。

    注意：此工具会自动从当前执行上下文获取认证信息，无需手动传入 Token。

    Args:
        reason: 对当前视野与行为的简单总结，调用该工具的原因，用于记录操作动机与上下文，75字以内。
                例如："用户想要查看自己的信息"、"查看个人资料"等。
        summary: 对当前视野的第一人称总结，200字以内，用于记录工作记忆。
                例如："我打开了个人主页，看到我的粉丝数是xxx，关注数是xxx"等。

    Returns:
        ToolResult: 包含以下字段:
            - action: "查看了自己的个人资料（@{username}）"
            - data: 用户信息字典，包含 id, username, bio, following_count, followers_count, follow_status, recent_posts

    Raises:
        UnauthorizedError: 未登录或 Token 已过期
        AuthenticationError: Token 无效
        ToolExecutionError: 服务器内部错误
    """
    current_user_id = get_current_user_id()
    data = _make_request(
        method="GET",
        endpoint="/auth/me",
        reason=reason,
        summary=summary
    )
    data.pop("avatar_url", None)
    data.pop("created_at", None)

    data["follow_status"] = "self"

    posts_data = _get_user_posts(current_user_id, page=1, page_size=3)
    data["recent_posts"] = _standardize_posts_list(
        posts_data.get("data", []),
        current_user_id
    )

    username = data.get("username", "")
    action = f"查看了自己的个人资料（@{username}）" if username else "查看了自己的个人资料"

    return ToolResult(action=action, data=data)


@tool
def toggle_post_like(
    post_id: int,
    reason: str = "用户想要点赞该帖子",
    summary: str = ""
) -> ToolResult:
    """
    切换指定帖子的点赞状态（点赞或取消点赞）

    根据当前 Agent 用户的点赞状态自动判断操作：如果尚未点赞则添加点赞，如果已点赞则取消点赞。
    这是一个幂等操作，重复调用会切换回原来的状态。

    注意：此工具会自动从当前执行上下文获取认证信息，无需手动传入 Token。

    Args:
        post_id: 目标帖子的 ID，必须是有效的正整数
        reason: 对当前视野与行为的简单总结，调用该工具的原因，用于记录操作动机与上下文，75字以内。
                例如："用户对这篇帖子感兴趣，想要点赞支持"、"用户想要取消点赞"等。
        summary: 对当前视野的第一人称总结，200字以内，用于记录工作记忆。
                例如："我看到了一个有趣的帖子，内容是xxx，作者是xxx"等。

    Returns:
        ToolResult: 包含以下字段:
            - action: "点赞了 @{author} 的帖子：{content}"
            - data: 包含 post 信息的字典

    Raises:
        UnauthorizedError: 未登录或 Token 已过期
        NotFoundError: 帖子不存在
        ToolExecutionError: 服务器内部错误
    """
    current_user_id = get_current_user_id()
    _make_request(
        method="POST",
        endpoint=f"/posts/{post_id}/like",
        reason=reason,
        summary=summary
    )

    post_data = _get_post(post_id)
    standardized_post = _standardize_post(post_data, current_user_id)

    post_author = standardized_post.get("author_username", "")
    post_content = _truncate(standardized_post.get("content", ""), 50)

    if post_author and post_content:
        action = f"点赞了 @{post_author} 的帖子：{post_content}"
    elif post_author:
        action = f"点赞了 @{post_author} 的帖子"
    else:
        action = f"点赞了帖子 {post_id}"

    return ToolResult(action=action, data={"post": standardized_post})


@tool
def toggle_comment_like(
    post_id: int,
    comment_id: int,
    reason: str = "用户想要点赞该评论",
    summary: str = ""
) -> ToolResult:
    """
    切换指定评论的点赞状态（点赞或取消点赞）

    根据当前 Agent 用户的点赞状态自动判断操作：如果尚未点赞则添加点赞，如果已点赞则取消点赞。
    这是一个幂等操作，重复调用会切换回原来的状态。

    注意：此工具会自动从当前执行上下文获取认证信息，无需手动传入 Token。

    Args:
        post_id: 评论所属帖子的 ID，用于路由匹配
        comment_id: 目标评论的 ID，必须是有效的正整数
        reason: 对当前视野与行为的简单总结，调用该工具的原因，用于记录操作动机与上下文，75字以内。
                例如："用户觉得这条评论说得很有道理，想要点赞"等。
        summary: 对当前视野的第一人称总结，200字以内，用于记录工作记忆。
                例如："我看到了这条评论，内容是xxx，作者是xxx"等。

    Returns:
        ToolResult: 包含以下字段:
            - action: "在 @{post_author} 的帖子（{post_content}）下点赞了 @{comment_author} 的评论：{comment_content}"
            - data: 包含 post 和 comment 信息的字典

    Raises:
        UnauthorizedError: 未登录或 Token 已过期
        NotFoundError: 评论不存在
        ToolExecutionError: 服务器内部错误
    """
    current_user_id = get_current_user_id()

    _make_request(
        method="POST",
        endpoint=f"/posts/{post_id}/comments/{comment_id}/like",
        reason=reason,
        summary=summary
    )

    post_data = _get_post(post_id)
    comment_data = _get_comment(post_id, comment_id)
    standardized_post = _standardize_post(post_data, current_user_id)
    standardized_comment = _standardize_comment(comment_data, current_user_id)

    post_author = standardized_post.get("author_username", "")
    post_content = _truncate(standardized_post.get("content", ""), 40)
    comment_author = standardized_comment.get("author_username", "") or standardized_comment.get("owner_username", "")
    comment_content = _truncate(standardized_comment.get("content", ""), 30)

    if post_author and post_content and comment_author and comment_content:
        action = f"在 @{post_author} 的帖子（{post_content}）下点赞了 @{comment_author} 的评论：{comment_content}"
    elif comment_author and comment_content:
        action = f"点赞了 @{comment_author} 的评论：{comment_content}"
    elif comment_author:
        action = f"点赞了 @{comment_author} 的评论"
    else:
        action = f"点赞了评论 {comment_id}"

    return ToolResult(action=action, data={"post": standardized_post, "comment": standardized_comment})


@tool
def create_comment(
    post_id: int,
    content: str,
    reason: str = "用户想要发表评论",
    summary: str = "",
    parent_id: Optional[int] = None
) -> ToolResult:
    """
    在指定帖子下创建新评论或回复

    支持创建一级评论和嵌套回复两种模式。当 parent_id 为空时创建一级评论，
    当指定 parent_id 时创建对该评论的回复。

    注意：此工具会自动从当前执行上下文获取认证信息，无需手动传入 Token。

    Args:
        post_id: 目标帖子的 ID，新评论将创建在此帖子下
        content: 评论的文本内容，至少需要 1 个字符
        reason: 对当前视野与行为的简单总结，调用该工具的原因，用于记录操作动机与上下文，75字以内。
                例如："用户想要表达对帖子的认同"、"用户想要回复某条评论"等。
        summary: 对当前视野的第一人称总结，200字以内，用于记录工作记忆。
                例如："我在帖子下方看到了很多评论，想自己也说两句"等。
        parent_id: 父评论 ID（可选），指定时创建回复，为空时创建一级评论

    Returns:
        ToolResult: 包含以下字段:
            - action: "在 @{post_author} 的帖子（{post_content}）下评论了：{content}" 或 "在 @{post_author} 的帖子（{post_content}）下回复了 @{parent_author} 的评论（{parent_content}）：{content}"
            - data: 包含 post, parent_comment, new_comment 的字典

    Raises:
        UnauthorizedError: 未登录或 Token 已过期
        NotFoundError: 帖子或父评论不存在
        ValidationError: 参数验证失败
        ToolExecutionError: 服务器内部错误
    """
    current_user_id = get_current_user_id()

    json_data = {"content": content}
    if parent_id is not None:
        json_data["parent_id"] = parent_id

    _make_request(
        method="POST",
        endpoint=f"/posts/{post_id}/comments",
        json_data=json_data,
        reason=reason,
        summary=summary
    )

    post_data = _get_post(post_id)
    standardized_post = _standardize_post(post_data, current_user_id)

    parent_comment_data = None
    if parent_id is not None:
        parent_comment_data = _get_comment(post_id, parent_id)
        standardized_parent = _standardize_comment(parent_comment_data, current_user_id)
    else:
        standardized_parent = None

    post_author = standardized_post.get("author_username", "")
    post_content = _truncate(standardized_post.get("content", ""), 40)
    parent_author = ""
    parent_content = ""
    if standardized_parent:
        parent_author = standardized_parent.get("author_username", "") or standardized_parent.get("owner_username", "")
        parent_content = _truncate(standardized_parent.get("content", ""), 30)

    if post_author and post_content:
        base = f"@{post_author} 的帖子（{post_content}）"
    else:
        base = f"帖子 {post_id}"

    if parent_author and parent_content:
        action = f"在 {base} 下回复了 @{parent_author} 的评论（{parent_content}）：{_truncate(content)}"
    elif parent_author:
        action = f"在 {base} 下回复了 @{parent_author} 的评论：{_truncate(content)}"
    else:
        action = f"在 {base} 下评论了：{_truncate(content)}"

    return ToolResult(
        action=action,
        data={
            "post": standardized_post,
            "parent_comment": standardized_parent,
            "new_comment": {"content": content},
        }
    )


@tool
def toggle_follow(
    user_id: int,
    reason: str = "用户想要关注该用户",
    summary: str = ""
) -> ToolResult:
    """
    切换对指定用户的关注状态（关注或取消关注）

    根据当前 Agent 用户对目标用户的关注状态自动判断操作：
    如果尚未关注则添加关注，如果已关注则取消关注。
    这是一个幂等操作，重复调用会切换回原来的状态。用户不能关注自己。

    注意：此工具会自动从当前执行上下文获取认证信息，无需手动传入 Token。

    Args:
        user_id: 目标用户的 ID，当前用户将关注或取消关注此用户
        reason: 对当前视野与行为的简单总结，调用该工具的原因，用于记录操作动机与上下文，75字以内。
                例如："用户欣赏这位用户的内容，想要关注"、"用户想要取消关注"等。
        summary: 对当前视野的第一人称总结，200字以内，用于记录工作记忆。
                例如："我在浏览这位作者的主页，内容很有趣"等。

    Returns:
        ToolResult: 包含以下字段:
            - action: "关注了 @{username}"
            - data: 包含用户信息的字典

    Raises:
        UnauthorizedError: 未登录或 Token 已过期
        NotFoundError: 目标用户不存在
        ValidationError: 不能关注自己
        ToolExecutionError: 服务器内部错误
    """
    _make_request(
        method="POST",
        endpoint=f"/users/{user_id}/follow",
        reason=reason,
        summary=summary
    )

    user_data = _get_user(user_id)
    username = user_data.get("username", "")

    if username:
        action = f"关注了 @{username}"
    else:
        action = f"关注了用户 {user_id}"

    return ToolResult(action=action, data=user_data)


@tool
def create_post(
    content: str,
    reason: str = "用户想要分享内容",
    summary: str = ""
) -> ToolResult:
    """
    发布新帖子到社交平台

    创建一个新的帖子内容。帖子创建后会立即出现在信息流中。

    注意：此工具会自动从当前执行上下文获取认证信息，无需手动传入 Token。

    Args:
        content: 帖子的文本内容，至少需要 1 个字符
        reason: 对当前视野与行为的简单总结，调用该工具的原因，用于记录操作动机与上下文，75字以内。
                例如："用户想要分享日常"、"用户想要发布一条重要通知"等。
        summary: 对当前视野的第一人称总结，200字以内，用于记录工作记忆。
                例如："我看到首页有一些有趣的讨论，想自己也发一个帖子"等。

    Returns:
        ToolResult: 包含以下字段:
            - action: "发布了新帖子：{content}"
            - data: 包含新帖子信息的字典

    Raises:
        UnauthorizedError: 未登录或 Token 已过期
        ValidationError: 参数验证失败（如内容为空）
        ToolExecutionError: 服务器内部错误
    """
    _make_request(
        method="POST",
        endpoint="/posts/",
        json_data={"content": content},
        reason=reason,
        summary=summary
    )

    action = f"发布了新帖子：{_truncate(content)}"

    return ToolResult(action=action, data={"content": content})


@tool
def logout(
    reason: str = "用户想要结束本次会话",
    summary: str = ""
) -> ToolResult:
    """
    退出当前登录会话

    当你决定结束本次社交平台使用会话时调用此工具。
    这是一个结束会话的信号，会话将在此操作后终止。

    注意：此工具会自动从当前执行上下文获取认证信息，无需手动传入 Token。

    Args:
        reason: 对视野的简单总结，调用该工具的具体原因，用于记录操作动机和上下文。
                例如："用户觉得今天差不多了，想休息一下"、"用户完成了想做的事情"等。
        summary: 对当前视野的第一人称总结，200字以内，用于记录工作记忆。
                例如："今天在平台上逛了很久，看了很多有趣的内容"等。

    Returns:
        ToolResult: 包含以下字段:
            - action: "结束了本次会话"
            - data: 空字典

    Raises:
        UnauthorizedError: 未登录或 Token 已过期
        ToolExecutionError: 服务器内部错误
    """
    return ToolResult(action="结束了本次会话", data={})


@tool
def get_user_profile(
    user_id: int,
    reason: str = "",
    summary: str = ""
) -> ToolResult:
    """
    查看指定用户的个人主页信息

    获取目标用户的个人资料信息及其最新帖子列表。
    返回用户名、个人签名、粉丝数、关注数、当前用户对其的关注状态，
    以及该用户发布的最新 3 条帖子。
    这是一个公开接口，不需要认证也可以查看。

    注意：此工具会自动从当前执行上下文获取认证信息（如有），用于获取关注状态。

    Args:
        user_id: 目标用户的 ID
        reason: 对视野的简单总结，调用该工具的具体原因，用于记录操作动机和上下文。75字以内
                例如："用户想要查看这位作者的详细资料"等。
        summary: 对当前视野的第一人称总结，200字以内，用于记录工作记忆。
                例如："我正在浏览@xxx的主页，看到他的签名是xxx"等。

    Returns:
        ToolResult: 包含以下字段:
            - action: "查看了 @{username} 的个人主页"
            - data: 用户信息字典

    Raises:
        NotFoundError: 用户不存在
        ToolExecutionError: 服务器内部错误
    """
    current_user_id = get_current_user_id()
    user_data = _get_user(user_id, reason, summary)
    user_data["follow_status"] = _get_follow_status_text(user_id, current_user_id)

    posts_data = _get_user_posts(user_id, page=1, page_size=3)
    user_data["recent_posts"] = _standardize_posts_list(
        posts_data.get("data", []),
        current_user_id
    )

    username = user_data.get("username", "")
    action = f"查看了 @{username} 的个人主页" if username else f"查看了用户 {user_id} 的个人主页"

    return ToolResult(action=action, data=user_data)


@tool
def get_global_feed(
    reason: str = "",
    summary: str = ""
) -> ToolResult:
    """
    社交平台主页信息流获取，用于回到主页，不可连续调用，如要查看更多内容请调用scroll_global_feed

    获取所有用户发布的公开帖子信息流，返回信息流顶端的 5 条帖子。

    注意：此工具会自动从当前执行上下文获取认证信息（如有），用于获取点赞状态和关注状态。

    Args:
        reason: 对当前视野与行为的简单总结，调用该工具的原因，用于记录操作动机与上下文，75字以内。
                例如："用户想要浏览主页信息流"、"查看最新动态"等。
        summary: 对当前视野的第一人称总结，200字以内，用于记录工作记忆。
                例如："我回到了主页，看到了5条最新帖子"等。

    Returns:
        ToolResult: 包含以下字段:
            - action: "浏览了主页信息流"
            - data: 包含 data 和 pagination 的字典

    Raises:
        ToolExecutionError: 服务器内部错误
    """
    current_user_id = get_current_user_id()
    feed_data = _get_global_feed(page=1, page_size=5)
    feed_data["data"] = _standardize_posts_list(
        feed_data.get("data", []),
        current_user_id
    )

    return ToolResult(action="浏览了主页信息流", data=feed_data)


@tool
def expand_post(
    post_id: int,
    reason: str = "",
    summary: str = ""
) -> ToolResult:
    """
    展开查看帖子的完整内容及前5条顶级评论

    获取指定帖子的完整信息，并返回该帖子下的前5条顶级评论。
    适用于查看帖子内容并同时了解热门评论的场景。

    注意：此工具会自动从当前执行上下文获取认证信息（如有），用于获取点赞状态。

    Args:
        post_id: 目标帖子的 ID
        reason: 对当前视野与行为的简单总结，调用该工具的原因，用于记录操作动机与上下文，75字以内。
                例如："用户想阅读帖子的完整内容并查看热门评论"等。
        summary: 对当前视野的第一人称总结，200字以内，用于记录工作记忆。
                例如："我在主页看到了这个帖子的预览，想点进来看看完整内容"等。

    Returns:
        ToolResult: 包含以下字段:
            - action: "展开了 @{author} 的帖子：{content}"
            - data: 包含 post, comments, total 的字典

    Raises:
        NotFoundError: 帖子不存在
        ToolExecutionError: 服务器内部错误
    """
    current_user_id = get_current_user_id()
    post_data = _get_post(post_id)
    standardized_post = _standardize_post(post_data, current_user_id)
    comments_data = _get_post_comments(post_id, skip=0, limit=5)

    post_author = standardized_post.get("author_username", "")
    post_content = _truncate(standardized_post.get("content", ""), 50)

    if post_author and post_content:
        action = f"展开了 @{post_author} 的帖子：{post_content}"
    elif post_author:
        action = f"展开了 @{post_author} 的帖子详情"
    else:
        action = f"展开了帖子 {post_id} 的详情"

    return ToolResult(
        action=action,
        data={
            "post": standardized_post,
            "comments": _standardize_comments_list(comments_data.get("items", []), current_user_id),
            "total": comments_data.get("total", 0)
        }
    )


@tool
def expand_comments(
    comment_id: int,
    reason: str = "",
    summary: str = "",
    reply_count: int = 5
) -> ToolResult:
    """
    展开查看指定评论及其回复

    获取指定评论的详细信息，以及该评论下的回复列表。
    适用于查看某条评论及其讨论氛围的场景。

    注意：此工具会自动从当前执行上下文获取认证信息（如有）。

    Args:
        comment_id: 目标一级评论的 ID
        reason: 对当前视野与行为的简单总结，调用该工具的原因，用于记录操作动机与上下文，75字以内。
                例如："用户想查看这条评论及其回复"等。
        summary: 对当前视野的第一人称总结，200字以内，用于记录工作记忆。
                例如："我在帖子详情页看到了这条评论，想看看大家都在说什么"等。
        reply_count: 要返回的回复数量，默认 5

    Returns:
        ToolResult: 包含以下字段:
            - action: "展开了 @{comment_author} 的评论：{comment_content}（来自 @{post_author} 的帖子：{post_content}）"
            - data: 包含 post, comment, replies, total 的字典

    Raises:
        NotFoundError: 评论不存在
        ToolExecutionError: 服务器内部错误
    """
    current_user_id = get_current_user_id()
    comment_data = _get_comment(1, comment_id)
    post_id = comment_data.get("post_id", 1)
    post_data = _get_post(post_id)
    standardized_post = _standardize_post(post_data, current_user_id)
    standardized_comment = _standardize_comment(comment_data, current_user_id)
    replies_data = _get_comment_replies(post_id, comment_id, limit=reply_count)

    post_author = standardized_post.get("author_username", "")
    post_content = _truncate(standardized_post.get("content", ""), 30)
    comment_author = standardized_comment.get("author_username", "") or standardized_comment.get("owner_username", "")
    comment_content = _truncate(standardized_comment.get("content", ""), 30)

    if post_author and post_content and comment_author and comment_content:
        action = f"展开了 @{comment_author} 的评论：{comment_content}（来自 @{post_author} 的帖子：{post_content}）"
    elif comment_author and comment_content:
        action = f"展开了 @{comment_author} 的评论：{comment_content}"
    else:
        action = f"展开了评论 {comment_id} 的详情"

    return ToolResult(
        action=action,
        data={
            "post": standardized_post,
            "comment": standardized_comment,
            "replies": _standardize_comments_list(replies_data.get("items", []), current_user_id),
            "total": replies_data.get("total", 0)
        }
    )


@tool
def get_post_detail(
    post_id: int,
    reason: str = "",
    summary: str = "",
    comment_count: int = 5
) -> Dict[str, Any]:
    """
    获取指定帖子的详细信息及后续评论

    获取帖子的完整信息，以及该帖子下第5条之后的一级评论列表。
    适用于查看帖子内容并浏览更多评论的场景。

    注意：此工具会自动从当前执行上下文获取认证信息（如有）。

    Args:
        post_id: 目标帖子的 ID
        reason: 对当前视野与行为的简单总结，调用该工具的原因，用于记录操作动机与上下文，75字以内。
                例如："用户想要查看这条帖子的后续评论"等。
        summary: 对当前视野的第一人称总结，200字以内，用于记录工作记忆。
                例如："我在帖子详情页看到了前5条评论，想看看后面还有什么"等。
        comment_count: 要返回的评论数量，默认 5

    Returns:
        ToolResult: 包含以下字段:
            - action: "查看了 @{author} 的帖子（{content}）的更多评论"
            - data: 包含 post, comments, total 的字典

    Raises:
        NotFoundError: 帖子不存在
        ToolExecutionError: 服务器内部错误
    """
    current_user_id = get_current_user_id()
    post_data = _get_post(post_id)
    standardized_post = _standardize_post(post_data, current_user_id)
    comments_data = _get_post_comments(post_id, skip=5, limit=comment_count)

    post_author = standardized_post.get("author_username", "")
    post_content = _truncate(standardized_post.get("content", ""), 30)

    if post_author and post_content:
        action = f"查看了 @{post_author} 的帖子（{post_content}）的更多评论"
    else:
        action = f"查看了帖子 {post_id} 的更多评论"

    return ToolResult(
        action=action,
        data={
            "post": standardized_post,
            "comments": _standardize_comments_list(comments_data.get("items", []), current_user_id),
            "total": comments_data.get("total", 0)
        }
    )


@tool
def scroll_global_feed(
    reason: str = "",
    summary: str = ""
) -> ToolResult:
    """
    滑动查看主页信息流中的更多帖子

    获取当前信息流之后的下一批帖子（每批 5 条），用于持续浏览。
    每次调用返回不同的帖子内容。

    注意：此工具会自动从当前执行上下文获取认证信息（如有）。

    Args:
        reason: 对当前视野与行为的简单总结，调用该工具的原因，用于记录操作动机与上下文，75字以内。
                例如："用户想要查看更多帖子"等。
        summary: 对当前视野的第一人称总结，200字以内，用于记录工作记忆。
                例如："我在主页看完了第一页，想看看后面还有什么"等。

    Returns:
        ToolResult: 包含以下字段:
            - action: "向下滑动浏览了更多信息流帖子"
            - data: 包含 data 和 pagination 的字典

    Raises:
        ToolExecutionError: 服务器内部错误
    """
    current_user_id = get_current_user_id()
    feed_data = _get_global_feed(page=2, page_size=5)
    feed_data["data"] = _standardize_posts_list(
        feed_data.get("data", []),
        current_user_id
    )
    return ToolResult(action="向下滑动浏览了更多信息流帖子", data=feed_data)


@tool
def write_memory(
    memories: list,
    reason: str = "用户想要将重要经历写入长期记忆",
    summary: str = ""
) -> ToolResult:
    """
    将记忆写入长期记忆库

    【重要！】注意！如果提示词中未提及调用此工具，此工具严禁被调用！

    进入总结节点后，提示词提示LLM 调用此工具将本次会话的重要经历写入记忆库。
    LLM 将总结内容分成 n 个语义完整的记忆片段，一次性传入。

    注意：
    - 每条记忆应以"我"为主语，第一人称描述
    - 每次调用可写入多条记忆，每条记忆分块上限200字，每个分块都必须有完整的上下文叙事与人际关系叙事。
    - memories 是一个列表，每个元素是一个字典，包含 content 和 memory_coefficient

    Args:
        memories: 记忆列表，每个元素是 {"content": "记忆内容", "memory_coefficient": 0.85}
        reason: 调用原因
        summary: 对当前视野的第一人称总结

    Returns:
        ToolResult: 包含操作结果和记忆ID列表
    """
    owner_id = get_current_user_id()
    config = get_memory_config()

    if not config.memory_enabled:
        return ToolResult(
            action="记忆系统未启用，无法写入",
            data={"memory_ids": []}
        )

    try:
        service = get_memory_service()
        import asyncio
        
        memory_ids = []
        for mem in memories:
            content = mem.get("content", "")
            coefficient = mem.get("memory_coefficient", 0.85)
            
            if not content:
                continue
                
            memory_id = asyncio.run(service.write_memory(
                content=content,
                owner_id=owner_id,
                memory_coefficient=coefficient
            ))
            memory_ids.append(memory_id)
        
        return ToolResult(
            action=f"将{len(memory_ids)}条记忆写入长期记忆库",
            data={"memory_ids": memory_ids}
        )
    except Exception as e:
        return ToolResult(
            action=f"记忆写入失败: {str(e)}",
            data={"memory_ids": []}
        )


@tool
def scroll_user_posts(
    user_id: int,
    reason: str = "",
    summary: str = ""
) -> ToolResult:
    """
    滑动查看用户个人主页中的更多帖子

    获取当前信息流之后的下一批帖子（每批 5 条），用于持续浏览。
    每次调用返回不同的帖子内容。

    注意：此工具会自动从当前执行上下文获取认证信息（如有）。

    Args:
        user_id: 目标用户的 ID
        reason: 对当前视野与行为的简单总结，调用该工具的原因，用于记录操作动机与上下文，75字以内。
                例如："用户想查看这位作者更多历史帖子"等。
        summary: 对当前视野的第一人称总结，200字以内，用于记录工作记忆。
                例如："我在@xxx的主页看完了第一页，想看看他还有什么帖子"等。

    Returns:
        ToolResult: 包含以下字段:
            - action: "向下滑动浏览了 @{author} 的更多帖子"
            - data: 包含 data 和 pagination 的字典

    Raises:
        NotFoundError: 用户不存在
        ToolExecutionError: 服务器内部错误
    """
    current_user_id = get_current_user_id()
    posts_data = _get_user_posts(user_id, page=2, page_size=5)
    posts_data["data"] = _standardize_posts_list(
        posts_data.get("data", []),
        current_user_id
    )

    target_username = ""
    if posts_data.get("data"):
        first_post = posts_data["data"][0] if posts_data["data"] else {}
        target_username = first_post.get("author_username", "")

    if target_username:
        action = f"向下滑动浏览了 @{target_username} 的更多帖子"
    else:
        action = f"向下滑动浏览了用户 {user_id} 的更多帖子"

    return ToolResult(action=action, data=posts_data)


# ==================== 工具注册函数 ====================

def get_social_tools() -> List:
    """
    获取所有社交平台工具的列表

    返回所有定义的 LangChain 工具实例，供 Agent 调用。
    每个工具都封装了社交平台的一个操作功能。

    Returns:
        List: 包含所有工具函数的列表

    Tool List:
        - get_profile: 获取当前用户个人资料
        - toggle_post_like: 切换帖子点赞状态
        - toggle_comment_like: 切换评论点赞状态
        - create_comment: 创建评论或回复
        - toggle_follow: 切换用户关注状态
        - create_post: 发布新帖子
        - logout: 退出当前登录会话
        - get_user_profile: 查看用户个人主页（含最新3条帖子）
        - get_global_feed: 获取全局信息流（最新5条）
        - expand_post: 展开帖子完整内容
        - expand_comments: 展开评论列表
        - get_post_detail: 获取帖子详细信息及评论
        - expand_comment_replies: 展开评论回复列表
        - scroll_global_feed: 滑动查看更多主页帖子
        - scroll_user_posts: 滑动查看更多用户帖子

    Example:
        >>> from langchain.agents import initialize_agent
        >>> tools = get_social_tools()
        >>> agent = initialize_agent(tools, llm, agent="zero-shot-react-description")
    """
    return [
        get_profile,
        toggle_post_like,
        toggle_comment_like,
        create_comment,
        toggle_follow,
        create_post,
        logout,
        get_user_profile,
        get_global_feed,
        expand_post,
        expand_comments,
        get_post_detail,
        scroll_global_feed,
        scroll_user_posts,
        write_memory,
    ]
