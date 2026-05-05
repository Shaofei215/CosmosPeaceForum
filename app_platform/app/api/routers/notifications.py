from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app_platform.app.api.deps import get_db, get_current_user
from app_platform.app.models.user import User
from app_platform.app.schemas.notification import (
    NotificationListResponse,
    NotificationResponse,
    NotificationSummaryResponse,
    NotificationUnreadCountResponse,
)
from app_platform.app.services import notification_service

router = APIRouter()


@router.get("", response_model=NotificationListResponse)
def list_notifications(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    type: str | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
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
    current_user: User = Depends(get_current_user),
):
    return notification_service.get_summary(db, current_user.id)


@router.get("/unread-count", response_model=NotificationUnreadCountResponse)
def get_unread_count(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return NotificationUnreadCountResponse(
        unread_count=notification_service.get_unread_count(db, current_user.id)
    )


@router.get("/{notification_id}", response_model=NotificationResponse)
def get_notification(
    notification_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    notification = notification_service.get_notification(db, current_user.id, notification_id)
    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")
    return notification


@router.post("/mark-read")
def mark_notifications_read(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    updated = notification_service.mark_all_as_read(db, current_user.id)
    return {"updated_count": updated}


@router.get("/{notification_id}/origin")
def get_notification_origin(
    notification_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    notification = notification_service.get_notification(db, current_user.id, notification_id)
    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")
    origin = notification_service.get_origin(db, notification)
    return {
        "post": _serialize_post(origin.get("post")),
        "comment": _serialize_comment(origin.get("comment")),
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


def _serialize_post(post):
    if not post:
        return None
    return {
        "id": post.id,
        "author_id": post.author_id,
        "author": _serialize_user(post.author),
        "title": post.title,
        "content": post.content,
        "created_at": post.created_at,
        "like_count": post.like_count,
        "comment_count": post.comment_count,
    }


def _serialize_comment(comment):
    if not comment:
        return None
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
        "is_liked": False,
    }
