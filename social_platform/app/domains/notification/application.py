import re
from typing import Dict, List, Optional, Tuple, TypedDict

from sqlalchemy import func
from sqlalchemy import event
from sqlalchemy.orm import Session, joinedload

from social_platform.app.domains.comment.models import Comment
from social_platform.app.domains.follow.models import Follow
from social_platform.app.domains.mention import application as mention_service
from social_platform.app.domains.notification.models import Notification
from social_platform.app.domains.post.models import Post
from social_platform.app.domains.user.models import User
from social_platform.app.domains.notification.stream import publish_notification_update


LIKE_TYPES = {"post_like", "comment_like"}
COMMENT_TYPES = {"comment", "comment_reply"}
FOLLOW_TYPES = {"follow"}
REPOST_TYPES = {"repost"}
_PENDING_NOTIFICATION_RECIPIENTS_KEY = "pending_notification_recipient_ids"


class NotificationOrigin(TypedDict):
    """通知跳转来源中可能存在的帖子、评论和用户对象。"""

    post: Post | None
    comment: Comment | None
    user: User | None


@event.listens_for(Session, "after_commit")
def _publish_pending_notification_updates(session: Session) -> None:
    """事务提交后发布通知版本更新，供 SSE 客户端刷新未读状态。"""
    recipient_ids = session.info.pop(_PENDING_NOTIFICATION_RECIPIENTS_KEY, set())
    for recipient_id in recipient_ids:
        publish_notification_update(recipient_id)


@event.listens_for(Session, "after_rollback")
def _clear_pending_notification_updates(session: Session) -> None:
    """事务回滚时清理待发布通知状态，避免失败事务产生外部副作用。"""
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
    truncate_source_content: bool = True,
    created_by_agent: bool = False,
) -> Optional[Notification]:
    """创建通知记录并登记提交后的实时推送更新。"""
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
        source_content=_truncate(source_content) if truncate_source_content else source_content,
        is_read=0,
        created_by_agent=created_by_agent,
    )
    db.add(notification)
    pending = db.info.setdefault(_PENDING_NOTIFICATION_RECIPIENTS_KEY, set())
    pending.add(recipient_id)
    return notification


def create_post_like_notification(
    db: Session,
    post: Post,
    sender_id: int,
    created_by_agent: bool = False,
) -> None:
    """为帖子点赞事件创建通知，由 notification 订阅 reaction 事件后调用。"""
    create_notification(
        db=db,
        recipient_id=post.author_id,
        sender_id=sender_id,
        notification_type="post_like",
        resource_type="post",
        resource_id=post.id,
        post_id=post.id,
        source_content=format_post_source_content(post),
        created_by_agent=created_by_agent,
    )


def create_post_coin_notification(
    db: Session,
    post: Post,
    sender_id: int,
    created_by_agent: bool = False,
) -> None:
    """为帖子投币事件创建通知。"""

    create_notification(
        db=db,
        recipient_id=post.author_id,
        sender_id=sender_id,
        notification_type="post_coin",
        resource_type="post",
        resource_id=post.id,
        post_id=post.id,
        source_content=format_post_source_content(post),
        created_by_agent=created_by_agent,
    )


def create_comment_like_notification(
    db: Session,
    comment: Comment,
    sender_id: int,
    created_by_agent: bool = False,
) -> None:
    """为评论点赞事件创建通知，由 notification 订阅 reaction 事件后调用。"""
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
        created_by_agent=created_by_agent,
    )


def create_comment_notifications(
    db: Session,
    post: Post,
    comment: Comment,
    sender_id: int,
    parent_comment: Optional[Comment] = None,
    excluded_recipient_ids: Optional[set[int]] = None,
    created_by_agent: bool = False,
) -> None:
    """为评论或回复事件创建对应通知，保持通知生成逻辑归属通知领域。

    Args:
        db: 当前数据库会话。
        post: 被评论的帖子。
        comment: 新创建的评论。
        sender_id: 评论发布者 ID。
        parent_comment: 回复场景中的父评论，为空表示一级评论。
        excluded_recipient_ids: 已因同一内容收到更具体通知的用户 ID 集合。

    Returns:
        None: 通知记录由当前数据库事务统一提交。
    """
    excluded_recipient_ids = excluded_recipient_ids or set()
    if parent_comment is not None:
        if parent_comment.owner_id in excluded_recipient_ids:
            return
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
            created_by_agent=created_by_agent,
        )
        return

    if post.author_id in excluded_recipient_ids:
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
        created_by_agent=created_by_agent,
    )


