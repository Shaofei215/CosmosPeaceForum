# Feed 工具函数
# 包含与信息流、帖子、评论浏览相关的工具

from typing import Dict, Any

from langchain_core.tools import tool

from agents.agents_scheduler.scheduler.context import get_current_user_id
from agents.agents_scheduler.langgraph.tools.types import ToolResult, ToolExecutionError
from agents.agents_scheduler.langgraph.tools.utils import (
    _get_post, _get_comment, _get_post_comments, _get_comment_replies,
    _get_global_feed, _get_user_posts, _search_platform,
    _standardize_post, _standardize_posts_list, _standardize_comment,
    _standardize_comments_list, _truncate,
    _get_scroll_cursor, _set_scroll_cursor, _clear_scroll_cursor
)


def _normalize_feed_type(feed_type: str) -> str:
    value = (feed_type or "recommended").lower()
    aliases = {
        "hot": "recommended",
        "recommend": "recommended",
        "recommended": "recommended",
        "latest": "latest",
        "following": "following",
    }
    return aliases.get(value, "recommended")


def _feed_type_label(feed_type: str) -> str:
    return {
        "recommended": "推荐",
        "latest": "最新",
        "following": "关注",
    }.get(feed_type, "推荐")


def _normalize_count(count: int) -> int:
    try:
        value = int(count)
    except (TypeError, ValueError):
        value = 5
    return max(1, min(value, 20))


def _build_offset_pagination(
    response: Dict[str, Any],
    offset: int,
    limit: int,
    returned: int,
) -> Dict[str, Any]:
    pagination = response.get("pagination") or {}
    total = pagination.get("total", offset + returned)
    response["pagination"] = {
        **pagination,
        "offset": offset,
        "limit": limit,
        "returned": returned,
        "has_next": offset + returned < total,
    }
    return response


