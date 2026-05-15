import re
from typing import Dict, List, Optional, Tuple

from sqlalchemy import func
from sqlalchemy import event
from sqlalchemy.orm import Session, joinedload

from app_platform.app.models.comment import Comment
from app_platform.app.models.follow import Follow
from app_platform.app.models.notification import Notification
from app_platform.app.models.post import Post
from app_platform.app.models.user import User
from app_platform.app.services.notification_events import publish_notification_update


LIKE_TYPES = {"post_like", "comment_like"}
COMMENT_TYPES = {"comment", "comment_reply"}
FOLLOW_TYPES = {"follow"}
REPOST_TYPES = {"repost"}
_PENDING_NOTIFICATION_RECIPIENTS_KEY = "pending_notification_recipient_ids"


@event.listens_for(Session, "after_commit")
def _publish_pending_notification_updates(session: Session) -> None:
    recipient_ids = session.info.pop(_PENDING_NOTIFICATION_RECIPIENTS_KEY, set())
    for recipient_id in recipient_ids:
        publish_notification_update(recipient_id)


@event.listens_for(Session, "after_rollback")
def _clear_pending_notification_updates(session: Session) -> None:
    session.info.pop(_PENDING_NOTIFICATION_RECIPIENTS_KEY, None)


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
    pending = db.info.setdefault(_PENDING_NOTIFICATION_RECIPIENTS_KEY, set())
    pending.add(recipient_id)
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
        source_content=format_post_source_content(post),
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
        return

    create_notification(
        db=db,
        recipient_id=post.author_id,
        sender_id=sender_id,
        notification_type="comment",
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


def create_repost_notifications(
    db: Session,
    root_post: Post,
    repost: Post,
    sender_id: int,
    source_post: Optional[Post] = None,
    source_comment: Optional[Comment] = None,
    source_content: Optional[str] = None,
) -> None:
    recipients = []
    if source_comment is not None:
        recipients.append(source_comment.owner_id)
    if source_post is not None:
        recipients.append(source_post.author_id)
    recipients.append(root_post.author_id)

    notified = set()
    display_content = source_content or format_post_source_content(repost)
    if getattr(root_post, "type", "post") == "article":
        display_content = _truncate(
            f"{display_content}\n{format_post_source_content(root_post)}",
            500,
        )
    for recipient_id in recipients:
        if recipient_id in notified:
            continue
        create_notification(
            db=db,
            recipient_id=recipient_id,
            sender_id=sender_id,
            notification_type="repost",
            resource_type="post",
            resource_id=repost.id,
            post_id=repost.id,
            source_content=display_content,
        )
        notified.add(recipient_id)


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
    items = query.options(
        joinedload(Notification.sender),
        joinedload(Notification.post).joinedload(Post.repost_root_post),
    ).order_by(
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
    if updated:
        publish_notification_update(user_id)
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
        post = db.query(Post).options(
            joinedload(Post.author),
            joinedload(Post.repost_root_post).joinedload(Post.author),
        ).filter(Post.id == notification.post_id).first()
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


def format_post_source_content(post: Post, max_len: int = 500) -> str:
    if getattr(post, "type", "post") == "article":
        title = (post.title or "Untitled").strip()
        body = _plain_markdown(post.content)
        return _truncate(f"文章标题：{title}\n正文：{body}", max_len) or ""
    return _truncate(post.content, max_len) or ""


def _plain_markdown(content: Optional[str]) -> str:
    text = content or ""
    text = re.sub(r"```[\s\S]*?```", " ", text)
    text = re.sub(r"`([^`]*)`", r"\1", text)
    text = re.sub(r"!\[[^\]]*\]\([^)]+\)", " ", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"^[#>\-\*\+\d\.\s]+", "", text, flags=re.MULTILINE)
    text = re.sub(r"[*_~]+", "", text)
    return re.sub(r"\s+", " ", text).strip()


def _truncate(content: Optional[str], max_len: int = 500) -> Optional[str]:
    if content is None:
        return None
    return content[:max_len]
