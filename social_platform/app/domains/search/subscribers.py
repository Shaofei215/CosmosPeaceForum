"""搜索投影事件订阅器。

搜索索引是可由数据库重建的运行期投影，因此在主事务提交后更新，避免索引失败影响
用户的核心写操作。
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from social_platform.app.db.session import SessionLocal
from social_platform.app.domains.post.events import PostCreated, PostDeleted, PostUpdated, RepostCreated
from social_platform.app.domains.user.events import UserDeleted, UserUpdated
from social_platform.app.domains.post.models import Post
from social_platform.app.domains.user.models import User
from social_platform.app.shared.events import subscribe_domain_event
from social_platform.app.domains.search import application as search_service


def _index_post_by_id(post_id: int) -> None:
    """按帖子 ID 读取最新数据并更新搜索索引。

    Args:
        post_id: 待更新索引的帖子 ID。
    """

    db = SessionLocal()
    try:
        post = db.query(Post).filter(Post.id == post_id).first()
        if post is not None:
            search_service.index_post(post)
    finally:
        db.close()


def _index_user_by_id(user_id: int) -> None:
    """按用户 ID 读取最新数据并更新搜索索引。

    Args:
        user_id: 待更新索引的用户 ID。
    """

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if user is not None:
            search_service.index_user(user)
    finally:
        db.close()


def handle_post_created(_: Session, event: PostCreated) -> None:
    """提交后更新新帖子的搜索索引。"""

    _index_post_by_id(event.post_id)


def handle_post_updated(_: Session, event: PostUpdated) -> None:
    """提交后更新已编辑帖子的搜索索引。"""

    _index_post_by_id(event.post_id)


def handle_repost_created(_: Session, event: RepostCreated) -> None:
    """提交后更新转发帖子的搜索索引。"""

    _index_post_by_id(event.repost_id)


def handle_post_deleted(_: Session, event: PostDeleted) -> None:
    """提交后删除已删除帖子的搜索索引。"""

    search_service.delete_post(event.post_id)


def handle_user_updated(_: Session, event: UserUpdated) -> None:
    """提交后更新用户搜索索引。"""

    _index_user_by_id(event.user_id)


def handle_user_deleted(_: Session, event: UserDeleted) -> None:
    """提交后删除用户及其帖子搜索索引。"""

    search_service.delete_user(event.user_id)
    for post_id in event.post_ids:
        search_service.delete_post(post_id)


def register_search_subscribers() -> None:
    """注册搜索投影事件订阅器。"""

    subscribe_domain_event(PostCreated, handle_post_created, phase="after_commit")
    subscribe_domain_event(PostUpdated, handle_post_updated, phase="after_commit")
    subscribe_domain_event(PostDeleted, handle_post_deleted, phase="after_commit")
    subscribe_domain_event(UserUpdated, handle_user_updated, phase="after_commit")
    subscribe_domain_event(UserDeleted, handle_user_deleted, phase="after_commit")