def create_mention_notifications(
    db: Session,
    *,
    sender_id: int,
    content: str,
    resource_type: str,
    resource_id: int,
    post_id: int,
    comment_id: Optional[int] = None,
    created_by_agent: bool = False,
) -> set[int]:
    """为正文中实际存在的被提及用户创建通知。

    Args:
        db: 当前数据库会话。
        sender_id: 发布提及内容的用户 ID。
        content: 帖子或评论正文，同时作为通知中的来源原文。
        resource_type: 提及所在资源类型，支持 ``post`` 和 ``comment``。
        resource_id: 提及所在帖子或评论 ID。
        post_id: 通知跳转和互动操作指向的帖子 ID。
        comment_id: 评论提及时对应的评论 ID，帖子提及时为空。

    Returns:
        set[int]: 实际创建提及通知的接收者 ID，用于避免同一内容产生重复通知。

    Raises:
        数据库查询异常会透传给调用方。
    """
    recipient_ids: set[int] = set()
    for mentioned_user in mention_service.build_mention_users(db, content):
        recipient_id = mentioned_user["user_id"]
        notification = create_notification(
            db=db,
            recipient_id=recipient_id,
            sender_id=sender_id,
            notification_type="mention",
            resource_type=resource_type,
            resource_id=resource_id,
            post_id=post_id,
            comment_id=comment_id,
            source_content=content,
            created_by_agent=created_by_agent,
        )
        if notification is not None:
            recipient_ids.add(recipient_id)
    return recipient_ids


def create_follow_notification(
    db: Session,
    follower_id: int,
    following_id: int,
    created_by_agent: bool = False,
) -> None:
    """为关注状态开启事件创建通知，由 notification 订阅 follow 事件后调用。"""
    create_notification(
        db=db,
        recipient_id=following_id,
        sender_id=follower_id,
        notification_type="follow",
        resource_type="user",
        resource_id=follower_id,
        created_by_agent=created_by_agent,
    )


def create_repost_notifications(
    db: Session,
    root_post: Post,
    repost: Post,
    sender_id: int,
    source_post: Optional[Post] = None,
    source_comment: Optional[Comment] = None,
    source_content: Optional[str] = None,
    created_by_agent: bool = False,
) -> None:
    """为转发事件创建通知，并去重原作者、源作者等可能重复的接收者。"""
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
            created_by_agent=created_by_agent,
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
    """分页查询用户通知，并按需要将已拉取通知标记为已读。"""
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
    """按用户和通知 ID 查询单条通知，防止跨用户读取。"""
    return db.query(Notification).options(joinedload(Notification.sender)).filter(
        Notification.id == notification_id,
        Notification.recipient_id == user_id,
    ).first()


def get_unread_count(db: Session, user_id: int) -> int:
    """统计用户未读通知数量，供导航徽标和 summary 接口使用。"""
    return db.query(func.count(Notification.id)).filter(
        Notification.recipient_id == user_id,
        Notification.is_read == 0,
    ).scalar() or 0


def mark_all_as_read(db: Session, user_id: int) -> int:
    """将用户未读通知批量标记为已读，并发布实时更新信号。"""
    updated = db.query(Notification).filter(
        Notification.recipient_id == user_id,
        Notification.is_read == 0,
    ).update({"is_read": 1}, synchronize_session=False)
    db.commit()
    if updated:
        publish_notification_update(user_id)
    return updated


def get_summary(db: Session, user_id: int) -> Dict[str, int]:
    """汇总关注计数和未读通知计数，供通知中心头部使用。"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return {"following_count": 0, "followers_count": 0, "unread_count": 0}

    return {
        "following_count": user.following_count,
        "followers_count": user.followers_count,
        "unread_count": get_unread_count(db, user_id),
    }


def get_origin(db: Session, notification: Notification) -> NotificationOrigin:
    """解析通知来源对象，供 API 层组装跳转和展示上下文。"""
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
    """格式化帖子来源摘要，供通知列表展示被互动内容。"""
    if getattr(post, "type", "post") == "article":
        title = (post.title or "Untitled").strip()
        body = _plain_markdown(post.content)
        return _truncate(f"文章标题：{title}\n正文：{body}", max_len) or ""
    return _truncate(post.content, max_len) or ""


def _plain_markdown(content: Optional[str]) -> str:
    """将 Markdown 内容压缩为纯文本摘要，避免通知中暴露格式标记。"""
    text = content or ""
    text = re.sub(r"```[\s\S]*?```", " ", text)
    text = re.sub(r"`([^`]*)`", r"\1", text)
    text = re.sub(r"!\[[^\]]*\]\([^)]+\)", " ", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"^[#>\-\*\+\d\.\s]+", "", text, flags=re.MULTILINE)
    text = re.sub(r"[*_~]+", "", text)
    return re.sub(r"\s+", " ", text).strip()


def _truncate(content: Optional[str], max_len: int = 500) -> Optional[str]:
    """截断通知来源文本，控制存储和响应体大小。"""
    if content is None:
        return None
    return content[:max_len]
