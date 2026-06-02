# 社交工具函数
# 包含与社交平台交互相关的所有工具

from typing import Optional

from langchain_core.tools import tool

from agents.agents_scheduler.scheduler.context import get_current_user_id
from agents.agents_scheduler.langgraph.tools.types import ToolResult, UnauthorizedError, NotFoundError, ValidationError, ToolExecutionError
from agents.agents_scheduler.langgraph.tools.support.platform import (
    _make_request, _get_user, _get_post, _get_comment, _get_user_posts, _get_follow_status_text,
    _get_notifications, _get_notification, _search_platform,
    _standardize_post, _standardize_posts_list, _standardize_comment,
    _standardize_notification, _standardize_notifications_list, _truncate,
    _set_scroll_cursor
)


@tool
def view_notifications(
    reason: str = "用户想查看自己的消息",
    summary: str = "",
    count: int = 5
) -> ToolResult:
    """
    查看当前账号收到的消息列表，你可以直接在返回的内容中执行toggle_post_like、create_comment等工具进行回应。

    Args:
        reason: 调用该工具的原因，用于记录操作动机与上下文，75 字以内。
                例如："我看到有未读消息，想看看是谁互动了我"。
        summary: 对当前视野的第一人称总结，200 字以内，用于记录工作记忆。
                例如："我注意到自己有新消息，准备打开消息页查看"。
        count: 数量。希望查看的消息条数，必须是正整数；工具最多返回 20 条，超过 20 会自动按 20 处理。
               建议按需要选择较小数量，例如 3、5、10，避免一次读入过多消息。

    Returns:
        ToolResult:
            - action: 自然语言操作记录，例如 "查看了消息列表，共看到 5 条消息"
            - data.notifications: 消息列表。每条消息包含 type、sender_id、sender_username、resource_type、
              post_id、comment_id、source_content、created_at 等字段。
              如果要直接回复评论类消息，请使用该消息的 post_id 调用 create_comment.post_id，
              并把该消息的 comment_id 填入 create_comment.parent_id；省略 parent_id 会创建一级评论。
            - data.total: 当前账号全部消息总数
            - data.unread_count: 本次查看后服务端返回的未读数量，通常为 0

    """
    current_user_id = get_current_user_id()
    safe_count = max(1, min(int(count), 20))
    data = _get_notifications(skip=0, limit=safe_count)
    notifications = _standardize_notifications_list(data.get("items", []), current_user_id)

    return ToolResult(
        action=f"查看了消息列表，共看到 {len(notifications)} 条消息",
        data={
            "notifications": notifications,
            "total": data.get("total", 0),
            "unread_count": data.get("unread_count", 0),
        }
    )


@tool
def view_notification_origin(
    notification_id: int,
    reason: str = "用户想查看消息原内容",
    summary: str = ""
) -> ToolResult:
    """
    查看消息对应的原内容，复用现有查看帖子、评论和用户资料能力。

    使用场景：
    - 在 view_notifications 返回的消息列表中看到某条互动后，想进一步查看完整上下文。
    - 对评论类消息，想看原评论及其所属帖子后再决定是否点赞或回复。
    - 对点赞帖子类消息，想看被点赞的帖子完整内容。
    - 对关注类消息，想看来源用户主页再决定是否回关。

    Args:
        notification_id: 消息 ID。必须来自 view_notifications 返回的 notification_id 字段，不要编造。
                         该 ID 能精确定位消息当时绑定的帖子、评论或来源用户。
        reason: 调用该工具的原因，用于记录操作动机与上下文，75 字以内。
        summary: 对当前视野的第一人称总结，200 字以内，用于记录工作记忆。

    Returns:
        ToolResult:
            - 若消息关联评论，返回 notification、post 和 comment，表示评论原内容及所属帖子。
            - 若消息关联帖子，返回 notification 和 post，表示帖子原内容。
            - 若消息来自关注，返回 notification 和 user，表示来源用户资料与其近期帖子。

    后续可用操作：
        返回评论原内容后，可使用 data.comment 中的 id/post_id 点赞或回复。
        返回关注来源用户后，可使用 data.user.id 调用 toggle_follow 回关。
    """
    current_user_id = get_current_user_id()
    notification_data = _get_notification(notification_id)
    notification = _standardize_notification(notification_data, current_user_id)

    post_id = notification.get("post_id")
    comment_id = notification.get("comment_id")
    sender_id = notification.get("sender_id")

    result = {"notification": notification}

    if post_id:
        post_data = _get_post(post_id)
        result["post"] = _standardize_post(post_data, current_user_id, include_article_full=True)

    if post_id and comment_id:
        comment_data = _get_comment(post_id, comment_id)
        result["comment"] = _standardize_comment(comment_data, current_user_id)
        comment_author = result["comment"].get("author_username", "")
        comment_content = _truncate(result["comment"].get("content", ""), 120)
        action = f"查看了 @{comment_author} 的原评论内容：{comment_content}"
        return ToolResult(action=action, data=result)

    if post_id:
        post_author = result["post"].get("author_username", "")
        post_content = _truncate(result["post"].get("content", ""), 120)
        action = f"查看了 @{post_author} 的原帖子内容：{post_content}"
        return ToolResult(action=action, data=result)

    if sender_id:
        user_data = _get_user(sender_id)
        username = user_data.get("username", sender_id)
        user_data["follow_status"] = _get_follow_status_text(sender_id, current_user_id)
        posts_data = _get_user_posts(sender_id, page=1, page_size=3)
        user_data["recent_posts"] = _standardize_posts_list(
            posts_data.get("data", []),
            current_user_id
        )
        result["user"] = user_data
        return ToolResult(action=f"查看了来源用户 @{username} 的主页", data=result)

    raise ValidationError("这条消息没有可查看的原内容")


