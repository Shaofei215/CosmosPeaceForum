"""通知领域事件订阅器。

该模块把互动领域事件转换为通知记录，保持通知生成规则集中在通知领域内。
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from social_platform.app.domains.events import (
    CommentCreated,
    CommentLiked,
    PostLiked,
    RepostCreated,
    UserFollowed,
)
from social_platform.app.models.comment import Comment
from social_platform.app.models.post import Post
from social_platform.app.shared.events import subscribe_domain_event
from social_platform.app.services import notification_service


def handle_post_liked(db: Session, event: PostLiked) -> None:
    """处理帖子点赞事件并创建通知。

    Args:
        db: 当前事务使用的数据库会话。
        event: 帖子点赞事件。
    """

    post = db.query(Post).filter(Post.id == event.post_id).first()
    if post is None:
        return
    notification_service.create_post_like_notification(db, post, event.sender_id)


def handle_comment_liked(db: Session, event: CommentLiked) -> None:
    """处理评论点赞事件并创建通知。

    Args:
        db: 当前事务使用的数据库会话。
        event: 评论点赞事件。
    """

    comment = db.query(Comment).filter(Comment.id == event.comment_id).first()
    if comment is None:
        return
    notification_service.create_comment_like_notification(db, comment, event.sender_id)


def handle_comment_created(db: Session, event: CommentCreated) -> None:
    """处理评论创建事件并创建评论或回复通知。

    Args:
        db: 当前事务使用的数据库会话。
        event: 评论创建事件。
    """

    post = db.query(Post).filter(Post.id == event.post_id).first()
    comment = db.query(Comment).filter(Comment.id == event.comment_id).first()
    if post is None or comment is None:
        return

    parent_comment = None
    if event.parent_comment_id is not None:
        parent_comment = db.query(Comment).filter(Comment.id == event.parent_comment_id).first()

    notification_service.create_comment_notifications(
        db=db,
        post=post,
        comment=comment,
        sender_id=event.sender_id,
        parent_comment=parent_comment,
    )


def handle_user_followed(db: Session, event: UserFollowed) -> None:
    """处理用户关注事件并创建通知。

    Args:
        db: 当前事务使用的数据库会话。
        event: 用户关注事件。
    """

    notification_service.create_follow_notification(db, event.follower_id, event.following_id)


def handle_repost_created(db: Session, event: RepostCreated) -> None:
    """处理转发创建事件并创建通知。

    Args:
        db: 当前事务使用的数据库会话。
        event: 转发创建事件。
    """

    root_post = db.query(Post).filter(Post.id == event.root_post_id).first()
    repost = db.query(Post).filter(Post.id == event.repost_id).first()
    if root_post is None or repost is None:
        return

    source_post = None
    if event.source_post_id is not None:
        source_post = db.query(Post).filter(Post.id == event.source_post_id).first()

    source_comment = None
    if event.source_comment_id is not None:
        source_comment = db.query(Comment).filter(Comment.id == event.source_comment_id).first()

    notification_service.create_repost_notifications(
        db=db,
        root_post=root_post,
        repost=repost,
        sender_id=event.sender_id,
        source_post=source_post,
        source_comment=source_comment,
        source_content=event.source_content,
    )


def register_notification_subscribers() -> None:
    """注册通知领域事件订阅器。"""

    subscribe_domain_event(PostLiked, handle_post_liked)
    subscribe_domain_event(CommentLiked, handle_comment_liked)
    subscribe_domain_event(CommentCreated, handle_comment_created)
    subscribe_domain_event(UserFollowed, handle_user_followed)
    subscribe_domain_event(RepostCreated, handle_repost_created)
