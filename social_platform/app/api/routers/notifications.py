import asyncio
import json
from collections.abc import Sequence

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session, object_session

from social_platform.app.api.deps import (
    get_current_user_id_for_stream,
    get_db,
    get_current_user_including_banned,
)
from social_platform.app.db.session import SessionLocal
from social_platform.app.domains.comment.models import Comment, CommentLike
from social_platform.app.domains.notification.models import Notification
from social_platform.app.domains.post.models import Post
from social_platform.app.domains.reaction.models import Like
from social_platform.app.domains.user.models import User
from social_platform.app.domains.notification.schemas import (
    NotificationListResponse,
    NotificationResponse,
    NotificationSummaryResponse,
    NotificationUnreadCountResponse,
)
from social_platform.app.domains.content_safety import appeal_application
from social_platform.app.domains.content_safety.schemas import (
    ModerationAppealCreate,
    ModerationAppealResponse,
)
from social_platform.app.domains.notification import application as notification_service
from social_platform.app.domains.post import queries as post_queries
from social_platform.app.domains.topic import queries as topic_queries
from social_platform.app.domains.mention import application as mention_service
from social_platform.app.domains.notification.stream import (
    get_notification_version,
    wait_for_notification_update,
)

router = APIRouter()
_STREAM_MAX_LIFETIME_SECONDS = 300.0
_STREAM_HEARTBEAT_SECONDS = 25.0


@router.get("", response_model=NotificationListResponse)
def list_notifications(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    type: str | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_including_banned),
):
    items, total, unread_count = notification_service.get_notifications(
        db=db,
        user_id=current_user.id,
        skip=skip,
        limit=limit,
        notification_type=type,
        mark_read=True,
    )
    _attach_appeal_statuses(db, items, current_user.id)
    return NotificationListResponse(
        items=[NotificationResponse.model_validate(item) for item in items],
        total=total,
        unread_count=unread_count,
        skip=skip,
        limit=limit,
    )


@router.get("/summary", response_model=NotificationSummaryResponse)
def get_notification_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_including_banned),
):
    return notification_service.get_summary(db, current_user.id)


@router.get("/unread-count", response_model=NotificationUnreadCountResponse)
def get_unread_count(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_including_banned),
):
    return NotificationUnreadCountResponse(
        unread_count=notification_service.get_unread_count(db, current_user.id)
    )


@router.get("/events")
async def stream_notification_events(
    user_id: int = Depends(get_current_user_id_for_stream),
):
    """通过 Authorization Header 建立通知 SSE，避免凭据进入 URL 与访问日志。"""

    def build_payload(event_type: str) -> dict[str, int | str]:
        """为 SSE 事件即时读取最新通知摘要，避免长连接复用已关闭的请求会话。"""
        db = SessionLocal()
        try:
            summary = notification_service.get_summary(db, user_id)
            return {
                "type": event_type,
                "unread_count": summary.get("unread_count", 0),
                "following_count": summary.get("following_count", 0),
                "followers_count": summary.get("followers_count", 0),
            }
        finally:
            db.close()

    async def event_stream():
        version = get_notification_version(user_id)
        loop = asyncio.get_running_loop()
        deadline = loop.time() + _STREAM_MAX_LIFETIME_SECONDS
        yield _sse_event("notifications.changed", build_payload("connected"))

        while True:
            remaining = deadline - loop.time()
            if remaining <= 0:
                return
            next_version = await asyncio.to_thread(
                wait_for_notification_update,
                user_id,
                version,
                min(_STREAM_HEARTBEAT_SECONDS, remaining),
            )
            if next_version > version:
                version = next_version
                yield _sse_event("notifications.changed", build_payload("changed"))
            else:
                yield ": heartbeat\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/{notification_id}", response_model=NotificationResponse)
def get_notification(
    notification_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_including_banned),
):
    notification = notification_service.get_notification(db, current_user.id, notification_id)
    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")
    _attach_appeal_statuses(db, [notification], current_user.id)
    return notification


