from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from social_platform.app.admin.api.deps import require_permission
from social_platform.app.admin.models.admin_user import PlatformAdminUser
from social_platform.app.admin.schemas import (
    ContentDeleteRequest,
    ContentModerationLLMPromptConfigResponse,
    ContentModerationLLMPromptConfigUpdateRequest,
    ContentModerationLLMSettingsResponse,
    ContentModerationLLMSettingsUpdateRequest,
    PaginatedResponse,
    ReportedUserItemResponse,
    UserModerationBatchUpdateRequest,
    UserModerationBatchUpdateResponse,
    UserModerationResponse,
    UserModerationUpdateRequest,
    UserWithModerationResponse,
)
from social_platform.app.admin.services.moderation_service import (
    list_moderated_users,
    list_users,
    moderation_to_status,
    update_user_moderation,
    update_users_moderation,
)
from social_platform.app.admin.services.permissions import PERMISSION_MANAGE_USERS
from social_platform.app.api.deps import get_db
from social_platform.app.domains.content_safety import llm_moderation as content_moderation_llm_service
from social_platform.app.domains.content_safety.admin_application import (
    ban_reported_user_as_admin,
    list_reported_users,
    moderate_reported_user_as_admin,
    release_reported_user,
)

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


@router.get("/report-moderation/settings", response_model=ContentModerationLLMSettingsResponse)
async def get_user_report_moderation_settings(
    db: Session = Depends(get_db),
    _: PlatformAdminUser = Depends(require_permission(PERMISSION_MANAGE_USERS)),
):
    settings = content_moderation_llm_service.get_content_moderation_llm_settings(db)
    return content_moderation_llm_service.serialize_settings(settings)


@router.put("/report-moderation/settings", response_model=ContentModerationLLMSettingsResponse)
async def update_user_report_moderation_settings(
    request: ContentModerationLLMSettingsUpdateRequest,
    db: Session = Depends(get_db),
    _: PlatformAdminUser = Depends(require_permission(PERMISSION_MANAGE_USERS)),
):
    try:
        settings = content_moderation_llm_service.update_content_moderation_llm_settings(
            db,
            request.model_dump(exclude_unset=True),
        )
        return content_moderation_llm_service.serialize_settings(settings)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/report-moderation/prompt", response_model=ContentModerationLLMPromptConfigResponse)
async def get_user_report_moderation_prompt(
    db: Session = Depends(get_db),
    _: PlatformAdminUser = Depends(require_permission(PERMISSION_MANAGE_USERS)),
):
    settings = content_moderation_llm_service.get_content_moderation_llm_settings(db)
    return content_moderation_llm_service.serialize_prompt_config(settings)


@router.put("/report-moderation/prompt", response_model=ContentModerationLLMPromptConfigResponse)
async def update_user_report_moderation_prompt(
    request: ContentModerationLLMPromptConfigUpdateRequest,
    db: Session = Depends(get_db),
    _: PlatformAdminUser = Depends(require_permission(PERMISSION_MANAGE_USERS)),
):
    try:
        settings = content_moderation_llm_service.update_prompt_template(db, request.value)
        return content_moderation_llm_service.serialize_prompt_config(settings)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/report-moderation/prompt/reset", response_model=ContentModerationLLMPromptConfigResponse)
async def reset_user_report_moderation_prompt(
    db: Session = Depends(get_db),
    _: PlatformAdminUser = Depends(require_permission(PERMISSION_MANAGE_USERS)),
):
    settings = content_moderation_llm_service.reset_prompt_template(db)
    return content_moderation_llm_service.serialize_prompt_config(settings)


@router.get("/reports", response_model=PaginatedResponse[ReportedUserItemResponse])
async def reported_users(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    keyword: str | None = Query(default=None),
    db: Session = Depends(get_db),
    _: PlatformAdminUser = Depends(require_permission(PERMISSION_MANAGE_USERS)),
):
    items, total = list_reported_users(db, skip=skip, limit=limit, keyword=keyword)
    return PaginatedResponse(items=items, total=total, skip=skip, limit=limit)


@router.get("/moderated", response_model=PaginatedResponse[UserWithModerationResponse])
async def moderated_users(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    keyword: str | None = Query(default=None),
    db: Session = Depends(get_db),
    _: PlatformAdminUser = Depends(require_permission(PERMISSION_MANAGE_USERS)),
):
    items, total = list_moderated_users(db, skip=skip, limit=limit, keyword=keyword)
    return PaginatedResponse(items=items, total=total, skip=skip, limit=limit)


@router.post("/reports/{user_id}/release")
async def release_user_report(
    user_id: int,
    db: Session = Depends(get_db),
    current_admin: PlatformAdminUser = Depends(require_permission(PERMISSION_MANAGE_USERS)),
):
    try:
        released_count = release_reported_user(db, user_id, current_admin)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return {"released_count": released_count}


@router.delete("/reports/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def ban_reported_user(
    user_id: int,
    request: ContentDeleteRequest | None = None,
    db: Session = Depends(get_db),
    current_admin: PlatformAdminUser = Depends(require_permission(PERMISSION_MANAGE_USERS)),
):
    payload = request or ContentDeleteRequest()
    try:
        ban_reported_user_as_admin(
            db,
            user_id=user_id,
            admin=current_admin,
            reason=payload.reason,
            notify_user=payload.notify_author,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return None


@router.put("/reports/{user_id}/moderation", response_model=UserModerationResponse)
async def moderate_reported_user(
    user_id: int,
    request: UserModerationUpdateRequest,
    db: Session = Depends(get_db),
    current_admin: PlatformAdminUser = Depends(require_permission(PERMISSION_MANAGE_USERS)),
):
    try:
        moderation = moderate_reported_user_as_admin(db, user_id, request, current_admin)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    status_data = moderation_to_status(moderation)
    return UserModerationResponse(user_id=user_id, **status_data.model_dump())


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
