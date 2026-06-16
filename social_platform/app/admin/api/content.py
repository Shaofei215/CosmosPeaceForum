from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from social_platform.app.admin.api.deps import require_permission
from social_platform.app.admin.models.admin_user import PlatformAdminUser
from social_platform.app.admin.schemas import (
    ContentDeleteRequest,
    ContentItemResponse,
    ContentModerationLLMPromptConfigResponse,
    ContentModerationLLMPromptConfigUpdateRequest,
    ContentModerationLLMSettingsResponse,
    ContentModerationLLMSettingsUpdateRequest,
    PaginatedResponse,
    ReportedContentItemResponse,
)
from social_platform.app.admin.services.permissions import PERMISSION_MANAGE_CONTENT
from social_platform.app.api.deps import get_db
from social_platform.app.domains.content_safety import llm_moderation as content_moderation_llm_service
from social_platform.app.domains.content_safety.admin_application import (
    ContentType,
    delete_comment_as_admin,
    delete_post_as_admin,
    delete_reported_comment_as_admin,
    delete_reported_post_as_admin,
    list_content,
    list_reported_content,
    release_reported_content,
)

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


@router.get("/report-moderation/settings", response_model=ContentModerationLLMSettingsResponse)
async def get_report_moderation_settings(
    db: Session = Depends(get_db),
    _: PlatformAdminUser = Depends(require_permission(PERMISSION_MANAGE_CONTENT)),
):
    settings = content_moderation_llm_service.get_content_moderation_llm_settings(db)
    return content_moderation_llm_service.serialize_settings(settings)


@router.put("/report-moderation/settings", response_model=ContentModerationLLMSettingsResponse)
async def update_report_moderation_settings(
    request: ContentModerationLLMSettingsUpdateRequest,
    db: Session = Depends(get_db),
    _: PlatformAdminUser = Depends(require_permission(PERMISSION_MANAGE_CONTENT)),
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
async def get_report_moderation_prompt(
    db: Session = Depends(get_db),
    _: PlatformAdminUser = Depends(require_permission(PERMISSION_MANAGE_CONTENT)),
):
    settings = content_moderation_llm_service.get_content_moderation_llm_settings(db)
    return content_moderation_llm_service.serialize_prompt_config(settings)


@router.put("/report-moderation/prompt", response_model=ContentModerationLLMPromptConfigResponse)
async def update_report_moderation_prompt(
    request: ContentModerationLLMPromptConfigUpdateRequest,
    db: Session = Depends(get_db),
    _: PlatformAdminUser = Depends(require_permission(PERMISSION_MANAGE_CONTENT)),
):
    try:
        settings = content_moderation_llm_service.update_prompt_template(db, request.value)
        return content_moderation_llm_service.serialize_prompt_config(settings)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/report-moderation/prompt/reset", response_model=ContentModerationLLMPromptConfigResponse)
async def reset_report_moderation_prompt(
    db: Session = Depends(get_db),
    _: PlatformAdminUser = Depends(require_permission(PERMISSION_MANAGE_CONTENT)),
):
    settings = content_moderation_llm_service.reset_prompt_template(db)
    return content_moderation_llm_service.serialize_prompt_config(settings)


@router.get("/reports", response_model=PaginatedResponse[ReportedContentItemResponse])
async def reported_content(
    content_type: ContentType | None = Query(default=None, alias="type"),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    keyword: str | None = Query(default=None),
    db: Session = Depends(get_db),
    _: PlatformAdminUser = Depends(require_permission(PERMISSION_MANAGE_CONTENT)),
):
    items, total = list_reported_content(
        db,
        content_type=content_type,
        skip=skip,
        limit=limit,
        keyword=keyword,
    )
    return PaginatedResponse(items=items, total=total, skip=skip, limit=limit)


@router.post("/reports/{content_type}/{content_id}/release")
async def release_report(
    content_type: ContentType,
    content_id: int,
    db: Session = Depends(get_db),
    current_admin: PlatformAdminUser = Depends(require_permission(PERMISSION_MANAGE_CONTENT)),
):
    try:
        released_count = release_reported_content(db, content_type, content_id, current_admin)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return {"released_count": released_count}


@router.delete("/reports/{content_type}/{content_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_reported_content(
    content_type: ContentType,
    content_id: int,
    request: ContentDeleteRequest | None = None,
    db: Session = Depends(get_db),
    current_admin: PlatformAdminUser = Depends(require_permission(PERMISSION_MANAGE_CONTENT)),
):
    payload = request or ContentDeleteRequest()
    try:
        if content_type == "comment":
            delete_reported_comment_as_admin(
                db,
                comment_id=content_id,
                admin=current_admin,
                reason=payload.reason,
                notify_author=payload.notify_author,
            )
        else:
            delete_reported_post_as_admin(
                db,
                post_id=content_id,
                admin=current_admin,
                reason=payload.reason,
                notify_author=payload.notify_author,
            )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return None


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
