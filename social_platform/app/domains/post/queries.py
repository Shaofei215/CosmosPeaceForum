"""帖子领域读侧查询和响应组装辅助。

本模块承接帖子响应中与转发链、转发源缺失状态和正文提及用户有关的读侧投影。
写侧事务编排保留在 ``application.py``，避免查询辅助发布领域事件或提交事务。
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from social_platform.app.domains.post.models import Post
from social_platform.app.domains.mention import application as mention_service
from social_platform.app.domains.topic import queries as topic_queries


MentionUserData = dict[str, object]


def attach_repost_metadata(db: Session, post: Post) -> Post:
    """为帖子 ORM 对象挂载转发响应元数据。

    Args:
        db: 当前数据库会话。
        post: 待补充响应字段的帖子对象。

    Returns:
        Post: 原帖子对象，已挂载 ``repost_origin``、``repost_origin_missing``、
        ``repost_chain_authors`` 和 ``mention_users`` 临时字段。

    Raises:
        数据库查询异常会透传给调用方。
    """

    post.repost_origin = post.repost_root_post if post.repost_root_post_id else None
    post.repost_origin_missing = is_repost_origin_missing(post)
    post.repost_chain_authors = build_repost_chain_authors(db, post.content)
    post.mention_users = build_mention_users(db, post.content)
    post.topic_mentions = topic_queries.build_topic_mentions(db, post.id)
    return post


def attach_repost_origin(post: Post) -> Post:
    """为帖子 ORM 对象挂载转发源对象和缺失状态。

    Args:
        post: 待补充响应字段的帖子对象。

    Returns:
        Post: 原帖子对象，已挂载 ``repost_origin`` 和 ``repost_origin_missing``。
    """

    post.repost_origin = post.repost_root_post if post.repost_root_post_id else None
    post.repost_origin_missing = is_repost_origin_missing(post)
    return post


def is_repost_origin_missing(post: Post) -> bool:
    """判断转发帖的根帖是否已缺失。

    Args:
        post: 待判断的帖子对象。

    Returns:
        bool: 普通帖子返回 ``False``；转发帖缺少根帖关联时返回 ``True``。
    """

    if not post.repost_source_type:
        return False
    if post.repost_root_post_id is None:
        return True
    return post.repost_root_post is None or post.repost_root_post.moderation_status != "active"


def build_repost_chain_authors(db: Session, content: str) -> list[MentionUserData]:
    """构建转发链作者列表。

    Args:
        db: 当前数据库会话。
        content: 转发链正文。

    Returns:
        list[MentionUserData]: 转发链中可跳转用户的元数据列表。

    Raises:
        数据库查询异常会透传给调用方。
    """

    return build_mention_users(db, content)


def build_repost_chain_authors_for_contents(
    db: Session,
    contents: list[str],
) -> list[list[MentionUserData]]:
    """批量构建转发链作者列表。

    Args:
        db: 当前数据库会话。
        contents: 多段转发链正文。

    Returns:
        list[list[MentionUserData]]: 与 ``contents`` 一一对应的作者元数据列表。

    Raises:
        数据库查询异常会透传给调用方。
    """

    return build_mention_users_for_contents(db, contents)


def build_mention_users(db: Session, content: str) -> list[MentionUserData]:
    """构建正文提及用户列表，供帖子、转发链和通知 origin 响应复用。

    Args:
        db: 当前数据库会话。
        content: 帖子、文章、评论或转发链正文。

    Returns:
        list[MentionUserData]: 已存在用户的提及元数据列表。

    Raises:
        数据库查询异常会透传给调用方。
    """

    return _normalize_mention_users(mention_service.build_mention_users(db, content))


def build_mention_users_for_contents(
    db: Session,
    contents: list[str],
) -> list[list[MentionUserData]]:
    """批量构建正文提及用户列表。

    Args:
        db: 当前数据库会话。
        contents: 多段帖子、文章、评论或转发链正文。

    Returns:
        list[list[MentionUserData]]: 与 ``contents`` 一一对应的提及用户元数据。

    Raises:
        数据库查询异常会透传给调用方。
    """

    return [
        _normalize_mention_users(mention_users)
        for mention_users in mention_service.build_mention_users_for_contents(db, contents)
    ]


def _normalize_mention_users(mention_users: list[dict[str, Any]]) -> list[MentionUserData]:
    """把提及服务返回值收窄为帖子响应使用的普通字典列表。

    Args:
        mention_users: 提及服务返回的用户元数据列表。

    Returns:
        list[MentionUserData]: 普通字典形式的用户元数据列表。
    """

    return [dict(mention_user) for mention_user in mention_users]
