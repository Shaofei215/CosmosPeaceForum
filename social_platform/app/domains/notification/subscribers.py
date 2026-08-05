"""通知领域事件订阅器。

该模块把其他领域的状态变化事件转换为通知记录，保持通知生成规则集中在通知领域内。
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from social_platform.app.domains.comment.events import CommentCreated
from social_platform.app.domains.comment.models import Comment
from social_platform.app.domains.coin.events import PostCoinGiven
from social_platform.app.domains.content_safety.events import (
    ContentModerationActionApplied,
    ReportedContentViolationConfirmed,
)
from social_platform.app.domains.follow.events import FollowChanged
from social_platform.app.domains.post.events import PostCreated, RepostCreated
from social_platform.app.domains.post.models import Post
from social_platform.app.domains.reaction.events import LikeChanged
from social_platform.app.shared.events import subscribe_domain_event
from social_platform.app.domains.notification import application as notification_service
from social_platform.app.domains.notification.system import create_system_notifications


def handle_like_changed(db: Session, event: LikeChanged) -> None:
    """处理点赞状态变化，只在新增点赞时创建通知。"""

    if not event.current_state or event.previous_state:
        return

    if event.target_type == "post":
        post = db.query(Post).filter(Post.id == event.target_id).first()
        if post is not None:
            notification_service.create_post_like_notification(
                db,
                post,
                event.actor_id,
                created_by_agent=event.created_by_agent,
            )
        return

    comment = db.query(Comment).filter(Comment.id == event.target_id).first()
    if comment is not None:
        notification_service.create_comment_like_notification(
            db,
            comment,
            event.actor_id,
            created_by_agent=event.created_by_agent,
        )


def handle_post_coin_given(db: Session, event: PostCoinGiven) -> None:
    """投币成功后通知帖子作者。"""

    post = db.query(Post).filter(Post.id == event.post_id).first()
    if post is not None:
        notification_service.create_post_coin_notification(
            db,
            post,
            event.sender_id,
            created_by_agent=event.created_by_agent,
        )


def handle_comment_created(db: Session, event: CommentCreated) -> None:
    """处理评论创建事件并创建评论或回复通知。"""

    post = db.query(Post).filter(Post.id == event.post_id).first()
    comment = db.query(Comment).filter(Comment.id == event.comment_id).first()
    if post is None or comment is None:
        return

    parent_comment = None
    if event.parent_comment_id is not None:
        parent_comment = db.query(Comment).filter(Comment.id == event.parent_comment_id).first()

    mentioned_recipient_ids = notification_service.create_mention_notifications(
        db=db,
        sender_id=event.sender_id,
        content=comment.content,
        resource_type="comment",
        resource_id=comment.id,
        post_id=post.id,
        comment_id=comment.id,
        created_by_agent=event.created_by_agent,
    )
    notification_service.create_comment_notifications(
        db=db,
        post=post,
        comment=comment,
        sender_id=event.sender_id,
        parent_comment=parent_comment,
        excluded_recipient_ids=mentioned_recipient_ids,
        created_by_agent=event.created_by_agent,
    )


def handle_post_created(db: Session, event: PostCreated) -> None:
    """处理帖子创建事件并向正文中被提及的用户发送通知。

    Args:
        db: 当前数据库会话。
        event: 帖子创建事件，提供帖子和发布者 ID。

    Returns:
        None: 通知随帖子创建事务统一提交。

    Raises:
        数据库查询或通知创建异常会透传给帖子创建事务。
    """

    post = db.query(Post).filter(Post.id == event.post_id).first()
    if post is None:
        return

    notification_service.create_mention_notifications(
        db=db,
        sender_id=event.author_id,
        content=post.content,
        resource_type="post",
        resource_id=post.id,
        post_id=post.id,
        created_by_agent=event.created_by_agent,
    )


def handle_follow_changed(db: Session, event: FollowChanged) -> None:
    """处理关注状态变化，只在新增关注时创建通知。"""

    if not event.current_state or event.previous_state:
        return
    notification_service.create_follow_notification(
        db,
        event.follower_id,
        event.following_id,
        created_by_agent=event.created_by_agent,
    )


def handle_repost_created(db: Session, event: RepostCreated) -> None:
    """处理转发创建事件并创建通知。"""

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
        created_by_agent=event.created_by_agent,
    )


def handle_content_moderation_action_applied(
    db: Session,
    event: ContentModerationActionApplied,
) -> None:
    """处理内容安全处罚事件并通知内容作者。"""

    content = "你的内容因违反社区规则已被管理端处理。"
    if event.reason:
        content = f"{content}\n原因：{event.reason}"
    create_system_notifications(
        db=db,
        recipient_ids=[event.recipient_id],
        content=content,
        notification_type="moderation",
        resource_type=event.resource_type,
        resource_id=event.resource_id,
    )


def handle_reported_content_violation_confirmed(
    db: Session,
    event: ReportedContentViolationConfirmed,
) -> None:
    """处理举报确认违规事件并通知举报人。"""

    create_system_notifications(
        db=db,
        recipient_ids=event.reporter_ids,
        content="你举报的目标存在违规，已被管理端处理。",
        notification_type="moderation",
        resource_type=event.resource_type,
        resource_id=event.resource_id,
    )


def register_notification_subscribers() -> None:
    """注册通知领域事件订阅器。"""

    subscribe_domain_event(LikeChanged, handle_like_changed)
    subscribe_domain_event(PostCoinGiven, handle_post_coin_given)
    subscribe_domain_event(PostCreated, handle_post_created)
    subscribe_domain_event(CommentCreated, handle_comment_created)
    subscribe_domain_event(FollowChanged, handle_follow_changed)
    subscribe_domain_event(RepostCreated, handle_repost_created)
    subscribe_domain_event(ContentModerationActionApplied, handle_content_moderation_action_applied)
    subscribe_domain_event(
        ReportedContentViolationConfirmed,
        handle_reported_content_violation_confirmed,
    )
