"""外部工具响应 presenter。

本模块把公开平台返回的裸对象、分页包装和领域对象压缩成外部 Agent 可直接消费的
稳定字典，同时保留真实资源 ID、原文、精确时间、来源标记和当前用户关系状态。
"""

from __future__ import annotations

from typing import Any


def truncate_text(text: str | None, max_len: int = 120) -> str:
    """截断用于 action 的摘要文本。"""

    if not text:
        return ""
    return text if len(text) <= max_len else f"{text[:max_len]}..."


def has_next_from_pagination(pagination: dict[str, Any] | None, returned: int) -> bool:
    """从平台分页结构判断是否还有更多数据。"""

    if not pagination:
        return returned > 0
    if "has_next" in pagination:
        return bool(pagination.get("has_next"))
    page = int(pagination.get("page", 1) or 1)
    total_pages = int(pagination.get("total_pages", page) or page)
    return page < total_pages


def normalize_user(data: dict[str, Any] | None) -> dict[str, Any] | None:
    """标准化用户数据。"""

    if not data:
        return None
    return {
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


def normalize_post(data: dict[str, Any] | None, include_article_full: bool = True) -> dict[str, Any] | None:
    """标准化帖子或信息流条目。"""

    if not data:
        return None
    author = data.get("author") or {}
    author_id = data.get("author_id") or author.get("id")
    author_name = data.get("author_name") or author.get("username")
    content = data.get("content") or ""
    if data.get("type") == "article" and not include_article_full:
        content = truncate_text(content, 300)
    return {
        "id": data.get("id"),
        "author_id": author_id,
        "author_username": author_name,
        "author": normalize_user(author) if author else None,
        "title": data.get("title"),
        "type": data.get("type", "post") or "post",
        "content": content,
        "created_at": data.get("created_at"),
        "created_by_agent": data.get("created_by_agent", False),
        "like_count": data.get("like_count", 0),
        "comment_count": data.get("comment_count", 0),
        "is_liked": data.get("is_liked", data.get("is_liked_by_current_user", False)),
        "is_liked_by_current_user": data.get(
            "is_liked_by_current_user",
            data.get("is_liked", False),
        ),
        "author_is_following": data.get("author_is_following"),
        "author_is_followed_by": data.get("author_is_followed_by"),
        "author_is_mutual": data.get("author_is_mutual"),
        "repost_count": data.get("repost_count", 0),
        "repost_root_post_id": data.get("repost_root_post_id"),
        "repost_chain": data.get("repost_chain"),
        "repost_chain_authors": data.get("repost_chain_authors", []),
        "mention_users": data.get("mention_users", []),
        "topic_mentions": data.get("topic_mentions", []),
        "repost_origin_missing": data.get("repost_origin_missing", False),
        "repost_origin": normalize_post(data.get("repost_origin"), include_article_full=False)
        if data.get("repost_origin")
        else None,
        "poll": data.get("poll"),
    }


def normalize_posts(items: list[dict[str, Any]], include_article_full: bool = False) -> list[dict[str, Any]]:
    """标准化帖子列表。"""

    return [
        post
        for item in items
        if (post := normalize_post(item, include_article_full=include_article_full)) is not None
    ]


def normalize_comment(data: dict[str, Any] | None) -> dict[str, Any] | None:
    """标准化评论数据。"""

    if not data:
        return None
    owner = data.get("owner") or {}
    parent = data.get("parent") or {}
    parent_owner = parent.get("owner") or {}
    return {
        "id": data.get("id"),
        "post_id": data.get("post_id"),
        "author_id": data.get("owner_id") or owner.get("id"),
        "author_username": owner.get("username"),
        "author": normalize_user(owner) if owner else None,
        "content": data.get("content", ""),
        "created_at": data.get("created_at"),
        "created_by_agent": data.get("created_by_agent", False),
        "parent_id": data.get("parent_id"),
        "root_comment_id": data.get("root_comment_id"),
        "reply_to_author_id": parent.get("owner_id"),
        "reply_to_author_username": parent_owner.get("username"),
        "like_count": data.get("like_count", 0),
        "reply_count": data.get("reply_count", 0),
        "is_liked": data.get("is_liked", False),
        "mention_users": data.get("mention_users", []),
        "children": normalize_comments(data.get("children", [])),
    }


def normalize_comments(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """标准化评论列表。"""

    return [comment for item in items if (comment := normalize_comment(item)) is not None]


def normalize_notification(data: dict[str, Any]) -> dict[str, Any]:
    """标准化通知数据。"""

    sender = data.get("sender") or {}
    return {
        "id": data.get("id"),
        "type": data.get("type"),
        "sender_id": data.get("sender_id") or sender.get("id"),
        "sender_username": sender.get("username"),
        "sender": normalize_user(sender) if sender else None,
        "resource_type": data.get("resource_type"),
        "resource_id": data.get("resource_id"),
        "post_id": data.get("post_id"),
        "comment_id": data.get("comment_id"),
        "source_post_type": data.get("source_post_type"),
        "source_content": data.get("source_content"),
        "is_read": data.get("is_read", False),
        "created_by_agent": data.get("created_by_agent", False),
        "created_at": data.get("created_at"),
    }