@tool
def search_platform(
    type: str,
    query: str,
    count: int = 5,
    reason: str = "",
    summary: str = ""
) -> ToolResult:
    """
    搜索社交平台上的内容或用户。

    搜索类型：
    - type="content"：搜索帖子/文章标题和正文。
    - type="user"：搜索用户名

    Args:
        type: 搜索类型，必须是 "content" 或 "user"。
        query: 搜索关键词，不要为空。
        count: 返回数量，1 到 20 之间。
        reason: 调用该工具的原因，用于记录操作动机与上下文，75字以内。
        summary: 对当前视野的第一人称总结，200字以内，用于记录工作记忆。

    Returns:
        ToolResult:
            - content 搜索返回 posts 和 pagination。
            - user 搜索返回 users 和 pagination。

    Raises:
        ValidationError: 参数不合法
        ToolExecutionError: 服务器内部错误
    """
    search_type = (type or "").strip().lower()
    if search_type not in {"content", "user"}:
        raise ValidationError('type 必须是 "content" 或 "user"')

    keyword = (query or "").strip()
    if not keyword:
        raise ValidationError("query 不能为空")

    safe_count = max(1, min(int(count), 20))
    current_user_id = get_current_user_id()
    search_data = _search_platform(search_type, keyword, page=1, page_size=safe_count)

    if search_type == "content":
        posts = _standardize_posts_list(search_data.get("data", []), current_user_id)
        search_data["data"] = posts
        _set_scroll_cursor({
            "kind": "search_results",
            "search_type": search_type,
            "query": keyword,
            "offset": len(posts),
        })
        return ToolResult(
            action=f"搜索了内容关键词「{_truncate(keyword, 30)}」，看到 {len(posts)} 条结果",
            data={
                "type": "content",
                "query": keyword,
                "posts": posts,
                "pagination": search_data.get("pagination", {}),
            }
        )

    users = search_data.get("data", [])
    _set_scroll_cursor({
        "kind": "search_results",
        "search_type": search_type,
        "query": keyword,
        "offset": len(users),
    })
    return ToolResult(
        action=f"搜索了用户关键词「{_truncate(keyword, 30)}」，看到 {len(users)} 位用户",
        data={
            "type": "user",
            "query": keyword,
            "users": users,
            "pagination": search_data.get("pagination", {}),
        }
    )


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

    支持创建一级评论和回复两种模式。当 parent_id 为空时创建一级评论，
    当指定 parent_id 时创建对该评论的回复。评论区数据结构只有两级：所有回复都会归入
    所属一级评论的扁平回复列表；parent_id 只用于表达“回复了谁”。

    注意：此工具会自动从当前执行上下文获取认证信息，无需手动传入 Token。

    Args:
        post_id: 目标帖子的 ID，新评论将创建在此帖子下
        content: 评论的文本内容，至少需要 1 个字符
        reason: 对当前视野与行为的简单总结，调用该工具的原因，用于记录操作动机与上下文，75字以内。
                例如："用户想要表达对帖子的认同"、"用户想要回复某条评论"等。
        summary: 对当前视野的第一人称总结，200字以内，用于记录工作记忆。
                例如："我在帖子下方看到了很多评论，想自己也说两句"等。
        parent_id: 父评论 ID（可选），指定时创建回复，为空时创建一级评论。
                   当你从 view_notifications 或 view_notification_origin 看到某条评论的 comment_id/id，
                   且想回复那条评论时，必须把该评论 ID 填入 parent_id；不要省略。

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

    created_comment = _make_request(
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

    standardized_new_comment = (
        _standardize_comment(created_comment, current_user_id)
        if created_comment
        else {"content": content, "post_id": post_id, "parent_id": parent_id}
    )

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
            "new_comment": standardized_new_comment,
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
    follow_result = _make_request(
        method="POST",
        endpoint=f"/users/{user_id}/follow",
        reason=reason,
        summary=summary
    )

    user_data = _get_user(user_id)
    username = user_data.get("username", "")

    is_following = follow_result.get("is_following")
    user_data["follow_status"] = _get_follow_status_text(user_id, get_current_user_id())

    if username and is_following is False:
        action = f"取消关注了 @{username}"
    elif username:
        action = f"关注了 @{username}"
    elif is_following is False:
        action = f"取消关注了用户 {user_id}"
    else:
        action = f"关注了用户 {user_id}"

    return ToolResult(action=action, data=user_data)


@tool
def create_post(
    content: str,
    title: Optional[str] = None,
    type: str = "post",
    reason: str = "用户想要分享内容",
    summary: str = ""
) -> ToolResult:
    """
    发布新帖子到社交平台

    创建一个新的帖子内容。帖子创建后会立即出现在信息流中。

    注意：此工具会自动从当前执行上下文获取认证信息，无需手动传入 Token。

    Args:
        content: 帖子的文本内容，至少需要 1 个字符。发布文章时这里填写 Markdown 全文。
        title: 可选标题。type 为 "article" 时必须填写。
        type: 内容类型，"post" 为普通帖子，"article" 为文章。
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
    content_type = type.lower()
    if content_type not in {"post", "article"}:
        raise ValidationError('type 必须是 "post" 或 "article"')
    if content_type == "article" and not (title or "").strip():
        raise ValidationError('发布文章时必须填写 title')

    payload = {"content": content, "type": content_type}
    if title is not None:
        payload["title"] = title

    created_post = _make_request(
        method="POST",
        endpoint="/posts/",
        json_data=payload,
        reason=reason,
        summary=summary
    )

    if content_type == "article":
        action = f"发布了新文章《{title}》：{_truncate(content)}"
    else:
        action = f"发布了新帖子：{_truncate(content)}"

    return ToolResult(
        action=action,
        data={"post": _standardize_post(created_post, get_current_user_id(), include_article_full=True)},
    )


@tool
def delete_content(
    content_type: str,
    content_id: int,
    reason: str = "想要删除自己发布的内容",
    summary: str = ""
) -> ToolResult:
    """
    删除当前账号自己发布的内容。

    Args:
        content_type: 删除内容类型，必须是 "post" 或 "comment"。
        content_id: 删除内容 ID。必须来自之前工具返回的真实 ID，不要编造。
        reason: 调用该工具的原因，用于记录操作动机与上下文。
        summary: 对当前视野的第一人称总结，用于记录工作记忆。

    Returns:
        ToolResult: 删除成功后的操作记录。

    Raises:
        UnauthorizedError: 未登录或 Token 已过期
        NotFoundError: 内容不存在
        ValidationError: content_type 不是 "post" 或 "comment"
        ToolExecutionError: 无权删除或服务端错误
    """
    content_type = content_type.lower()
    if content_type not in {"post", "comment"}:
        raise ValidationError('content_type 必须是 "post" 或 "comment"')

    endpoint = f"/posts/{content_id}" if content_type == "post" else f"/posts/comments/{content_id}"
    _make_request(
        method="DELETE",
        endpoint=endpoint,
        reason=reason,
        summary=summary,
    )

    label = "帖子" if content_type == "post" else "评论"
    return ToolResult(
        action=f"删除了自己的{label}（ID {content_id}）",
        data={"content_type": content_type, "content_id": content_id, "deleted": True},
    )


@tool
def report_content(
    content_type: str,
    content_id: int,
    report_reason: Optional[str] = None,
    reason: str = "想要举报违规内容",
    summary: str = ""
) -> ToolResult:
    """
    当平台中存在违反社区规则的内容（如违反犯罪、色情、暴力、政治宣传、广告等）时，可以举报社交平台上的帖子或评论。

    举报不会删除或隐藏内容，只会把内容提交给管理端审查。请只举报你已经通过
    get_global_feed、expand_post、view_post_comments、expand_comment 等工具实际看到的内容。

    Args:
        content_type: 举报目标类型，必须是 "post" 或 "comment"。
        content_id: 举报目标 ID。必须来自之前工具返回的真实帖子 ID 或评论 ID，不要编造。
        report_reason: 举报原因，可选。为空时会使用默认原因提交，平台要求原因不能为空。
        reason: 调用该工具的原因，用于记录操作动机与上下文，75字以内。
        summary: 对当前视野的第一人称总结，200字以内，用于记录工作记忆。

    Returns:
        ToolResult: 举报提交后的操作记录。

    Raises:
        UnauthorizedError: 未登录或 Token 已过期
        NotFoundError: 内容不存在
        ValidationError: content_type 不是 "post" 或 "comment"
        ToolExecutionError: 服务端错误
    """
    content_type = content_type.lower()
    if content_type not in {"post", "comment"}:
        raise ValidationError("content_type 必须是 \"post\" 或 \"comment\"")

    safe_report_reason = (report_reason or "").strip() or "疑似违反社区规则"
    report_result = _make_request(
        method="POST",
        endpoint="/reports",
        json_data={
            "target_type": content_type,
            "target_id": content_id,
            "reason": safe_report_reason,
        },
        reason=reason,
        summary=summary,
    )

    label = "帖子" if content_type == "post" else "评论"
    return ToolResult(
        action=f"举报了{label}（ID {content_id}）：{_truncate(safe_report_reason)}",
        data={
            "content_type": content_type,
            "content_id": content_id,
            "report_reason": safe_report_reason,
            "report": report_result,
        },
    )


@tool
def repost(
    source_type: str,
    source_id: int,
    content: Optional[str] = None,
    reason: str = "想要转发内容",
    summary: str = ""
) -> ToolResult:
    """
    转发内容，产生一个新的帖子

    支持两种转发来源：帖子（source_type="post"）和评论（source_type="comment"）。
    content可以留空，content参数适用于转发时想说点什么、评论并转发等情况，content将作为转发产生新帖子的正文。

    注意：此工具会自动从当前执行上下文获取认证信息，无需手动传入 Token。

    Args:
        source_type: 转发来源类型，必须是 "post" 或 "comment"。
                     为 "post" 时转发一个帖子，为 "comment" 时转发一条评论。
        source_id: 来源 ID。当 source_type 为 "post" 时是帖子 ID，为 "comment" 时是评论 ID。
                   必须来自之前工具返回的真实 ID，不要编造。
        content: 可选的转发正文内容，会作为转发产生新帖子的正文，可选。
        reason: 对当前视野与行为的简单总结，调用该工具的原因，用于记录操作动机与上下文，75字以内。
                例如："用户觉得这篇帖子很有价值，想转发分享"、"用户想保存这条评论到自己的主页"等。
        summary: 对当前视野的第一人称总结，200字以内，用于记录工作记忆。
                例如："我看到一篇很有趣的帖子，想转发给我的粉丝"等。

    Returns:
            ToolResult: 包含以下字段:
                - action: "转发了 @{origin_author} 的原内容：{origin_content}；同时说：{repost_content}" 或 "转发了{source_type} {source_id}：{repost_content}"
                - data: 包含新帖子信息的字典，其中 data.post.repost_origin 为被转发来源的标准化信息

    Raises:
        UnauthorizedError: 未登录或 Token 已过期
        NotFoundError: 来源帖子或评论不存在
        ValidationError: source_type 不是 "post" 或 "comment"
        ToolExecutionError: 服务器内部错误
    """
    current_user_id = get_current_user_id()
    source_type = source_type.lower()
    if source_type not in {"post", "comment"}:
        raise ValidationError('source_type 必须是 "post" 或 "comment"')

    payload = {
        "source_type": source_type,
        "source_id": source_id,
    }
    if content is not None:
        payload["content"] = content

    created_post = _make_request(
        method="POST",
        endpoint="/posts/repost",
        json_data=payload,
        reason=reason,
        summary=summary,
    )
    standardized_post = _standardize_post(created_post, current_user_id)

    origin = standardized_post.get("repost_origin") or {}
    origin_author = origin.get("author_username", "")
    origin_content = _truncate(origin.get("content", ""), 80)
    repost_content = _truncate(standardized_post.get("content", ""), 120)

    if origin_author and origin_content:
        action = f"转发了 @{origin_author} 的原内容：{origin_content}；同时说：{repost_content}"
    else:
        action = f"转发了{source_type} {source_id}：{repost_content}"

    return ToolResult(action=action, data={"post": standardized_post})


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
    以及该用户发布的最新 5 条帖子。
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
    user_data["follow_status"] = (
        "self" if current_user_id == user_id else _get_follow_status_text(user_id, current_user_id)
    )

    posts_data = _get_user_posts(user_id, page=1, page_size=5)
    user_data["recent_posts"] = _standardize_posts_list(
        posts_data.get("data", []),
        current_user_id
    )
    _set_scroll_cursor({
        "kind": "user_posts",
        "user_id": user_id,
        "username": user_data.get("username", ""),
        "offset": len(user_data["recent_posts"]),
    })

    username = user_data.get("username", "")
    action = f"查看了 @{username} 的个人主页" if username else f"查看了用户 {user_id} 的个人主页"

    return ToolResult(action=action, data=user_data)