@router.post("/{notification_id}/appeal", response_model=ModerationAppealResponse)
def submit_moderation_appeal(
    notification_id: int,
    request: ModerationAppealCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_including_banned),
):
    """基于当前用户收到的处罚通知创建或覆盖站内申诉。"""

    try:
        appeal = appeal_application.create_or_update_appeal(
            db=db,
            notification_id=notification_id,
            appellant=current_user,
            reason=request.reason,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return ModerationAppealResponse(id=appeal.id, status=appeal.status, message="申诉已提交")


@router.post("/mark-read")
def mark_notifications_read(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_including_banned),
):
    updated = notification_service.mark_all_as_read(db, current_user.id)
    return {"updated_count": updated}


@router.get("/{notification_id}/origin")
def get_notification_origin(
    notification_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_including_banned),
):
    notification = notification_service.get_notification(db, current_user.id, notification_id)
    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")
    origin = notification_service.get_origin(db, notification)
    return {
        "post": _serialize_post(db, origin.get("post"), current_user.id),
        "comment": _serialize_comment(db, origin.get("comment"), current_user.id),
        "user": _serialize_user(origin.get("user")),
    }


def _serialize_user(user: User | None):
    if not user:
        return None
    return {
        "id": user.id,
        "username": user.username,
        "bio": user.bio,
        "avatar_url": user.avatar_url,
        "created_at": user.created_at,
        "following_count": user.following_count,
        "followers_count": user.followers_count,
    }


def _serialize_post(db: Session, post: Post | None, current_user_id: int):
    if not post:
        return None
    is_liked = db.query(Like).filter(
        Like.user_id == current_user_id,
        Like.post_id == post.id,
    ).first() is not None
    post_session = object_session(post)
    return {
        "id": post.id,
        "author_id": post.author_id,
        "author": _serialize_user(post.author),
        "title": post.title,
        "type": getattr(post, "type", "post"),
        "content": post.content,
        "created_at": post.created_at,
        "created_by_agent": post.created_by_agent,
        "like_count": post.like_count,
        "comment_count": post.comment_count,
        "is_liked": is_liked,
        "is_liked_by_current_user": is_liked,
        "repost_count": getattr(post, "repost_count", 0),
        "repost_source_type": getattr(post, "repost_source_type", None),
        "repost_source_id": getattr(post, "repost_source_id", None),
        "repost_root_post_id": getattr(post, "repost_root_post_id", None),
        "repost_chain": getattr(post, "repost_chain", None),
        "repost_chain_authors": post_queries.build_repost_chain_authors(
            post_session,
            post.content,
        ) if post_session else [],
        "mention_users": post_queries.build_mention_users(
            post_session,
            post.content,
        ) if post_session else [],
        "topic_mentions": topic_queries.build_topic_mentions(
            post_session,
            post.id,
        ) if post_session else [],
        "repost_origin": _serialize_post(db, post.repost_root_post, current_user_id)
        if getattr(post, "repost_root_post_id", None) and getattr(post, "repost_root_post", None)
        else None,
    }


def _serialize_comment(db: Session, comment: Comment | None, current_user_id: int):
    if not comment:
        return None
    is_liked = db.query(CommentLike).filter(
        CommentLike.user_id == current_user_id,
        CommentLike.comment_id == comment.id,
    ).first() is not None
    return {
        "id": comment.id,
        "post_id": comment.post_id,
        "owner_id": comment.owner_id,
        "owner": _serialize_user(comment.owner),
        "parent_id": comment.parent_id,
        "content": comment.content,
        "created_at": comment.created_at,
        "created_by_agent": comment.created_by_agent,
        "like_count": comment.like_count,
        "reply_count": comment.reply_count,
        "is_liked": is_liked,
        "mention_users": mention_service.build_mention_users(db, comment.content),
    }


def _sse_event(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def _attach_appeal_statuses(
    db: Session,
    items: Sequence[Notification],
    user_id: int,
) -> None:
    """给通知对象动态附加申诉状态，供 Pydantic from_attributes 序列化。"""

    notification_ids = [item.id for item in items if getattr(item, "type", None) == "moderation"]
    statuses = appeal_application.get_notification_appeal_statuses(db, notification_ids)
    for item in items:
        if getattr(item, "type", None) == "moderation":
            setattr(item, "appeal_status", statuses.get(item.id))
            setattr(
                item,
                "can_appeal",
                appeal_application.is_notification_appealable(db, item, user_id),
            )
