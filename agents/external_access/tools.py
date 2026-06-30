"""外部 Agent 工具注册与执行。

工具实现通过 `PlatformClient` 调用公开平台 API，并由客户端统一附加可信 agents
服务身份。所有工具参数来自当前 HTTP 请求，不读取 Scheduler 上下文、长期记忆或
Management 数据库业务状态。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from pydantic import BaseModel, ValidationError as PydanticValidationError

from agents.external_access.cursor import CursorError, decode_cursor, encode_cursor
from agents.external_access.presenters import (
    has_next_from_pagination,
    normalize_comment,
    normalize_comments,
    normalize_notification,
    normalize_post,
    normalize_posts,
    normalize_user,
    truncate_text,
)
from agents.external_access.schemas import (
    CommentArguments,
    CreateCommentArguments,
    CreatePostArguments,
    ExpandCommentArguments,
    FeedArguments,
    NotificationListArguments,
    NotificationOriginArguments,
    PostIdArguments,
    ScrollArguments,
    SearchArguments,
    ToggleCommentLikeArguments,
    ToggleFollowArguments,
    TogglePostLikeArguments,
    UserProfileArguments,
    ViewPostCommentsArguments,
)
from agents.platform_access import PlatformClient


class ExternalToolError(Exception):
    """外部工具参数或游标错误。"""


@dataclass
class ExternalToolContext:
    """单次外部工具调用上下文。

    Args:
        client: 显式 Token 平台客户端。
        access_token: 当前普通账号 access token。
        current_user: `/auth/me` 预检返回的账号信息。
        cursor_secret: 滚动游标签名密钥。
    """

    client: PlatformClient
    access_token: str
    current_user: dict[str, Any]
    cursor_secret: str


@dataclass
class ExternalToolResult:
    """内部工具执行结果。"""

    action: str
    data: dict[str, Any]
    scroll_cursor: str | None = None
    has_more: bool = False


@dataclass
class ExternalToolDefinition:
    """工具注册表条目。"""

    name: str
    description: str
    kind: str
    args_model: type[BaseModel]
    handler: Callable[[ExternalToolContext, BaseModel], ExternalToolResult]

    def input_schema(self) -> dict[str, Any]:
        """返回工具参数 JSON Schema。"""

        return self.args_model.model_json_schema()


def _normalize_feed_type(feed_type: str) -> str:
    """归一化信息流类型。"""

    return {"hot": "recommended", "recommend": "recommended"}.get(feed_type, feed_type)


def _feed_label(feed_type: str) -> str:
    """返回信息流中文标签。"""

    return {"recommended": "推荐", "latest": "最新", "following": "关注"}.get(feed_type, "推荐")


def _paged_items(response: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """从平台分页包装中提取列表与分页。"""

    return response.get("data", []), response.get("pagination", {})


def _make_cursor(ctx: ExternalToolContext, payload: dict[str, Any], has_more: bool) -> str | None:
    """按 has_more 决定是否生成下一页游标。"""

    if not has_more:
        return None
    return encode_cursor(payload, ctx.cursor_secret)


def _get_global_feed(ctx: ExternalToolContext, args: FeedArguments) -> ExternalToolResult:
    """读取主页信息流。"""

    feed_type = _normalize_feed_type(args.feed_type)
    response = ctx.client.request(
        "GET",
        "/feeds/feed/all",
        access_token=ctx.access_token,
        params={"page": 1, "page_size": args.count, "feed_type": feed_type, "seed": args.seed},
    )
    items, pagination = _paged_items(response)
    posts = normalize_posts(items)
    has_more = has_next_from_pagination(pagination, len(posts))
    return ExternalToolResult(
        action=f"浏览了主页{_feed_label(feed_type)}信息流",
        data={"posts": posts, "pagination": pagination},
        scroll_cursor=_make_cursor(
            ctx,
            {"kind": "global_feed", "feed_type": feed_type, "seed": args.seed, "offset": len(posts)},
            has_more,
        ),
        has_more=has_more,
    )


def _expand_post(ctx: ExternalToolContext, args: PostIdArguments) -> ExternalToolResult:
    """读取帖子详情。"""

    post = normalize_post(
        ctx.client.request("GET", f"/posts/{args.post_id}", access_token=ctx.access_token),
        include_article_full=True,
    )
    author = post.get("author_username") if post else ""
    content = truncate_text(post.get("content") if post else "")
    action = f"展开了 @{author} 的帖子：{content}" if author else f"展开了帖子 {args.post_id}"
    return ExternalToolResult(action=action, data={"post": post})


def _view_post_comments(ctx: ExternalToolContext, args: ViewPostCommentsArguments) -> ExternalToolResult:
    """读取帖子一级评论。"""

    post = normalize_post(ctx.client.request("GET", f"/posts/{args.post_id}", access_token=ctx.access_token))
    response = ctx.client.request(
        "GET",
        f"/posts/{args.post_id}/comments",
        access_token=ctx.access_token,
        params={"skip": 0, "limit": args.comment_count, "sort": args.sort, "seed": args.seed},
    )
    comments = normalize_comments(response.get("items", []))
    total = int(response.get("total", len(comments)) or 0)
    has_more = len(comments) < total
    return ExternalToolResult(
        action=f"查看了帖子 {args.post_id} 的评论",
        data={"post": post, "comments": comments, "total": total, "skip": 0, "limit": args.comment_count},
        scroll_cursor=_make_cursor(
            ctx,
            {
                "kind": "post_comments",
                "post_id": args.post_id,
                "sort": args.sort,
                "seed": args.seed,
                "offset": len(comments),
            },
            has_more,
        ),
        has_more=has_more,
    )


def _expand_comment(ctx: ExternalToolContext, args: ExpandCommentArguments) -> ExternalToolResult:
    """读取评论及其回复。"""

    post = normalize_post(ctx.client.request("GET", f"/posts/{args.post_id}", access_token=ctx.access_token))
    comment = normalize_comment(
        ctx.client.request(
            "GET",
            f"/posts/{args.post_id}/comments/{args.comment_id}",
            access_token=ctx.access_token,
        )
    )
    response = ctx.client.request(
        "GET",
        f"/posts/{args.post_id}/comments/{args.comment_id}/replies",
        access_token=ctx.access_token,
        params={"skip": 0, "limit": args.reply_count},
    )
    replies = normalize_comments(response.get("items", []))
    total = int(response.get("total", len(replies)) or 0)
    has_more = len(replies) < total
    return ExternalToolResult(
        action=f"展开了评论 {args.comment_id} 的详情",
        data={
            "post": post,
            "comment": comment,
            "replies": replies,
            "total": total,
            "skip": 0,
            "limit": args.reply_count,
        },
        scroll_cursor=_make_cursor(
            ctx,
            {"kind": "comment_replies", "post_id": args.post_id, "comment_id": args.comment_id, "offset": len(replies)},
            has_more,
        ),
        has_more=has_more,
    )


def _scroll(ctx: ExternalToolContext, args: ScrollArguments) -> ExternalToolResult:
    """按签名游标继续读取。"""

    try:
        cursor = decode_cursor(args.scroll_cursor, ctx.cursor_secret)
    except CursorError as exc:
        raise ExternalToolError(str(exc)) from exc

    kind = cursor.get("kind")
    offset = int(cursor.get("offset", 0) or 0)
    if kind == "global_feed":
        feed_type = _normalize_feed_type(str(cursor.get("feed_type", "recommended")))
        response = ctx.client.request(
            "GET",
            "/feeds/feed/all",
            access_token=ctx.access_token,
            params={
                "page": offset // args.count + 1,
                "page_size": args.count,
                "feed_type": feed_type,
                "seed": cursor.get("seed", "default"),
            },
        )
        items, pagination = _paged_items(response)
        posts = normalize_posts(items)
        has_more = has_next_from_pagination(pagination, len(posts))
        next_offset = offset + len(posts)
        return ExternalToolResult(
            action=f"向下滑动浏览了更多{_feed_label(feed_type)}信息流帖子",
            data={"posts": posts, "pagination": pagination},
            scroll_cursor=_make_cursor(ctx, {**cursor, "offset": next_offset}, has_more),
            has_more=has_more,
        )

    if kind == "user_posts":
        user_id = int(cursor.get("user_id"))
        response = ctx.client.request(
            "GET",
            f"/feeds/feed/user/{user_id}",
            access_token=ctx.access_token,
            params={"page": offset // args.count + 1, "page_size": args.count},
        )
        items, pagination = _paged_items(response)
        posts = normalize_posts(items)
        has_more = has_next_from_pagination(pagination, len(posts))
        return ExternalToolResult(
            action=f"向下滑动浏览了用户 {user_id} 的更多帖子",
            data={"posts": posts, "pagination": pagination},
            scroll_cursor=_make_cursor(ctx, {**cursor, "offset": offset + len(posts)}, has_more),
            has_more=has_more,
        )

    if kind == "search_results":
        search_type = str(cursor.get("search_type", "content"))
        query = str(cursor.get("query", ""))
        response = ctx.client.request(
            "GET",
            "/search",
            access_token=ctx.access_token,
            params={"type": search_type, "q": query, "page": offset // args.count + 1, "page_size": args.count},
        )
        items, pagination = _paged_items(response)
        has_more = has_next_from_pagination(pagination, len(items))
        data_key = "users" if search_type == "user" else "posts"
        values = [normalize_user(item) for item in items] if search_type == "user" else normalize_posts(items)
        return ExternalToolResult(
            action=f"向下滑动浏览了更多「{truncate_text(query, 30)}」搜索结果",
            data={"type": search_type, "query": query, data_key: values, "pagination": pagination},
            scroll_cursor=_make_cursor(ctx, {**cursor, "offset": offset + len(items)}, has_more),
            has_more=has_more,
        )

    if kind == "post_comments":
        post_id = int(cursor.get("post_id"))
        response = ctx.client.request(
            "GET",
            f"/posts/{post_id}/comments",
            access_token=ctx.access_token,
            params={
                "skip": offset,
                "limit": args.count,
                "sort": cursor.get("sort", "default"),
                "seed": cursor.get("seed", "default"),
            },
        )
        comments = normalize_comments(response.get("items", []))
        total = int(response.get("total", offset + len(comments)) or 0)
        has_more = offset + len(comments) < total
        return ExternalToolResult(
            action=f"向下滑动浏览了帖子 {post_id} 的更多评论",
            data={"comments": comments, "total": total, "skip": offset, "limit": args.count},
            scroll_cursor=_make_cursor(ctx, {**cursor, "offset": offset + len(comments)}, has_more),
            has_more=has_more,
        )

    if kind == "comment_replies":
        post_id = int(cursor.get("post_id"))
        comment_id = int(cursor.get("comment_id"))
        response = ctx.client.request(
            "GET",
            f"/posts/{post_id}/comments/{comment_id}/replies",
            access_token=ctx.access_token,
            params={"skip": offset, "limit": args.count},
        )
        replies = normalize_comments(response.get("items", []))
        total = int(response.get("total", offset + len(replies)) or 0)
        has_more = offset + len(replies) < total
        return ExternalToolResult(
            action=f"向下滑动浏览了评论 {comment_id} 的更多回复",
            data={"replies": replies, "total": total, "skip": offset, "limit": args.count},
            scroll_cursor=_make_cursor(ctx, {**cursor, "offset": offset + len(replies)}, has_more),
            has_more=has_more,
        )

    raise ExternalToolError("当前 scroll_cursor 不支持继续滚动")


def _get_user_profile(ctx: ExternalToolContext, args: UserProfileArguments) -> ExternalToolResult:
    """读取用户主页和近期帖子。"""

    user = normalize_user(ctx.client.request("GET", f"/users/{args.user_id}", access_token=ctx.access_token))
    status = ctx.client.request(
        "GET",
        f"/users/{args.user_id}/follow-status",
        access_token=ctx.access_token,
    )
    if user:
        user.update(status)
    response = ctx.client.request(
        "GET",
        f"/feeds/feed/user/{args.user_id}",
        access_token=ctx.access_token,
        params={"page": 1, "page_size": args.post_count},
    )
    items, pagination = _paged_items(response)
    posts = normalize_posts(items)
    has_more = has_next_from_pagination(pagination, len(posts))
    return ExternalToolResult(
        action=f"查看了用户 {args.user_id} 的主页",
        data={"user": user, "posts": posts, "pagination": pagination},
        scroll_cursor=_make_cursor(ctx, {"kind": "user_posts", "user_id": args.user_id, "offset": len(posts)}, has_more),
        has_more=has_more,
    )


def _search_platform(ctx: ExternalToolContext, args: SearchArguments) -> ExternalToolResult:
    """搜索平台内容、用户或话题。"""

    response = ctx.client.request(
        "GET",
        "/search",
        access_token=ctx.access_token,
        params={"type": args.type, "q": args.query, "page": 1, "page_size": args.count},
    )
    items, pagination = _paged_items(response)
    has_more = has_next_from_pagination(pagination, len(items))
    if args.type == "user":
        users = [normalize_user(item) for item in items]
        data = {"type": args.type, "query": args.query, "users": users, "pagination": pagination}
    else:
        posts = normalize_posts(items)
        data = {"type": args.type, "query": args.query, "posts": posts, "pagination": pagination}
    return ExternalToolResult(
        action=f"搜索了「{truncate_text(args.query, 30)}」",
        data=data,
        scroll_cursor=_make_cursor(
            ctx,
            {"kind": "search_results", "search_type": args.type, "query": args.query, "offset": len(items)},
            has_more,
        ),
        has_more=has_more,
    )


def _view_notifications(ctx: ExternalToolContext, args: NotificationListArguments) -> ExternalToolResult:
    """读取通知列表。"""

    params: dict[str, Any] = {"skip": 0, "limit": args.count}
    if args.type:
        params["type"] = args.type
    response = ctx.client.request("GET", "/notifications", access_token=ctx.access_token, params=params)
    notifications = [normalize_notification(item) for item in response.get("items", [])]
    total = int(response.get("total", len(notifications)) or 0)
    return ExternalToolResult(
        action=f"查看了消息列表，共看到 {len(notifications)} 条消息",
        data={
            "notifications": notifications,
            "total": total,
            "unread_count": response.get("unread_count", 0),
            "skip": 0,
            "limit": args.count,
        },
        has_more=len(notifications) < total,
    )


def _view_notification_origin(ctx: ExternalToolContext, args: NotificationOriginArguments) -> ExternalToolResult:
    """读取通知关联来源。"""

    notification = normalize_notification(
        ctx.client.request("GET", f"/notifications/{args.notification_id}", access_token=ctx.access_token)
    )
    origin = ctx.client.request(
        "GET",
        f"/notifications/{args.notification_id}/origin",
        access_token=ctx.access_token,
    )
    return ExternalToolResult(
        action=f"查看了消息 {args.notification_id} 的原内容",
        data={
            "notification": notification,
            "post": normalize_post(origin.get("post")),
            "comment": normalize_comment(origin.get("comment")),
            "user": normalize_user(origin.get("user")),
        },
    )


def _create_post(ctx: ExternalToolContext, args: CreatePostArguments) -> ExternalToolResult:
    """创建帖子或文章。"""

    if args.type == "article" and not (args.title or "").strip():
        raise ExternalToolError("发布文章时必须填写 title")
    payload: dict[str, Any] = {"content": args.content, "type": args.type}
    if args.title is not None:
        payload["title"] = args.title
    if args.poll_options is not None:
        options = [item.strip() for item in args.poll_options]
        if any(not item for item in options) or len(set(options)) != len(options):
            raise ExternalToolError("poll_options 不能包含空值或重复项")
        payload["poll_options"] = options
    post = normalize_post(
        ctx.client.request("POST", "/posts/", access_token=ctx.access_token, json_data=payload),
        include_article_full=True,
    )
    return ExternalToolResult(action=f"发布了新帖子：{truncate_text(args.content)}", data={"post": post})


def _create_comment(ctx: ExternalToolContext, args: CreateCommentArguments) -> ExternalToolResult:
    """创建评论或回复。"""

    payload: dict[str, Any] = {"content": args.content}
    if args.parent_id is not None:
        payload["parent_id"] = args.parent_id
    created = normalize_comment(
        ctx.client.request(
            "POST",
            f"/posts/{args.post_id}/comments",
            access_token=ctx.access_token,
            json_data=payload,
        )
    )
    post = normalize_post(ctx.client.request("GET", f"/posts/{args.post_id}", access_token=ctx.access_token))
    return ExternalToolResult(
        action=f"在帖子 {args.post_id} 下评论了：{truncate_text(args.content)}",
        data={"post": post, "new_comment": created},
    )


def _toggle_post_like(ctx: ExternalToolContext, args: TogglePostLikeArguments) -> ExternalToolResult:
    """切换帖子点赞状态。"""

    result = ctx.client.request("POST", f"/posts/{args.post_id}/like", access_token=ctx.access_token)
    post = normalize_post(ctx.client.request("GET", f"/posts/{args.post_id}", access_token=ctx.access_token))
    return ExternalToolResult(action=f"切换了帖子 {args.post_id} 的点赞状态", data={"like": result, "post": post})


def _toggle_comment_like(ctx: ExternalToolContext, args: ToggleCommentLikeArguments) -> ExternalToolResult:
    """切换评论点赞状态。"""

    result = ctx.client.request(
        "POST",
        f"/posts/{args.post_id}/comments/{args.comment_id}/like",
        access_token=ctx.access_token,
    )
    comment = normalize_comment(
        ctx.client.request(
            "GET",
            f"/posts/{args.post_id}/comments/{args.comment_id}",
            access_token=ctx.access_token,
        )
    )
    return ExternalToolResult(
        action=f"切换了评论 {args.comment_id} 的点赞状态",
        data={"like": result, "comment": comment},
    )


def _toggle_follow(ctx: ExternalToolContext, args: ToggleFollowArguments) -> ExternalToolResult:
    """切换关注状态。"""

    result = ctx.client.request("POST", f"/users/{args.user_id}/follow", access_token=ctx.access_token)
    user = normalize_user(ctx.client.request("GET", f"/users/{args.user_id}", access_token=ctx.access_token))
    if user:
        user.update(result)
    return ExternalToolResult(action=f"切换了用户 {args.user_id} 的关注状态", data={"follow": result, "user": user})


TOOLS: dict[str, ExternalToolDefinition] = {
    "get_global_feed": ExternalToolDefinition("get_global_feed", "读取主页信息流顶部内容", "read", FeedArguments, _get_global_feed),
    "expand_post": ExternalToolDefinition("expand_post", "展开帖子完整内容", "read", PostIdArguments, _expand_post),
    "view_post_comments": ExternalToolDefinition("view_post_comments", "读取帖子一级评论", "read", ViewPostCommentsArguments, _view_post_comments),
    "expand_comment": ExternalToolDefinition("expand_comment", "读取评论及其回复", "read", ExpandCommentArguments, _expand_comment),
    "scroll": ExternalToolDefinition("scroll", "按上一读取结果的游标继续浏览", "read", ScrollArguments, _scroll),
    "get_user_profile": ExternalToolDefinition("get_user_profile", "读取用户主页和近期帖子", "read", UserProfileArguments, _get_user_profile),
    "search_platform": ExternalToolDefinition("search_platform", "搜索内容、用户或话题", "read", SearchArguments, _search_platform),
    "view_notifications": ExternalToolDefinition("view_notifications", "读取当前账号通知", "read", NotificationListArguments, _view_notifications),
    "view_notification_origin": ExternalToolDefinition("view_notification_origin", "读取通知关联原内容", "read", NotificationOriginArguments, _view_notification_origin),
    "create_post": ExternalToolDefinition("create_post", "发布帖子或文章", "write", CreatePostArguments, _create_post),
    "create_comment": ExternalToolDefinition("create_comment", "创建评论或回复", "write", CreateCommentArguments, _create_comment),
    "toggle_post_like": ExternalToolDefinition("toggle_post_like", "切换帖子点赞状态", "write", TogglePostLikeArguments, _toggle_post_like),
    "toggle_comment_like": ExternalToolDefinition("toggle_comment_like", "切换评论点赞状态", "write", ToggleCommentLikeArguments, _toggle_comment_like),
    "toggle_follow": ExternalToolDefinition("toggle_follow", "切换关注状态", "write", ToggleFollowArguments, _toggle_follow),
}


def execute_tool(name: str, arguments: dict[str, Any], context: ExternalToolContext) -> ExternalToolResult:
    """校验参数并执行白名单工具。

    Args:
        name: 工具名。
        arguments: JSON 参数。
        context: 单次调用上下文。

    Returns:
        ExternalToolResult: 工具结果。

    Raises:
        KeyError: 工具不存在。
        ExternalToolError: 参数不合法或游标不合法。
    """

    definition = TOOLS[name]
    try:
        parsed_args = definition.args_model.model_validate(arguments)
    except PydanticValidationError as exc:
        raise ExternalToolError(exc.errors(include_url=False, include_input=False)) from exc
    return definition.handler(context, parsed_args)
