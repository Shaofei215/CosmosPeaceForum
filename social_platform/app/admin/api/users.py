from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from social_platform.app.admin.api.deps import require_permission
from social_platform.app.admin.models.admin_user import PlatformAdminUser
from social_platform.app.admin.schemas import (
    PaginatedResponse,
    UserModerationBatchUpdateRequest,
    UserModerationBatchUpdateResponse,
    UserModerationResponse,
    UserModerationUpdateRequest,
    UserWithModerationResponse,
)
from social_platform.app.admin.services.moderation_service import (
    list_users,
    moderation_to_status,
    update_user_moderation,
    update_users_moderation,
)
from social_platform.app.admin.services.permissions import PERMISSION_MANAGE_USERS
from social_platform.app.api.deps import get_db

router = APIRouter(prefix="/users", tags=["platform-admin-users"])


@router.get("/", response_model=PaginatedResponse[UserWithModerationResponse])
async def users(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    keyword: str | None = Query(default=None),
    db: Session = Depends(get_db),
    _: PlatformAdminUser = Depends(require_permission(PERMISSION_MANAGE_USERS)),
):
    items, total = list_users(db, skip=skip, limit=limit, keyword=keyword)
    return PaginatedResponse(items=items, total=total, skip=skip, limit=limit)


@router.put("/moderation/batch", response_model=UserModerationBatchUpdateResponse)
async def update_moderation_batch(
    request: UserModerationBatchUpdateRequest,
    db: Session = Depends(get_db),
    current_admin: PlatformAdminUser = Depends(require_permission(PERMISSION_MANAGE_USERS)),
):
    try:
        return update_users_moderation(db, request, current_admin)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.put("/{user_id}/moderation", response_model=UserModerationResponse)
async def update_moderation(
    user_id: int,
    request: UserModerationUpdateRequest,
    db: Session = Depends(get_db),
    current_admin: PlatformAdminUser = Depends(require_permission(PERMISSION_MANAGE_USERS)),
):
    try:
        moderation = update_user_moderation(db, user_id, request, current_admin)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    status_data = moderation_to_status(moderation)
    return UserModerationResponse(user_id=user_id, **status_data.model_dump())
