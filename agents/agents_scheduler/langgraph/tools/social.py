# 社交工具函数
# 包含与社交平台交互相关的所有工具

from typing import Optional

from langchain_core.tools import tool

from agents.agents_scheduler.scheduler.context import get_current_user_id
from agents.agents_scheduler.langgraph.tools.types import ToolResult, UnauthorizedError, NotFoundError, ValidationError, ToolExecutionError
from agents.agents_scheduler.langgraph.tools.utils import (
    _make_request, _get_user, _get_post, _get_comment, _get_user_posts, _get_follow_status_text,
    _standardize_post, _standardize_posts_list, _standardize_comment, _truncate
)


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
    post_content = _truncate(standardized_post.get("content", ""), 120)

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
    post_content = _truncate(standardized_post.get("content", ""), 120)
    comment_author = standardized_comment.get("author_username", "") or standardized_comment.get("owner_username", "")
    comment_content = _truncate(standardized_comment.get("content", ""), 120)

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
        parent_comment_data = _get_post(post_id, parent_id)
        standardized_parent = _standardize_comment(parent_comment_data, current_user_id)
    else:
        standardized_parent = None

    post_author = standardized_post.get("author_username", "")
    post_content = _truncate(standardized_post.get("content", ""), 120)
    parent_author = ""
    parent_content = ""
    if standardized_parent:
        parent_author = standardized_parent.get("author_username", "") or standardized_parent.get("owner_username", "")
        parent_content = _truncate(standardized_parent.get("content", ""), 120)

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
