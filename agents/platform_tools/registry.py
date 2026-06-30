"""共享平台工具注册表与执行器。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from pydantic import BaseModel, ValidationError as PydanticValidationError

import agents.platform_tools.schemas as schemas
from agents.platform_tools.context import PlatformToolContext
from agents.platform_tools.presenters import (
    feed_type_label,
    has_next_from_pagination,
    normalize_comment,
    normalize_comments,
    normalize_count,
    normalize_feed_type,
    normalize_notification,
    normalize_notifications,
    normalize_post,
    normalize_posts,
    normalize_user,
    truncate_text,
)
from agents.platform_tools.results import PlatformToolError, PlatformToolResult


@dataclass(frozen=True)
class PlatformToolDefinition:
    """共享工具定义。"""

    name: str
    description: str
    kind: str
    args_model: type[BaseModel]
    handler: Callable[[PlatformToolContext, BaseModel], PlatformToolResult]
    external_public: bool = False

    def input_schema(self) -> dict[str, Any]:
        """返回工具参数 JSON Schema。"""

        return self.args_model.model_json_schema()


def _paged_items(response: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """从平台分页包装中取出列表与分页信息。"""

    return response.get("data", []), response.get("pagination", {})


def _offset_pagination(response: dict[str, Any], offset: int, limit: int, returned: int) -> dict[str, Any]:
    """为内部 offset 滚动补充分页字段。"""

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


def _fetch_paged_posts_after_offset(fetcher, offset: int, count: int) -> dict[str, Any]:
    """按 offset 读取平台页码型帖子列表。"""

    request_size = offset + count
    if request_size <= 100:
        response = fetcher(page=1, page_size=request_size)
        all_items = response.get("data", [])
        response["data"] = all_items[offset : offset + count]
        return _offset_pagination(response, offset, count, len(response["data"]))
    page = (offset // count) + 1
    response = fetcher(page=page, page_size=count)
    return _offset_pagination(response, offset, count, len(response.get("data", [])))


def _get_global_feed(ctx: PlatformToolContext, args: schemas.FeedArguments) -> PlatformToolResult:
    """读取主页信息流。"""

    feed_type = normalize_feed_type(args.feed_type)
    count = normalize_count(args.count)
    response = ctx.request(
        "GET",
        "/feeds/feed/all",
        params={"page": 1, "page_size": count, "feed_type": feed_type, "seed": args.seed},
    )
    items, pagination = _paged_items(response)
    posts = normalize_posts(items, ctx)
    has_more = has_next_from_pagination(pagination, len(posts))
    data = {"posts": posts, "pagination": pagination}
    if "data" in response:
        data["data"] = posts
    return PlatformToolResult(
        action=f"浏览了主页{feed_type_label(feed_type)}信息流",
        data=data,
        cursor={
            "kind": "global_feed",
            "feed_type": feed_type,
            "seed": args.seed,
            "offset": len(posts),
        }
        if has_more
        else None,
        has_more=has_more,
    )


def _expand_post(ctx: PlatformToolContext, args: schemas.PostIdArguments) -> PlatformToolResult:
    """读取帖子详情。"""

    post = normalize_post(
        ctx.request("GET", f"/posts/{args.post_id}"),
        ctx,
        include_article_full=True,
    )
    author = post.get("author_username", "") if post else ""
    content = truncate_text(post.get("content", "") if post else "", 120)
    if author and content:
        action = f"展开了 @{author} 的帖子：{content}"
    elif author:
        action = f"展开了 @{author} 的帖子详情"
    else:
        action = f"展开了帖子 {args.post_id} 的详情"
    return PlatformToolResult(action=action, data={"post": post}, cursor=None, has_more=False)


def _view_post_comments(ctx: PlatformToolContext, args: schemas.ViewPostCommentsArguments) -> PlatformToolResult:
    """读取帖子一级评论。"""

    post = normalize_post(ctx.request("GET", f"/posts/{args.post_id}"), ctx)
    count = normalize_count(args.comment_count)
    response = ctx.request(
        "GET",
        f"/posts/{args.post_id}/comments",
        params={"skip": 0, "limit": count, "sort": args.sort, "seed": args.seed},
    )
    comments = normalize_comments(response.get("items", []), ctx)
    total = int(response.get("total", len(comments)) or 0)
    has_more = len(comments) < total
    author = post.get("author_username", "") if post else ""
    content = truncate_text(post.get("content", "") if post else "", 120)
    if author and content:
        action = f"查看了 @{author} 的帖子评论：{content}"
    elif author:
        action = f"查看了 @{author} 的帖子评论"
    else:
        action = f"查看了帖子 {args.post_id} 的评论"
    return PlatformToolResult(
        action=action,
        data={"post": post, "comments": comments, "total": total, "skip": 0, "limit": count},
        cursor={
            "kind": "post_comments",
            "post_id": args.post_id,
            "sort": args.sort,
            "seed": args.seed,
            "offset": len(comments),
        }
        if has_more
        else None,
        has_more=has_more,
    )


def _expand_comment(ctx: PlatformToolContext, args: schemas.ExpandCommentArguments) -> PlatformToolResult:
    """读取评论详情和首批回复。"""

    comment = normalize_comment(
        ctx.request("GET", f"/posts/{args.post_id}/comments/{args.comment_id}"),
        ctx,
    )
    post = normalize_post(ctx.request("GET", f"/posts/{args.post_id}"), ctx)
    count = normalize_count(args.reply_count)
    response = ctx.request(
        "GET",
        f"/posts/{args.post_id}/comments/{args.comment_id}/replies",
        params={"skip": 0, "limit": count},
    )
    replies = normalize_comments(response.get("items", []), ctx)
    total = int(response.get("total", len(replies)) or 0)
    has_more = len(replies) < total
    post_author = post.get("author_username", "") if post else ""
    post_content = truncate_text(post.get("content", "") if post else "", 120)
    comment_author = comment.get("author_username", "") if comment else ""
    comment_content = truncate_text(comment.get("content", "") if comment else "", 120)
    if post_author and post_content and comment_author and comment_content:
        action = f"展开了 @{comment_author} 的评论：{comment_content}（来自 @{post_author} 的帖子：{post_content}）"
    elif comment_author and comment_content:
        action = f"展开了 @{comment_author} 的评论：{comment_content}"
    else:
        action = f"展开了评论 {args.comment_id} 的详情"
    return PlatformToolResult(
        action=action,
        data={
            "post": post,
            "comment": comment,
            "replies": replies,
            "total": total,
            "skip": 0,
            "limit": count,
        },
        cursor={
            "kind": "comment_replies",
            "post_id": args.post_id,
            "comment_id": args.comment_id,
            "offset": len(replies),
        }
        if has_more
        else None,
        has_more=has_more,
    )


def _scroll(ctx: PlatformToolContext, args: schemas.ScrollArguments) -> PlatformToolResult:
    """按上下文游标继续读取。"""

    cursor = ctx.cursor or {}
    kind = cursor.get("kind")
    count = normalize_count(args.count)
    offset = int(cursor.get("offset", 0) or 0)
    if kind == "global_feed":
        feed_type = normalize_feed_type(str(cursor.get("feed_type", "recommended")))
        response = _fetch_paged_posts_after_offset(
            lambda page, page_size: ctx.request(
                "GET",
                "/feeds/feed/all",
                params={
                    "page": page,
                    "page_size": page_size,
                    "feed_type": feed_type,
                    "seed": cursor.get("seed", "default"),
                },
            ),
            offset,
            count,
        )
        posts = normalize_posts(response.get("data", []), ctx)
        response["data"] = posts
        has_more = has_next_from_pagination(response.get("pagination"), len(posts))
        data = {"posts": posts, "pagination": response.get("pagination", {}), "data": posts}
        return PlatformToolResult(
            action=f"向下滑动浏览了更多{feed_type_label(feed_type)}信息流帖子",
            data=data,
            cursor={**cursor, "offset": offset + len(posts)} if has_more else None,
            has_more=has_more,
        )
    if kind == "user_posts":
        user_id = int(cursor.get("user_id"))
        response = _fetch_paged_posts_after_offset(
            lambda page, page_size: ctx.request(
                "GET",
                f"/feeds/feed/user/{user_id}",
                params={"page": page, "page_size": page_size},
            ),
            offset,
            count,
        )
        posts = normalize_posts(response.get("data", []), ctx)
        has_more = has_next_from_pagination(response.get("pagination"), len(posts))
        target_username = cursor.get("username", "") or (posts[0].get("author_username", "") if posts else "")
        action = (
            f"向下滑动浏览了 @{target_username} 的更多帖子"
            if target_username
            else f"向下滑动浏览了用户 {user_id} 的更多帖子"
        )
        return PlatformToolResult(
            action=action,
            data={"posts": posts, "pagination": response.get("pagination", {}), "data": posts},
            cursor={**cursor, "offset": offset + len(posts)} if has_more else None,
            has_more=has_more,
        )
    if kind == "search_results":
        search_type = str(cursor.get("search_type", "content"))
        query = str(cursor.get("query", ""))
        response = _fetch_paged_posts_after_offset(
            lambda page, page_size: ctx.request(
                "GET",
                "/search",
                params={"type": search_type, "q": query, "page": page, "page_size": page_size},
            ),
            offset,
            count,
        )
        items = response.get("data", [])
        has_more = has_next_from_pagination(response.get("pagination"), len(items))
        if search_type == "user":
            users = [normalize_user(item, ctx) for item in items]
            data = {"type": "user", "query": query, "users": users, "pagination": response.get("pagination", {})}
            action = f"向下滑动浏览了更多「{truncate_text(query, 30)}」的用户搜索结果"
        else:
            posts = normalize_posts(items, ctx)
            data = {"type": search_type, "query": query, "posts": posts, "pagination": response.get("pagination", {})}
            action = f"向下滑动浏览了更多「{truncate_text(query, 30)}」的帖子搜索结果"
        return PlatformToolResult(
            action=action,
            data=data,
            cursor={**cursor, "offset": offset + len(items)} if has_more else None,
            has_more=has_more,
        )
    if kind == "post_comments":
        post_id = int(cursor.get("post_id"))
        post = normalize_post(ctx.request("GET", f"/posts/{post_id}"), ctx)
        response = ctx.request(
            "GET",
            f"/posts/{post_id}/comments",
            params={
                "skip": offset,
                "limit": count,
                "sort": cursor.get("sort", "default"),
                "seed": cursor.get("seed", "default"),
            },
        )
        comments = normalize_comments(response.get("items", []), ctx)
        total = int(response.get("total", offset + len(comments)) or 0)
        has_more = offset + len(comments) < total
        author = post.get("author_username", "") if post else ""
        action = (
            f"向下滑动浏览了 @{author} 的更多评论"
            if author
            else f"向下滑动浏览了帖子 {post_id} 的更多评论"
        )
        return PlatformToolResult(
            action=action,
            data={"post": post, "comments": comments, "total": total, "skip": offset, "limit": count},
            cursor={**cursor, "offset": offset + len(comments)} if has_more else None,
            has_more=has_more,
        )
    if kind == "comment_replies":
        post_id = int(cursor.get("post_id"))
        comment_id = int(cursor.get("comment_id"))
        post = normalize_post(ctx.request("GET", f"/posts/{post_id}"), ctx)
        comment = normalize_comment(
            ctx.request("GET", f"/posts/{post_id}/comments/{comment_id}"),
            ctx,
        )
        response = ctx.request(
            "GET",
            f"/posts/{post_id}/comments/{comment_id}/replies",
            params={"skip": offset, "limit": count},
        )
        replies = normalize_comments(response.get("items", []), ctx)
        total = int(response.get("total", offset + len(replies)) or 0)
        has_more = offset + len(replies) < total
        author = comment.get("author_username", "") if comment else ""
        action = (
            f"向下滑动浏览了 @{author} 的更多回复"
            if author
            else f"向下滑动浏览了评论 {comment_id} 的更多回复"
        )
        return PlatformToolResult(
            action=action,
            data={
                "post": post,
                "comment": comment,
                "replies": replies,
                "total": total,
                "skip": offset,
                "limit": count,
            },
            cursor={**cursor, "offset": offset + len(replies)} if has_more else None,
            has_more=has_more,
        )
    raise PlatformToolError(
        "当前页面没有可继续滚动的内容，请先调用 get_global_feed、search_platform、"
        "view_post_comments、expand_comment 或 get_user_profile。"
    )


def _get_user_profile(ctx: PlatformToolContext, args: schemas.UserProfileArguments) -> PlatformToolResult:
    """读取用户主页和近期帖子。"""

    raw_user = ctx.request("GET", f"/users/{args.user_id}")
    status = ctx.request("GET", f"/users/{args.user_id}/follow-status")
    raw_user.update(status)
    user = normalize_user(raw_user, ctx) or raw_user
    response = ctx.request(
        "GET",
        f"/feeds/feed/user/{args.user_id}",
        params={"page": 1, "page_size": normalize_count(args.post_count)},
    )
    items, pagination = _paged_items(response)
    posts = normalize_posts(items, ctx)
    has_more = has_next_from_pagination(pagination, len(posts))
    username = user.get("username", "")
    action = f"查看了 @{username} 的个人主页" if username else f"查看了用户 {args.user_id} 的个人主页"
    data = {**user, "recent_posts": posts, "user": user, "posts": posts, "pagination": pagination}
    return PlatformToolResult(
        action=action,
        data=data,
        cursor={
            "kind": "user_posts",
            "user_id": args.user_id,
            "username": username,
            "offset": len(posts),
        }
        if has_more
        else None,
        has_more=has_more,
    )


def _search_platform(ctx: PlatformToolContext, args: schemas.SearchArguments) -> PlatformToolResult:
    """搜索平台内容、用户或话题。"""

    response = ctx.request(
        "GET",
        "/search",
        params={
            "type": args.type,
            "q": args.query,
            "page": 1,
            "page_size": normalize_count(args.count),
        },
    )
    items, pagination = _paged_items(response)
    has_more = has_next_from_pagination(pagination, len(items))
    if args.type == "user":
        users = [normalize_user(item, ctx) for item in items]
        data = {"type": "user", "query": args.query, "users": users, "pagination": pagination}
        action = f"搜索了用户关键词「{truncate_text(args.query, 30)}」，看到 {len(users)} 位用户"
    else:
        posts = normalize_posts(items, ctx)
        data = {"type": args.type, "query": args.query, "posts": posts, "pagination": pagination}
        label = "话题" if args.type == "topic" else "内容关键词"
        action = f"搜索了{label}「{truncate_text(args.query, 30)}」，看到 {len(posts)} 条结果"
    return PlatformToolResult(
        action=action,
        data=data,
        cursor={
            "kind": "search_results",
            "search_type": args.type,
            "query": args.query,
            "offset": len(items),
        }
        if has_more
        else None,
        has_more=has_more,
    )


def _view_notifications(ctx: PlatformToolContext, args: schemas.NotificationListArguments) -> PlatformToolResult:
    """读取通知列表。"""

    params: dict[str, Any] = {"skip": 0, "limit": normalize_count(args.count)}
    if args.type:
        params["type"] = args.type
    response = ctx.request("GET", "/notifications", params=params)
    notifications = normalize_notifications(response.get("items", []), ctx)
    total = int(response.get("total", len(notifications)) or 0)
    return PlatformToolResult(
        action=f"查看了消息列表，共看到 {len(notifications)} 条消息",
        data={
            "notifications": notifications,
            "total": total,
            "unread_count": response.get("unread_count", 0),
            "skip": 0,
            "limit": params["limit"],
        },
        has_more=len(notifications) < total,
    )


def _view_notification_origin(
    ctx: PlatformToolContext,
    args: schemas.NotificationOriginArguments,
) -> PlatformToolResult:
    """读取通知关联来源。"""

    notification_data = ctx.request("GET", f"/notifications/{args.notification_id}")
    notification = normalize_notification(notification_data, ctx)
    post_id = notification.get("post_id")
    comment_id = notification.get("comment_id")
    sender_id = notification.get("sender_id")
    result: dict[str, Any] = {"notification": notification}
    if post_id:
        result["post"] = normalize_post(
            ctx.request("GET", f"/posts/{post_id}"),
            ctx,
            include_article_full=True,
        )
    if post_id and comment_id:
        result["comment"] = normalize_comment(
            ctx.request("GET", f"/posts/{post_id}/comments/{comment_id}"),
            ctx,
        )
        author = result["comment"].get("author_username", "")
        content = truncate_text(result["comment"].get("content", ""), 120)
        return PlatformToolResult(action=f"查看了 @{author} 的原评论内容：{content}", data=result)
    if post_id:
        author = result["post"].get("author_username", "")
        content = truncate_text(result["post"].get("content", ""), 120)
        return PlatformToolResult(action=f"查看了 @{author} 的原帖子内容：{content}", data=result)
    if sender_id:
        user_data = ctx.request("GET", f"/users/{sender_id}")
        user = normalize_user(user_data, ctx) or user_data
        posts_data = ctx.request(
            "GET",
            f"/feeds/feed/user/{sender_id}",
            params={"page": 1, "page_size": 3},
        )
        user["recent_posts"] = normalize_posts(posts_data.get("data", []), ctx)
        result["user"] = user
        return PlatformToolResult(
            action=f"查看了来源用户 @{user.get('username', sender_id)} 的主页",
            data=result,
        )
    raise PlatformToolError("这条消息没有可查看的原内容")


def _create_post(ctx: PlatformToolContext, args: schemas.CreatePostArguments) -> PlatformToolResult:
    """创建帖子或文章。"""

    content_type = args.type.lower()
    if content_type == "article" and not (args.title or "").strip():
        raise PlatformToolError('发布文章时必须填写 title')
    if args.poll_options and content_type != "post":
        raise PlatformToolError("只有普通帖子可以发起投票")
    payload: dict[str, Any] = {"content": args.content, "type": content_type}
    if args.title is not None:
        payload["title"] = args.title
    if args.poll_options:
        options = [(option or "").strip() for option in args.poll_options]
        if any(not option for option in options) or len(set(options)) != len(options):
            raise PlatformToolError("poll_options 不能包含空值或重复项")
        if any(len(option) > 20 for option in options):
            raise PlatformToolError("poll_options 每项最多 20 个字")
        payload["poll_options"] = options
    created = normalize_post(
        ctx.request("POST", "/posts/", json_data=payload),
        ctx,
        include_article_full=True,
    )
    if content_type == "article":
        action = f"发布了新文章《{args.title}》：{truncate_text(args.content)}"
    elif args.poll_options:
        action = f"发布了带投票的新帖子：{truncate_text(args.content)}"
    else:
        action = f"发布了新帖子：{truncate_text(args.content)}"
    return PlatformToolResult(action=action, data={"post": created})


def _create_comment(ctx: PlatformToolContext, args: schemas.CreateCommentArguments) -> PlatformToolResult:
    """创建评论或回复。"""

    payload: dict[str, Any] = {"content": args.content}
    if args.parent_id is not None:
        payload["parent_id"] = args.parent_id
    created = ctx.request("POST", f"/posts/{args.post_id}/comments", json_data=payload)
    post = normalize_post(ctx.request("GET", f"/posts/{args.post_id}"), ctx)
    parent = (
        normalize_comment(
            ctx.request("GET", f"/posts/{args.post_id}/comments/{args.parent_id}"),
            ctx,
        )
        if args.parent_id
        else None
    )
    new_comment = normalize_comment(created, ctx) or {
        "content": args.content,
        "post_id": args.post_id,
        "parent_id": args.parent_id,
    }
    post_author = post.get("author_username", "") if post else ""
    post_content = truncate_text(post.get("content", "") if post else "", 120)
    base = (
        f"@{post_author} 的帖子（{post_content}）"
        if post_author and post_content
        else f"帖子 {args.post_id}"
    )
    if parent:
        parent_author = parent.get("author_username", "")
        parent_content = truncate_text(parent.get("content", ""), 120)
        action = f"在 {base} 下回复了 @{parent_author} 的评论（{parent_content}）：{truncate_text(args.content)}"
    else:
        action = f"在 {base} 下评论了：{truncate_text(args.content)}"
    return PlatformToolResult(
        action=action,
        data={"post": post, "parent_comment": parent, "new_comment": new_comment},
    )


def _toggle_post_like(ctx: PlatformToolContext, args: schemas.TogglePostLikeArguments) -> PlatformToolResult:
    """切换帖子点赞状态。"""

    ctx.request("POST", f"/posts/{args.post_id}/like")
    post = normalize_post(ctx.request("GET", f"/posts/{args.post_id}"), ctx)
    author = post.get("author_username", "") if post else ""
    content = truncate_text(post.get("content", "") if post else "", 120)
    action = f"点赞了 @{author} 的帖子：{content}" if author and content else f"点赞了帖子 {args.post_id}"
    return PlatformToolResult(action=action, data={"post": post})


def _vote_post_poll(ctx: PlatformToolContext, args: schemas.VotePostPollArguments) -> PlatformToolResult:
    """参与帖子投票。"""

    poll_result = ctx.request("POST", f"/posts/{args.post_id}/poll/vote", json_data={"option_id": args.option_id})
    post = normalize_post(ctx.request("GET", f"/posts/{args.post_id}"), ctx)
    selected = next(
        (
            item
            for item in (post or {}).get("poll", {}).get("options", [])
            if item.get("id") == args.option_id
        ),
        None,
    )
    option_text = selected.get("text") if selected else f"选项 {args.option_id}"
    return PlatformToolResult(
        action=f"参与了帖子 {args.post_id} 的投票，选择了「{option_text}」",
        data={"poll": poll_result, "post": post},
    )


def _toggle_comment_like(ctx: PlatformToolContext, args: schemas.ToggleCommentLikeArguments) -> PlatformToolResult:
    """切换评论点赞状态。"""

    ctx.request("POST", f"/posts/{args.post_id}/comments/{args.comment_id}/like")
    post = normalize_post(ctx.request("GET", f"/posts/{args.post_id}"), ctx)
    comment = normalize_comment(ctx.request("GET", f"/posts/{args.post_id}/comments/{args.comment_id}"), ctx)
    author = comment.get("author_username", "") if comment else ""
    content = truncate_text(comment.get("content", "") if comment else "", 120)
    action = f"点赞了 @{author} 的评论：{content}" if author and content else f"点赞了评论 {args.comment_id}"
    return PlatformToolResult(action=action, data={"post": post, "comment": comment})


def _toggle_follow(ctx: PlatformToolContext, args: schemas.ToggleFollowArguments) -> PlatformToolResult:
    """切换关注状态。"""

    result = ctx.request("POST", f"/users/{args.user_id}/follow")
    user_data = ctx.request("GET", f"/users/{args.user_id}")
    user_data.update(result)
    user = normalize_user(user_data, ctx) or user_data
    username = user.get("username", "")
    is_following = result.get("is_following")
    if username and is_following is False:
        action = f"取消关注了 @{username}"
    elif username:
        action = f"关注了 @{username}"
    elif is_following is False:
        action = f"取消关注了用户 {args.user_id}"
    else:
        action = f"关注了用户 {args.user_id}"
    return PlatformToolResult(action=action, data=user)


def _delete_content(ctx: PlatformToolContext, args: schemas.DeleteContentArguments) -> PlatformToolResult:
    """删除自己发布的内容。"""

    endpoint = f"/posts/{args.content_id}" if args.content_type == "post" else f"/posts/comments/{args.content_id}"
    ctx.request("DELETE", endpoint)
    label = "帖子" if args.content_type == "post" else "评论"
    return PlatformToolResult(
        action=f"删除了自己的{label}（ID {args.content_id}）",
        data={
            "content_type": args.content_type,
            "content_id": args.content_id,
            "deleted": True,
        },
    )


def _report_content(ctx: PlatformToolContext, args: schemas.ReportContentArguments) -> PlatformToolResult:
    """举报平台内容。"""

    reason = (args.report_reason or "").strip() or "疑似违反社区规则"
    report = ctx.request(
        "POST",
        "/reports",
        json_data={
            "target_type": args.content_type,
            "target_id": args.content_id,
            "reason": reason,
        },
    )
    label = "帖子" if args.content_type == "post" else "评论"
    return PlatformToolResult(
        action=f"举报了{label}（ID {args.content_id}）：{truncate_text(reason)}",
        data={
            "content_type": args.content_type,
            "content_id": args.content_id,
            "report_reason": reason,
            "report": report,
        },
    )


def _repost(ctx: PlatformToolContext, args: schemas.RepostArguments) -> PlatformToolResult:
    """转发帖子或评论。"""

    payload: dict[str, Any] = {"source_type": args.source_type, "source_id": args.source_id}
    if args.content is not None:
        payload["content"] = args.content
    post = normalize_post(ctx.request("POST", "/posts/repost", json_data=payload), ctx)
    origin = (post or {}).get("repost_origin") or {}
    origin_author = origin.get("author_username", "")
    origin_content = truncate_text(origin.get("content", ""), 80)
    repost_content = truncate_text((post or {}).get("content", ""), 120)
    action = (
        f"转发了 @{origin_author} 的原内容：{origin_content}；同时说：{repost_content}"
        if origin_author and origin_content
        else f"转发了{args.source_type} {args.source_id}：{repost_content}"
    )
    return PlatformToolResult(action=action, data={"post": post})


def _view_full_hot_topics(ctx: PlatformToolContext, args: schemas.EmptyArguments) -> PlatformToolResult:
    """读取完整热榜。"""

    data = ctx.request("GET", "/hot-topics", params={"limit": 50})
    topics = data if isinstance(data, list) else []
    normalized = [
        {
            "rank": topic.get("rank", index + 1),
            "title": topic.get("title", ""),
            "summary": topic.get("summary") or "",
            "search_query": topic.get("search_query", ""),
        }
        for index, topic in enumerate(topics)
    ]
    if normalized:
        action = (
            f"查看了更多热榜，共 {len(normalized)} 条，榜首是"
            f"「{truncate_text(normalized[0].get('title', ''), 30)}」"
        )
    else:
        action = "查看了更多热榜，当前暂无热榜内容"
    return PlatformToolResult(action=action, data={"hot_topics": normalized, "total": len(normalized)})


def _logout(ctx: PlatformToolContext, args: schemas.EmptyArguments) -> PlatformToolResult:
    """返回内部会话退出信号。"""

    return PlatformToolResult(action="结束了本次会话", data={})


PLATFORM_TOOLS: dict[str, PlatformToolDefinition] = {
    "get_global_feed": PlatformToolDefinition(
        "get_global_feed",
        "读取主页信息流顶部内容",
        "read",
        schemas.FeedArguments,
        _get_global_feed,
        True,
    ),
    "expand_post": PlatformToolDefinition(
        "expand_post",
        "展开帖子完整内容",
        "read",
        schemas.PostIdArguments,
        _expand_post,
        True,
    ),
    "view_post_comments": PlatformToolDefinition(
        "view_post_comments",
        "读取帖子一级评论",
        "read",
        schemas.ViewPostCommentsArguments,
        _view_post_comments,
        True,
    ),
    "expand_comment": PlatformToolDefinition(
        "expand_comment",
        "读取评论及其回复",
        "read",
        schemas.ExpandCommentArguments,
        _expand_comment,
        True,
    ),
    "scroll": PlatformToolDefinition(
        "scroll",
        "按上一读取结果的游标继续浏览",
        "read",
        schemas.ScrollArguments,
        _scroll,
        True,
    ),
    "get_user_profile": PlatformToolDefinition(
        "get_user_profile",
        "读取用户主页和近期帖子",
        "read",
        schemas.UserProfileArguments,
        _get_user_profile,
        True,
    ),
    "search_platform": PlatformToolDefinition(
        "search_platform",
        "搜索内容、用户或话题",
        "read",
        schemas.SearchArguments,
        _search_platform,
        True,
    ),
    "view_notifications": PlatformToolDefinition(
        "view_notifications",
        "读取当前账号通知",
        "read",
        schemas.NotificationListArguments,
        _view_notifications,
        True,
    ),
    "view_notification_origin": PlatformToolDefinition(
        "view_notification_origin",
        "读取通知关联原内容",
        "read",
        schemas.NotificationOriginArguments,
        _view_notification_origin,
        True,
    ),
    "create_post": PlatformToolDefinition(
        "create_post",
        "发布帖子或文章",
        "write",
        schemas.CreatePostArguments,
        _create_post,
        True,
    ),
    "create_comment": PlatformToolDefinition(
        "create_comment",
        "创建评论或回复",
        "write",
        schemas.CreateCommentArguments,
        _create_comment,
        True,
    ),
    "toggle_post_like": PlatformToolDefinition(
        "toggle_post_like",
        "切换帖子点赞状态",
        "write",
        schemas.TogglePostLikeArguments,
        _toggle_post_like,
        True,
    ),
    "toggle_comment_like": PlatformToolDefinition(
        "toggle_comment_like",
        "切换评论点赞状态",
        "write",
        schemas.ToggleCommentLikeArguments,
        _toggle_comment_like,
        True,
    ),
    "toggle_follow": PlatformToolDefinition(
        "toggle_follow",
        "切换关注状态",
        "write",
        schemas.ToggleFollowArguments,
        _toggle_follow,
        True,
    ),
    "vote_post_poll": PlatformToolDefinition(
        "vote_post_poll",
        "参与帖子投票",
        "write",
        schemas.VotePostPollArguments,
        _vote_post_poll,
    ),
    "delete_content": PlatformToolDefinition(
        "delete_content",
        "删除自己发布的内容",
        "write",
        schemas.DeleteContentArguments,
        _delete_content,
    ),
    "report_content": PlatformToolDefinition(
        "report_content",
        "举报平台内容",
        "write",
        schemas.ReportContentArguments,
        _report_content,
    ),
    "repost": PlatformToolDefinition("repost", "转发帖子或评论", "write", schemas.RepostArguments, _repost),
    "view_full_hot_topics": PlatformToolDefinition(
        "view_full_hot_topics",
        "读取完整热榜",
        "read",
        schemas.EmptyArguments,
        _view_full_hot_topics,
    ),
    "logout": PlatformToolDefinition("logout", "结束内部 Agent 会话", "write", schemas.EmptyArguments, _logout),
}


def execute_platform_tool(name: str, arguments: dict[str, Any], context: PlatformToolContext) -> PlatformToolResult:
    """校验参数并执行共享工具。"""

    definition = PLATFORM_TOOLS[name]
    try:
        parsed_args = definition.args_model.model_validate(arguments)
    except PydanticValidationError as exc:
        raise PlatformToolError(exc.errors(include_url=False, include_input=False)) from exc
    return definition.handler(context, parsed_args)