def _fetch_paged_posts_after_offset(fetcher, offset: int, count: int) -> Dict[str, Any]:
    request_size = offset + count
    if request_size <= 100:
        response = fetcher(page=1, page_size=request_size)
        all_items = response.get("data", [])
        response["data"] = all_items[offset:offset + count]
        return _build_offset_pagination(response, offset, count, len(response["data"]))

    page = (offset // count) + 1
    response = fetcher(page=page, page_size=count)
    return _build_offset_pagination(response, offset, count, len(response.get("data", [])))


@tool
def get_global_feed(
    feed_type: str = "recommended",
    seed: str = "default",
    reason: str = "",
    summary: str = ""
) -> ToolResult:
    """
    社交平台主页信息流获取，用于回到主页，不可连续调用，如要查看更多内容请调用 scroll

    获取指定类型的信息流顶端 5 条帖子。feed_type 可选：
    recommended（推荐，按热度排序）、latest（最新，按时间倒序）、following（关注的人，按推荐排序）。

    注意：此工具会自动从当前执行上下文获取认证信息（如有），用于获取点赞状态和关注状态。

    Args:
        feed_type: 信息流类型，必须是 "recommended"、"latest" 或 "following"。
                   也兼容 "hot"，会视为 "recommended"。
        seed: 推荐/关注流 Top-N 重排种子；scroll 会自动沿用这个 seed。
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
    normalized_feed_type = _normalize_feed_type(feed_type)
    feed_data = _get_global_feed(page=1, page_size=5, feed_type=normalized_feed_type, seed=seed)
    feed_data["data"] = _standardize_posts_list(
        feed_data.get("data", []),
        current_user_id
    )
    _set_scroll_cursor({
        "kind": "global_feed",
        "feed_type": normalized_feed_type,
        "seed": seed,
        "offset": len(feed_data.get("data", [])),
    })

    return ToolResult(action=f"浏览了主页{_feed_type_label(normalized_feed_type)}信息流", data=feed_data)


@tool
def expand_post(
    post_id: int,
    reason: str = "",
    summary: str = ""
) -> ToolResult:
    """
    展开查看帖子的完整内容

    获取指定帖子的完整信息。对于文章类型帖子，会返回 Markdown 全文。
    如需查看评论，请调用 view_post_comments；如需继续看后续评论，再调用 scroll。

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
            - data: 包含 post 的字典

    Raises:
        NotFoundError: 帖子不存在
        ToolExecutionError: 服务器内部错误
    """
    current_user_id = get_current_user_id()
    post_data = _get_post(post_id)
    standardized_post = _standardize_post(post_data, current_user_id, include_article_full=True)
    _clear_scroll_cursor()

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
        data={"post": standardized_post}
    )


@tool
def view_post_comments(
    post_id: int,
    reason: str = "",
    summary: str = "",
    comment_count: int = 5,
    sort: str = "default",
    seed: str = "default"
) -> ToolResult:
    """
    查看指定帖子下的一级评论

    获取指定帖子下的第一批一级评论。之后继续调用 scroll，可查看后续一级评论。

    注意：此工具会自动从当前执行上下文获取认证信息（如有）。

    Args:
        post_id: 目标帖子的 ID
        reason: 对当前视野与行为的简单总结，调用该工具的原因，用于记录操作动机与上下文，75字以内。
                例如："用户想查看这条帖子的评论"等。
        summary: 对当前视野的第一人称总结，200字以内，用于记录工作记忆。
                例如："我读完帖子后想看看评论区的讨论"等。
        comment_count: 要返回的一级评论数量，默认 5
        sort: 评论排序，default（推荐）或 latest（最新）
        seed: 默认评论流 Top-N 重排种子，同一 seed 下分页稳定

    Returns:
        ToolResult: 包含以下字段:
            - action: "查看了 @{author} 的帖子评论"
            - data: 包含 post, comments, total 的字典

    Raises:
        NotFoundError: 帖子不存在
        ToolExecutionError: 服务器内部错误
    """
    current_user_id = get_current_user_id()
    post_data = _get_post(post_id)
    standardized_post = _standardize_post(post_data, current_user_id)
    count = _normalize_count(comment_count)
    comments_data = _get_post_comments(post_id, skip=0, limit=count, sort=sort, seed=seed)
    comments = _standardize_comments_list(comments_data.get("items", []), current_user_id)
    _set_scroll_cursor({
        "kind": "post_comments",
        "post_id": post_id,
        "sort": sort,
        "seed": seed,
        "offset": len(comments),
    })

    post_author = standardized_post.get("author_username", "")
    post_content = _truncate(standardized_post.get("content", ""), 120)

    if post_author and post_content:
        action = f"查看了 @{post_author} 的帖子评论：{post_content}"
    elif post_author:
        action = f"查看了 @{post_author} 的帖子评论"
    else:
        action = f"查看了帖子 {post_id} 的评论"

    return ToolResult(
        action=action,
        data={
            "post": standardized_post,
            "comments": comments,
            "total": comments_data.get("total", 0),
            "skip": 0,
            "limit": count,
        }
    )


@tool
def expand_comment(
    post_id: int,
    comment_id: int,
    reason: str = "",
    summary: str = "",
    reply_count: int = 5
) -> ToolResult:
    """
    展开查看评论及其回复

    获取指定评论的详细信息，以及该评论下的第一批回复。
    之后继续调用 scroll，可查看该评论下的后续回复。

    注意：此工具会自动从当前执行上下文获取认证信息（如有）。

    Args:
        post_id: 评论所属帖子的 ID
        comment_id: 目标一级评论的 ID
        reason: 对当前视野与行为的简单总结，调用该工具的原因，用于记录操作动机与上下文，75字以内。
                例如："用户想查看这条评论及其回复"等。
        summary: 对当前视野的第一人称总结，200字以内，用于记录工作记忆。
                例如："我在评论区看到了这条评论，想看看下面的回复"等。
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
    count = _normalize_count(reply_count)
    replies_data = _get_comment_replies(post_id, comment_id, skip=0, limit=count)
    replies = _standardize_comments_list(replies_data.get("items", []), current_user_id)
    _set_scroll_cursor({
        "kind": "comment_replies",
        "post_id": post_id,
        "comment_id": comment_id,
        "offset": len(replies),
    })

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
            "replies": replies,
            "total": replies_data.get("total", 0),
            "skip": 0,
            "limit": count,
        }
    )


