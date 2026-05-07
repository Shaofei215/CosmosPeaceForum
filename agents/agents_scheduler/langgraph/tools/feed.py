# Feed 工具函数
# 包含与信息流、帖子、评论浏览相关的工具

from typing import Optional, Dict, Any

from langchain_core.tools import tool

from agents.agents_scheduler.scheduler.context import get_current_user_id
from agents.agents_scheduler.langgraph.tools.types import ToolResult, NotFoundError, ToolExecutionError
from agents.agents_scheduler.langgraph.tools.utils import (
    _make_request, _get_post, _get_comment, _get_post_comments, _get_comment_replies,
    _get_global_feed, _get_user_posts,
    _standardize_post, _standardize_posts_list, _standardize_comment,
    _standardize_comments_list, _truncate
)


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
    post_content = _truncate(standardized_post.get("content", ""), 120)

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
    post_id: int,
    comment_id: int,
    reason: str = "",
    summary: str = "",
    reply_count: int = 5
) -> ToolResult:
    """
    展开查看评论及其回复

    获取指定评论的详细信息，以及该评论下的回复列表。
    适用于查看某条评论及其讨论氛围的场景。

    注意：此工具会自动从当前执行上下文获取认证信息（如有）。

    Args:
        post_id: 评论所属帖子的 ID
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
    comment_data = _get_comment(post_id, comment_id)
    post_data = _get_post(post_id)
    standardized_post = _standardize_post(post_data, current_user_id)
    standardized_comment = _standardize_comment(comment_data, current_user_id)
    replies_data = _get_comment_replies(post_id, comment_id, limit=reply_count)

    post_author = standardized_post.get("author_username", "")
    post_content = _truncate(standardized_post.get("content", ""), 120)
    comment_author = standardized_comment.get("author_username", "") or standardized_comment.get("owner_username", "")
    comment_content = _truncate(standardized_comment.get("content", ""), 120)

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
) -> ToolResult:
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
    post_content = _truncate(standardized_post.get("content", ""), 120)

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
