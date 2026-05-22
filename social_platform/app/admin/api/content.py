from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from social_platform.app.admin.api.deps import require_permission
from social_platform.app.admin.models.admin_user import PlatformAdminUser
from social_platform.app.admin.schemas import ContentDeleteRequest, ContentItemResponse, PaginatedResponse
from social_platform.app.admin.services.moderation_service import (
    ContentType,
    delete_comment_as_admin,
    delete_post_as_admin,
    list_content,
)
from social_platform.app.admin.services.permissions import PERMISSION_MANAGE_CONTENT
from social_platform.app.api.deps import get_db

router = APIRouter(prefix="/content", tags=["platform-admin-content"])


@router.get("/", response_model=PaginatedResponse[ContentItemResponse])
async def content(
    content_type: ContentType | None = Query(default=None, alias="type"),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    keyword: str | None = Query(default=None),
    db: Session = Depends(get_db),
    _: PlatformAdminUser = Depends(require_permission(PERMISSION_MANAGE_CONTENT)),
):
    items, total = list_content(db, content_type=content_type, skip=skip, limit=limit, keyword=keyword)
    return PaginatedResponse(items=items, total=total, skip=skip, limit=limit)


@router.delete("/posts/{post_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_post(
    post_id: int,
    request: ContentDeleteRequest | None = None,
    db: Session = Depends(get_db),
    current_admin: PlatformAdminUser = Depends(require_permission(PERMISSION_MANAGE_CONTENT)),
):
    payload = request or ContentDeleteRequest()
    try:
        delete_post_as_admin(
            db,
            post_id=post_id,
            admin=current_admin,
            reason=payload.reason,
            notify_author=payload.notify_author,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return None


@router.delete("/comments/{comment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_comment(
    comment_id: int,
    request: ContentDeleteRequest | None = None,
    db: Session = Depends(get_db),
    current_admin: PlatformAdminUser = Depends(require_permission(PERMISSION_MANAGE_CONTENT)),
):
    payload = request or ContentDeleteRequest()
    try:
        delete_comment_as_admin(
            db,
            comment_id=comment_id,
            admin=current_admin,
            reason=payload.reason,
            notify_author=payload.notify_author,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return None

