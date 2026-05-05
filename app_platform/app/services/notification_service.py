from typing import Dict, List, Optional, Tuple

from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app_platform.app.models.comment import Comment
from app_platform.app.models.follow import Follow
from app_platform.app.models.notification import Notification
from app_platform.app.models.post import Post
from app_platform.app.models.user import User


LIKE_TYPES = {"post_like", "comment_like"}
COMMENT_TYPES = {"comment", "comment_reply"}
FOLLOW_TYPES = {"follow"}


def create_notification(
    db: Session,
    recipient_id: int,
    sender_id: Optional[int],
    notification_type: str,
    resource_type: str,
    resource_id: int,
    post_id: Optional[int] = None,
    comment_id: Optional[int] = None,
    source_content: Optional[str] = None,
) -> Optional[Notification]:
    if not recipient_id or recipient_id == sender_id:
        return None

    notification = Notification(
        recipient_id=recipient_id,
        sender_id=sender_id,
        type=notification_type,
        resource_type=resource_type,
        resource_id=resource_id,
        post_id=post_id,
        comment_id=comment_id,
        source_content=_truncate(source_content),
        is_read=0,
    )
    db.add(notification)
    return notification


def create_post_like_notification(db: Session, post: Post, sender_id: int) -> None:
    create_notification(
        db=db,
        recipient_id=post.author_id,
        sender_id=sender_id,
        notification_type="post_like",
        resource_type="post",
        resource_id=post.id,
        post_id=post.id,
        source_content=post.content,
    )


def create_comment_like_notification(db: Session, comment: Comment, sender_id: int) -> None:
    create_notification(
        db=db,
        recipient_id=comment.owner_id,
        sender_id=sender_id,
        notification_type="comment_like",
        resource_type="comment",
        resource_id=comment.id,
        post_id=comment.post_id,
        comment_id=comment.id,
        source_content=comment.content,
    )


def create_comment_notifications(
    db: Session,
    post: Post,
    comment: Comment,
    sender_id: int,
    parent_comment: Optional[Comment] = None,
) -> None:
    notified = set()

    if parent_comment is not None:
        create_notification(
            db=db,
            recipient_id=parent_comment.owner_id,
            sender_id=sender_id,
            notification_type="comment_reply",
            resource_type="comment",
            resource_id=comment.id,
            post_id=post.id,
            comment_id=comment.id,
            source_content=comment.content,
        )
        notified.add(parent_comment.owner_id)

    if post.author_id not in notified:
        create_notification(
            db=db,
            recipient_id=post.author_id,
            sender_id=sender_id,
            notification_type="comment_reply" if parent_comment else "comment",
            resource_type="comment",
            resource_id=comment.id,
            post_id=post.id,
            comment_id=comment.id,
            source_content=comment.content,
        )


def create_follow_notification(db: Session, follower_id: int, following_id: int) -> None:
    create_notification(
        db=db,
        recipient_id=following_id,
        sender_id=follower_id,
        notification_type="follow",
        resource_type="user",
        resource_id=follower_id,
    )


def get_notifications(
    db: Session,
    user_id: int,
    skip: int = 0,
    limit: int = 20,
    notification_type: Optional[str] = None,
    mark_read: bool = True,
) -> Tuple[List[Notification], int, int]:
    query = db.query(Notification).filter(Notification.recipient_id == user_id)
    if notification_type:
        query = query.filter(Notification.type == notification_type)

    total = query.count()
    items = query.options(joinedload(Notification.sender)).order_by(
        Notification.created_at.desc()
    ).offset(skip).limit(limit).all()

    if mark_read:
        mark_all_as_read(db, user_id)
        for item in items:
            item.is_read = 1

    unread_count = get_unread_count(db, user_id)
    return items, total, unread_count


def get_notification(db: Session, user_id: int, notification_id: int) -> Optional[Notification]:
    return db.query(Notification).options(joinedload(Notification.sender)).filter(
        Notification.id == notification_id,
        Notification.recipient_id == user_id,
    ).first()


def get_unread_count(db: Session, user_id: int) -> int:
    return db.query(func.count(Notification.id)).filter(
        Notification.recipient_id == user_id,
        Notification.is_read == 0,
    ).scalar() or 0


def mark_all_as_read(db: Session, user_id: int) -> int:
    updated = db.query(Notification).filter(
        Notification.recipient_id == user_id,
        Notification.is_read == 0,
    ).update({"is_read": 1}, synchronize_session=False)
    db.commit()
    return updated


def get_summary(db: Session, user_id: int) -> Dict[str, int]:
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return {"following_count": 0, "followers_count": 0, "unread_count": 0}

    return {
        "following_count": user.following_count,
        "followers_count": user.followers_count,
        "unread_count": get_unread_count(db, user_id),
    }


def get_origin(db: Session, notification: Notification) -> Dict[str, object]:
    if notification.post_id:
        post = db.query(Post).options(joinedload(Post.author)).filter(Post.id == notification.post_id).first()
    else:
        post = None

    if notification.comment_id:
        comment = db.query(Comment).options(joinedload(Comment.owner)).filter(
            Comment.id == notification.comment_id
        ).first()
    else:
        comment = None

    if notification.resource_type == "user" and notification.sender_id:
        user = db.query(User).filter(User.id == notification.sender_id).first()
    else:
        user = None

    return {"post": post, "comment": comment, "user": user}


def _truncate(content: Optional[str], max_len: int = 500) -> Optional[str]:
    if content is None:
        return None
    return content[:max_len]
