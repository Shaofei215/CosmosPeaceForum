import asyncio
import json

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session, object_session

from social_platform.app.api.deps import get_access_payload, get_db, get_current_user_including_banned
from social_platform.app.db.session import SessionLocal
from social_platform.app.models.comment import CommentLike
from social_platform.app.models.like import Like
from social_platform.app.models.user import User
from social_platform.app.schemas.notification import (
    NotificationListResponse,
    NotificationResponse,
    NotificationSummaryResponse,
    NotificationUnreadCountResponse,
)
from social_platform.app.services import notification_service
from social_platform.app.services import repost_service
from social_platform.app.services.notification_events import (
    get_notification_version,
    wait_for_notification_update,
)

router = APIRouter()


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
    return NotificationListResponse(
        items=items,
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
async def stream_notification_events(token: str = Query(...), db: Session = Depends(get_db)):
    """通知 SSE 入口，query token 同样要校验 active user session。

    EventSource 无法稳定附带 Authorization header，因此前端通过 query 传 access token；
    这里仍复用 get_access_payload，保证 session 撤销后 SSE 也无法继续建立。
    """
    try:
        payload = get_access_payload(token, db, "user")
        user_id = int(payload["sub"])
    except (ValueError, TypeError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )

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
        yield _sse_event("notifications.changed", build_payload("connected"))

        while True:
            next_version = await asyncio.to_thread(
                wait_for_notification_update,
                user_id,
                version,
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
    return notification


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


def _serialize_user(user):
    if not user:
        return None
    return {
        "id": user.id,
        "username": user.username,
        "bio": user.bio,
        "avatar_url": user.avatar_url,
        "is_ai_agent": user.is_ai_agent,
        "ai_config_id": user.ai_config_id,
        "created_at": user.created_at,
        "following_count": user.following_count,
        "followers_count": user.followers_count,
    }


def _serialize_post(db: Session, post, current_user_id: int):
    if not post:
        return None
    is_liked = db.query(Like).filter(
        Like.user_id == current_user_id,
        Like.post_id == post.id,
    ).first() is not None
    return {
        "id": post.id,
        "author_id": post.author_id,
        "author": _serialize_user(post.author),
        "title": post.title,
        "type": getattr(post, "type", "post"),
        "content": post.content,
        "created_at": post.created_at,
        "like_count": post.like_count,
        "comment_count": post.comment_count,
        "is_liked": is_liked,
        "is_liked_by_current_user": is_liked,
        "repost_count": getattr(post, "repost_count", 0),
        "repost_source_type": getattr(post, "repost_source_type", None),
        "repost_source_id": getattr(post, "repost_source_id", None),
        "repost_root_post_id": getattr(post, "repost_root_post_id", None),
        "repost_chain": getattr(post, "repost_chain", None),
        "repost_chain_authors": repost_service.build_repost_chain_authors(
            object_session(post),
            post.content,
        ) if object_session(post) else [],
        "repost_origin": _serialize_post(db, post.repost_root_post, current_user_id)
        if getattr(post, "repost_root_post_id", None) and getattr(post, "repost_root_post", None)
        else None,
    }


def _serialize_comment(db: Session, comment, current_user_id: int):
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
        "like_count": comment.like_count,
        "reply_count": comment.reply_count,
        "is_liked": is_liked,
    }


def _sse_event(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"