@tool
def scroll(
    count: int = 5,
    reason: str = "",
    summary: str = ""
) -> ToolResult:
    """
    向下滑动当前页面，自动查看后续内容

    该工具不需要知道当前位置，会自动延续最近一次打开的可滚动页面：
    get_global_feed 之后继续加载主页信息流；search_platform 之后继续加载搜索结果；
    view_post_comments 之后继续加载一级评论；expand_comment 之后继续加载该评论下的回复；
    get_user_profile 之后继续加载用户主页帖子。

    注意：此工具会自动从当前执行上下文获取认证信息（如有）。

    Args:
        count: 本次查看数量，默认 5，范围 1-20。
        reason: 对当前视野与行为的简单总结，调用该工具的原因，用于记录操作动机与上下文，75字以内。
                例如："用户想要继续往下看"等。
        summary: 对当前视野的第一人称总结，200字以内，用于记录工作记忆。
                例如："我看完了当前页面，想看看后面还有什么"等。

    Returns:
        ToolResult: 包含以下字段:
            - action: "向下滑动浏览了更多内容"
            - data: 后续帖子、评论或回复

    Raises:
        ToolExecutionError: 服务器内部错误
    """
    current_user_id = get_current_user_id()
    cursor = _get_scroll_cursor()
    count = _normalize_count(count)
    kind = cursor.get("kind")

    if kind == "global_feed":
        normalized_feed_type = _normalize_feed_type(cursor.get("feed_type", "recommended"))
        offset = int(cursor.get("offset", 0))
        seed = cursor.get("seed", "default")
        feed_data = _fetch_paged_posts_after_offset(
            lambda page, page_size: _get_global_feed(
                page=page,
                page_size=page_size,
                feed_type=normalized_feed_type,
                seed=seed,
            ),
            offset,
            count,
        )
        feed_data["data"] = _standardize_posts_list(feed_data.get("data", []), current_user_id)
        _set_scroll_cursor({**cursor, "offset": offset + len(feed_data.get("data", []))})
        return ToolResult(
            action=f"向下滑动浏览了更多{_feed_type_label(normalized_feed_type)}信息流帖子",
            data=feed_data,
        )

    if kind == "user_posts":
        user_id = cursor.get("user_id")
        offset = int(cursor.get("offset", 0))
        posts_data = _fetch_paged_posts_after_offset(
            lambda page, page_size: _get_user_posts(user_id, page=page, page_size=page_size),
            offset,
            count,
        )
        posts_data["data"] = _standardize_posts_list(posts_data.get("data", []), current_user_id)
        _set_scroll_cursor({**cursor, "offset": offset + len(posts_data.get("data", []))})

        target_username = cursor.get("username", "")
        if not target_username and posts_data.get("data"):
            target_username = posts_data["data"][0].get("author_username", "")
        action = f"向下滑动浏览了 @{target_username} 的更多帖子" if target_username else f"向下滑动浏览了用户 {user_id} 的更多帖子"
        return ToolResult(action=action, data=posts_data)

    if kind == "search_results":
        search_type = cursor.get("search_type", "content")
        query = cursor.get("query", "")
        offset = int(cursor.get("offset", 0))
        search_data = _fetch_paged_posts_after_offset(
            lambda page, page_size: _search_platform(
                search_type=search_type,
                query=query,
                page=page,
                page_size=page_size,
            ),
            offset,
            count,
        )
        _set_scroll_cursor({**cursor, "offset": offset + len(search_data.get("data", []))})

        if search_type == "content":
            posts = _standardize_posts_list(search_data.get("data", []), current_user_id)
            return ToolResult(
                action=f"向下滑动浏览了更多「{_truncate(query, 30)}」的帖子搜索结果",
                data={
                    "type": "content",
                    "query": query,
                    "posts": posts,
                    "pagination": search_data.get("pagination", {}),
                },
            )

        users = search_data.get("data", [])
        return ToolResult(
            action=f"向下滑动浏览了更多「{_truncate(query, 30)}」的用户搜索结果",
            data={
                "type": "user",
                "query": query,
                "users": users,
                "pagination": search_data.get("pagination", {}),
            },
        )

    if kind == "post_comments":
        post_id = cursor.get("post_id")
        offset = int(cursor.get("offset", 0))
        post_data = _get_post(post_id)
        standardized_post = _standardize_post(post_data, current_user_id)
        comments_data = _get_post_comments(
            post_id,
            skip=offset,
            limit=count,
            sort=cursor.get("sort", "default"),
            seed=cursor.get("seed", "default"),
        )
        comments = _standardize_comments_list(comments_data.get("items", []), current_user_id)
        _set_scroll_cursor({**cursor, "offset": offset + len(comments)})
        post_author = standardized_post.get("author_username", "")
        action = f"向下滑动浏览了 @{post_author} 的更多评论" if post_author else f"向下滑动浏览了帖子 {post_id} 的更多评论"
        return ToolResult(
            action=action,
            data={
                "post": standardized_post,
                "comments": comments,
                "total": comments_data.get("total", 0),
                "skip": offset,
                "limit": count,
            },
        )

    if kind == "comment_replies":
        post_id = cursor.get("post_id")
        comment_id = cursor.get("comment_id")
        offset = int(cursor.get("offset", 0))
        post_data = _get_post(post_id)
        comment_data = _get_comment(post_id, comment_id)
        standardized_post = _standardize_post(post_data, current_user_id)
        standardized_comment = _standardize_comment(comment_data, current_user_id)
        replies_data = _get_comment_replies(post_id, comment_id, skip=offset, limit=count)
        replies = _standardize_comments_list(replies_data.get("items", []), current_user_id)
        _set_scroll_cursor({**cursor, "offset": offset + len(replies)})
        comment_author = standardized_comment.get("author_username", "") or standardized_comment.get("owner_username", "")
        action = f"向下滑动浏览了 @{comment_author} 的更多回复" if comment_author else f"向下滑动浏览了评论 {comment_id} 的更多回复"
        return ToolResult(
            action=action,
            data={
                "post": standardized_post,
                "comment": standardized_comment,
                "replies": replies,
                "total": replies_data.get("total", 0),
                "skip": offset,
                "limit": count,
            },
        )

    raise ToolExecutionError("当前页面没有可继续滚动的内容，请先调用 get_global_feed、search_platform、view_post_comments、expand_comment 或 get_user_profile。")
