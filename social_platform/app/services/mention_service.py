"""提及解析服务。

本模块负责把帖子、文章和评论正文中的 ``@用户名`` 解析为前端与 Agent
可消费的用户元数据。它位于服务层，供 feed、post、comment 与转发逻辑复用，
避免各入口重复查询用户表。
"""

import re
from typing import Any, TypedDict

from sqlalchemy.orm import Session

from social_platform.app.models.user import User


class MentionUser(TypedDict):
    """正文中一次可跳转提及对应的用户信息。"""

    user_id: int
    username: str


MENTION_USERNAME_PATTERN = re.compile(r"@([a-zA-Z0-9_一-龥]+)")


def extract_mention_usernames(content: str) -> list[str]:
    """从正文中按出现顺序提取去重后的用户名。

    Args:
        content: 帖子、文章或评论正文。

    Returns:
        list[str]: 去重且保持首次出现顺序的用户名列表。

    Raises:
        本函数不主动抛出业务异常。
    """
    return list(dict.fromkeys(MENTION_USERNAME_PATTERN.findall(content or "")))


def build_mention_users(db: Session, content: str) -> list[MentionUser]:
    """为单段正文构建提及用户元数据。

    Args:
        db: SQLAlchemy 数据库会话。
        content: 需要解析的正文。

    Returns:
        list[MentionUser]: 已存在用户的提及元数据，保持正文中的首次出现顺序。

    Raises:
        数据库查询异常会透传给调用方。
    """
    return build_mention_users_for_contents(db, [content])[0]


def build_mention_users_for_contents(
    db: Session,
    contents: list[str],
) -> list[list[MentionUser]]:
    """批量为多段正文构建提及用户元数据。

    Args:
        db: SQLAlchemy 数据库会话。
        contents: 多段帖子、文章或评论正文。

    Returns:
        list[list[MentionUser]]: 与 ``contents`` 一一对应的提及用户列表。

    Raises:
        数据库查询异常会透传给调用方。
    """
    usernames_by_content = [extract_mention_usernames(content) for content in contents]
    all_usernames = list(
        dict.fromkeys(username for usernames in usernames_by_content for username in usernames)
    )
    if not all_usernames:
        return [[] for _ in contents]

    users = db.query(User).filter(User.username.in_(all_usernames)).all()
    user_by_name = {user.username: user for user in users}
    return [
        [
            {"user_id": user_by_name[username].id, "username": username}
            for username in usernames
            if username in user_by_name
        ]
        for usernames in usernames_by_content
    ]


def attach_mention_users(db: Session, item: Any, content: str | None = None) -> Any:
    """把 ``mention_users`` 临时挂载到 ORM 对象或响应对象上。

    Args:
        db: SQLAlchemy 数据库会话。
        item: 需要补充响应字段的对象。
        content: 可选正文；为空时读取 ``item.content``。

    Returns:
        Any: 原对象，便于调用方链式返回。

    Raises:
        数据库查询异常会透传给调用方。
    """
    item.mention_users = build_mention_users(db, content if content is not None else item.content)
    return item


def attach_mention_users_for_items(db: Session, items: list[Any]) -> list[Any]:
    """批量把 ``mention_users`` 临时挂载到对象列表上。

    Args:
        db: SQLAlchemy 数据库会话。
        items: 拥有 ``content`` 属性的 ORM 对象列表。

    Returns:
        list[Any]: 原对象列表，已按顺序补充 ``mention_users``。

    Raises:
        数据库查询异常会透传给调用方。
    """
    mention_users_by_item = build_mention_users_for_contents(
        db,
        [getattr(item, "content", "") for item in items],
    )
    for item, mention_users in zip(items, mention_users_by_item):
        item.mention_users = mention_users
    return items
