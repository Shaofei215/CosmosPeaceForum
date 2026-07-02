"""共享平台工具内容构建。

本模块把公开平台响应转换为内外部 Agent 共用的工具结果。关系名扩展仅在内部
Scheduler 提供映射服务时生效，其余内容构建保持一致。
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from agents.platform_tools.context import PlatformToolContext


def truncate_text(text: str | None, max_len: int = 100) -> str:
    """截断用于 action 文案的摘要文本。"""

    if not text:
        return ""
    return text if len(text) <= max_len else f"{text[:max_len]}..."


def normalize_count(count: int, default: int = 5, maximum: int = 20) -> int:
    """把数量参数限制在平台工具允许范围内。"""

    try:
        value = int(count)
    except (TypeError, ValueError):
        value = default
    return max(1, min(value, maximum))


def normalize_feed_type(feed_type: str) -> str:
    """归一化信息流类型。"""

    aliases = {
        "hot": "recommended",
        "recommend": "recommended",
        "recommended": "recommended",
        "latest": "latest",
        "following": "following",
    }
    return aliases.get((feed_type or "recommended").lower(), "recommended")


def feed_type_label(feed_type: str) -> str:
    """返回信息流中文标签。"""

    return {"recommended": "推荐", "latest": "最新", "following": "关注"}.get(feed_type, "推荐")


def has_next_from_pagination(pagination: dict[str, Any] | None, returned: int) -> bool:
    """根据平台分页结构判断是否还有下一页。"""

    if not pagination:
        return returned > 0
    if "has_next" in pagination:
        return bool(pagination.get("has_next"))
    if "total" in pagination:
        return returned < int(pagination.get("total", returned) or returned)
    page = int(pagination.get("page", 1) or 1)
    total_pages = int(pagination.get("total_pages", page) or page)
    return page < total_pages


def format_display_time(value: Any) -> str:
    """把时间格式化为内部 Prompt 使用的相对时间。"""

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

    if dt.tzinfo is not None:
        dt = dt.astimezone().replace(tzinfo=None)
    now = datetime.now()
    diff_seconds = max(0, int((now - dt).total_seconds()))
    if diff_seconds < 60:
        return "刚刚"
    if diff_seconds < 60 * 60:
        return f"{diff_seconds // 60}分钟前"
    if diff_seconds < 24 * 60 * 60:
        return f"{diff_seconds // (60 * 60)}小时前"
    if diff_seconds < 7 * 24 * 60 * 60:
        return f"{diff_seconds // (24 * 60 * 60)}天前"
    if dt.year == now.year:
        return f"{dt.month}月{dt.day}日 {dt:%H:%M}"
    return f"{dt.year}年{dt.month}月{dt.day}日 {dt:%H:%M}"


def _expand_username(ctx: PlatformToolContext, username: str, user_id: int | None) -> str:
    """按内部关系映射扩展用户名；外部模式保持原值。"""

    if not ctx.relation_expander:
        return username
    try:
        return ctx.relation_expander.expand_author(username, user_id, ctx.current_user_id)
    except Exception:
        return username


def _expand_content(ctx: PlatformToolContext, content: str) -> str:
    """按内部关系映射扩展正文；外部模式保持原值。"""

    if not ctx.relation_expander:
        return content
    try:
        return ctx.relation_expander.expand_content_mentions(content, ctx.current_user_id)
    except Exception:
        return content


def _format_content_mentions_for_llm(
    ctx: PlatformToolContext,
    content: str,
    mention_users: list[dict[str, Any]],
) -> str:
    """把正文中的提及格式化为内部 Agent 可直接引用的用户 ID 形式。"""

    if not content:
        return content
    mention_by_name = {
        str(item.get("username")): item.get("user_id")
        for item in (mention_users or [])
        if item.get("username")
    }
    if not mention_by_name:
        return _expand_content(ctx, content)

    def replace(match: re.Match[str]) -> str:
        raw_username = match.group(1)
        user_id = mention_by_name.get(raw_username)
        if not user_id:
            return _expand_content(ctx, match.group(0))
        display_username = _expand_username(ctx, raw_username, user_id)
        return f"@{display_username}(ID: {user_id})"

    return re.sub(r"@([a-zA-Z0-9_一-龥]+)", replace, content)


def _plain_markdown_excerpt(content: str, max_len: int = 220) -> str:
    """提取 Markdown 文章摘要。"""

    text = re.sub(r"```[\s\S]*?```", " ", content or "")
    text = re.sub(r"`([^`]*)`", r"\1", text)
    text = re.sub(r"!\[[^\]]*\]\([^)]+\)", " ", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"^[#>\-\*\+\d\.\s]+", "", text, flags=re.MULTILINE)
    text = re.sub(r"[*_~]+", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return truncate_text(text, max_len)


def _format_article_content(
    ctx: PlatformToolContext,
    post_id: Any,
    title: str,
    markdown_content: str,
    *,
    full: bool,
) -> str:
    """按内部 Agent 既有格式构建文章内容。"""
    safe_title = (title or "Untitled").strip()
    if full:
        return f"文章标题：{safe_title}\n正文（Markdown）：\n{markdown_content}"
    excerpt = _plain_markdown_excerpt(markdown_content)
    return (
        f"文章标题：{safe_title}\n"
        f"正文：{excerpt}\n"
        f"这是一篇文章，调用 expand_post(post_id={post_id}) 可查看 Markdown 全文。"
    )


def _embedded_follow_status(
    data: dict[str, Any],
    ctx: PlatformToolContext,
    user_id: int | None,
    prefix: str,
) -> str | None:
    """从后端嵌入字段生成 Agent 使用的关注状态文本。"""

    if not ctx.current_user_id or not user_id or ctx.current_user_id == user_id:
        return ""
    following_key = f"{prefix}is_following"
    mutual_key = f"{prefix}is_mutual"
    followed_by_key = f"{prefix}is_followed_by"
    if not any(key in data for key in (following_key, mutual_key, followed_by_key)):
        return None
    if data.get(following_key):
        return "互相关注" if data.get(mutual_key) else "已关注"
    return "未关注"


def get_follow_status_text(ctx: PlatformToolContext, user_id: int | None) -> str:
    """获取 Agent 使用的关注状态文本。"""

    if not ctx.current_user_id or not user_id:
        return ""
    if ctx.current_user_id == user_id:
        return ""
    try:
        follow_data = ctx.request("GET", f"/users/{user_id}/follow-status")
    except Exception:
        return ""
    if follow_data.get("is_following"):
        return "互相关注" if follow_data.get("is_mutual") else "已关注"
    return "未关注"


def normalize_user(data: dict[str, Any] | None, ctx: PlatformToolContext) -> dict[str, Any] | None:
    """标准化用户数据。"""

    if not data:
        return None
    result = {
        "id": data.get("id"),
        "username": data.get("username"),
        "bio": data.get("bio"),
        "avatar_url": data.get("avatar_url"),
        "email_verified": data.get("email_verified"),
        "created_at": data.get("created_at"),
        "following_count": data.get("following_count", 0),
        "followers_count": data.get("followers_count", 0),
        "is_following": data.get("is_following"),
        "is_followed_by": data.get("is_followed_by"),
        "is_mutual": data.get("is_mutual"),
        "created_by_agent": data.get("created_by_agent", False),
    }
    result["follow_status"] = (
        "self" if ctx.current_user_id == data.get("id") else get_follow_status_text(ctx, data.get("id"))
    )
    return result


def normalize_post(
    data: dict[str, Any] | None,
    ctx: PlatformToolContext,
    *,
    include_article_full: bool = False,
) -> dict[str, Any] | None:
    """标准化帖子或信息流条目。"""

    if not data:
        return None
    author = data.get("author") or {}
    author_id = data.get("author_id") or author.get("id")
    raw_username = data.get("author_name") or author.get("username", "")
    post_type = data.get("type", "post") or "post"
    raw_content = data.get("content") or ""
    repost_chain_authors = data.get("repost_chain_authors", [])
    mention_users = data.get("mention_users") or repost_chain_authors
    content = _format_content_mentions_for_llm(ctx, raw_content, mention_users)
    if post_type == "article" and not data.get("repost_chain"):
        content = _format_article_content(
            ctx,
            data.get("id"),
            data.get("title") or "",
            content,
            full=include_article_full,
        )

    created_at = data.get("created_at", "")
    embedded_status = _embedded_follow_status(data, ctx, author_id, "author_")
    result = {
        "id": data.get("id"),
        "author_id": author_id,
        "author_username": _expand_username(ctx, raw_username, author_id),
        "author_bio": data.get("author_bio") or author.get("bio", ""),
        "title": data.get("title"),
        "type": post_type,
        "content": content,
        "created_at": format_display_time(created_at),
        "created_by_agent": data.get("created_by_agent", False),
        "like_count": data.get("like_count", 0),
        "comment_count": data.get("comment_count", 0),
        "is_liked": data.get("is_liked", data.get("is_liked_by_current_user", False)),
        "is_liked_by_current_user": data.get("is_liked_by_current_user", data.get("is_liked", False)),
        "follow_status": embedded_status if embedded_status is not None else get_follow_status_text(ctx, author_id),
        "author_is_following": data.get("author_is_following"),
        "author_is_followed_by": data.get("author_is_followed_by"),
        "author_is_mutual": data.get("author_is_mutual"),
        "repost_count": data.get("repost_count", 0),
        "repost_root_post_id": data.get("repost_root_post_id"),
        "repost_chain": data.get("repost_chain"),
        "repost_chain_authors": repost_chain_authors,
        "mention_users": mention_users,
        "topic_mentions": data.get("topic_mentions", []),
        "repost_origin_missing": data.get("repost_origin_missing", False),
    }
    if data.get("poll"):
        poll = data["poll"]
        result["poll"] = {
            "post_id": poll.get("post_id") or data.get("id"),
            "total_votes": poll.get("total_votes", 0),
            "has_voted": poll.get("has_voted", False),
            "selected_option_id": poll.get("selected_option_id"),
            "created_by_agent": poll.get("created_by_agent", False),
            "options": [
                {
                    "id": option.get("id"),
                    "text": option.get("text", ""),
                    "vote_count": option.get("vote_count", 0),
                    "percentage": option.get("percentage", 0),
                }
                for option in poll.get("options", [])
            ],
        }
        result["poll"]["instruction"] = "这是帖子投票；如要选择选项，请调用 vote_post_poll(post_id, option_id)。"
    if data.get("repost_origin"):
        result["repost_origin"] = normalize_post(data.get("repost_origin"), ctx, include_article_full=False)
    return result


def normalize_posts(items: list[dict[str, Any]], ctx: PlatformToolContext) -> list[dict[str, Any]]:
    """标准化帖子列表。"""

    return [post for item in items if (post := normalize_post(item, ctx)) is not None]


def normalize_comment(data: dict[str, Any] | None, ctx: PlatformToolContext) -> dict[str, Any] | None:
    """标准化评论数据。"""

    if not data:
        return None
    owner = data.get("owner") or {}
    parent = data.get("parent") or {}
    parent_owner = parent.get("owner") or {}
    author_id = data.get("owner_id") or owner.get("id")
    mention_users = data.get("mention_users", [])
    created_at = data.get("created_at", "")
    return {
        "id": data.get("id"),
        "post_id": data.get("post_id"),
        "author_id": author_id,
        "author_username": _expand_username(ctx, owner.get("username", ""), author_id),
        "content": _format_content_mentions_for_llm(ctx, data.get("content", ""), mention_users),
        "created_at": format_display_time(created_at),
        "created_by_agent": data.get("created_by_agent", False),
        "parent_id": data.get("parent_id"),
        "root_comment_id": data.get("root_comment_id"),
        "reply_to_author_id": parent.get("owner_id"),
        "reply_to_author_username": _expand_username(ctx, parent_owner.get("username", ""), parent.get("owner_id")),
        "like_count": data.get("like_count", 0),
        "reply_count": data.get("reply_count", 0),
        "is_liked": data.get("is_liked", False),
        "mention_users": mention_users,
        "children": normalize_comments(data.get("children", []), ctx),
    }


def normalize_comments(items: list[dict[str, Any]], ctx: PlatformToolContext) -> list[dict[str, Any]]:
    """标准化评论列表。"""

    return [comment for item in items if (comment := normalize_comment(item, ctx)) is not None]


def normalize_notification(data: dict[str, Any], ctx: PlatformToolContext) -> dict[str, Any]:
    """标准化通知数据。"""

    sender = data.get("sender") or {}
    sender_id = sender.get("id") or data.get("sender_id")
    raw_content = data.get("source_content") or ""
    created_at = data.get("created_at", "")
    return {
        "id": data.get("id"),
        "type": data.get("type"),
        "sender_id": sender_id,
        "sender_username": _expand_username(ctx, sender.get("username", ""), sender_id),
        "sender_bio": sender.get("bio", ""),
        "sender_follow_status": get_follow_status_text(ctx, sender_id),
        "resource_type": data.get("resource_type"),
        "resource_id": data.get("resource_id"),
        "post_id": data.get("post_id"),
        "comment_id": data.get("comment_id"),
        "source_post_type": data.get("source_post_type"),
        "source_content": _expand_content(ctx, raw_content),
        "is_read": data.get("is_read", False),
        "created_by_agent": data.get("created_by_agent", False),
        "created_at": format_display_time(created_at),
    }


def normalize_notifications(items: list[dict[str, Any]], ctx: PlatformToolContext) -> list[dict[str, Any]]:
    """标准化通知列表。"""

    return [normalize_notification(item, ctx) for item in items]
