from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from social_platform.app.admin.api.deps import require_permission
from social_platform.app.admin.models.admin_user import PlatformAdminUser
from social_platform.app.admin.schemas import (
    ContentModerationLLMPromptConfigResponse,
    ContentModerationLLMPromptConfigUpdateRequest,
    ContentModerationLLMSettingsResponse,
    ContentModerationLLMSettingsUpdateRequest,
    ModerationAppealItemResponse,
    ModerationAppealRejectRequest,
    PaginatedResponse,
    ReportedUserItemResponse,
    InvitationCodeCreateRequest,
    InvitationCodeResponse,
    UserModerationBatchUpdateResponse,
    UserModerationResponse,
    UserViolationBatchRequest,
    UserViolationRequest,
    ViolationCategory,
    UserWithModerationResponse,
    UserCoinBalanceResponse,
    UserCoinBalanceUpdateRequest,
)
from social_platform.app.admin.services.moderation_service import (
    list_moderated_users,
    list_users,
    moderation_to_status,
    apply_user_violation,
    apply_users_violation,
    release_current_user_restriction,
)
from social_platform.app.admin.services.permissions import PERMISSION_MANAGE_USERS
from social_platform.app.admin.services.log_service import create_operation_log
from social_platform.app.api.deps import get_db
from social_platform.app.domains.content_safety import llm_moderation as content_moderation_llm_service
from social_platform.app.domains.content_safety.admin_application import (
    list_reported_users,
    moderate_reported_user_as_admin,
    release_reported_user,
)
from social_platform.app.domains.content_safety.appeal_application import (
    approve_user_appeal,
    list_pending_appeals,
    reject_appeal,
)
from social_platform.app.domains.invitation import application as invitation_service
from social_platform.app.domains.coin import application as coin_service

router = APIRouter(prefix="/users", tags=["platform-admin-users"])


@router.get("/", response_model=PaginatedResponse[UserWithModerationResponse])
async def users(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    keyword: str | None = Query(default=None),
    db: Session = Depends(get_db),
    _: PlatformAdminUser = Depends(require_permission(PERMISSION_MANAGE_USERS)),
):
    items, total = list_users(db, skip=skip, limit=limit, keyword=keyword)
    return PaginatedResponse(items=items, total=total, skip=skip, limit=limit)


@router.put("/{user_id}/coin-balance", response_model=UserCoinBalanceResponse)
async def update_user_coin_balance(
    user_id: int,
    request: UserCoinBalanceUpdateRequest,
    db: Session = Depends(get_db),
    current_admin: PlatformAdminUser = Depends(require_permission(PERMISSION_MANAGE_USERS)),
) -> UserCoinBalanceResponse:
    """手动设置用户硬币余额，并写入管理员操作日志。"""

    try:
        user = coin_service.set_user_coin_balance(db, user_id, request.coin_balance)
    except coin_service.UserNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    create_operation_log(
        db,
        current_admin,
        "update_user_coin_balance",
        "user",
        user_id,
        {"coin_balance": request.coin_balance},
    )
    db.commit()
    return UserCoinBalanceResponse(user_id=user.id, coin_balance=user.coin_balance)


@router.post("/violations/batch", response_model=UserModerationBatchUpdateResponse)
async def create_violations_batch(
    request: UserViolationBatchRequest,
    db: Session = Depends(get_db),
    current_admin: PlatformAdminUser = Depends(require_permission(PERMISSION_MANAGE_USERS)),
):
    try:
        return apply_users_violation(db, request, current_admin)
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
    current_admin: PlatformAdminUser = Depends(require_permission(PERMISSION_MANAGE_USERS)),
):
    try:
        settings = content_moderation_llm_service.update_content_moderation_llm_settings(
            db,
            request.model_dump(exclude_unset=True),
        )
        create_operation_log(
            db,
            current_admin,
            "update_user_report_moderation_settings",
            "user_moderation_settings",
        )
        db.commit()
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
    current_admin: PlatformAdminUser = Depends(require_permission(PERMISSION_MANAGE_USERS)),
):
    try:
        settings = content_moderation_llm_service.update_prompt_template(db, request.value)
        create_operation_log(
            db,
            current_admin,
            "update_user_report_moderation_prompt",
            "user_moderation_settings",
        )
        db.commit()
        return content_moderation_llm_service.serialize_prompt_config(settings)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/report-moderation/prompt/reset", response_model=ContentModerationLLMPromptConfigResponse)
async def reset_user_report_moderation_prompt(
    db: Session = Depends(get_db),
    current_admin: PlatformAdminUser = Depends(require_permission(PERMISSION_MANAGE_USERS)),
):
    settings = content_moderation_llm_service.reset_prompt_template(db)
    create_operation_log(
        db,
        current_admin,
        "reset_user_report_moderation_prompt",
        "user_moderation_settings",
    )
    db.commit()
    return content_moderation_llm_service.serialize_prompt_config(settings)


@router.get("/reports", response_model=PaginatedResponse[ReportedUserItemResponse])
async def reported_users(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    keyword: str | None = Query(default=None),
    db: Session = Depends(get_db),
    _: PlatformAdminUser = Depends(require_permission(PERMISSION_MANAGE_USERS)),
):
    items, total = list_reported_users(db, skip=skip, limit=limit, keyword=keyword)
    return PaginatedResponse(items=items, total=total, skip=skip, limit=limit)


@router.get("/moderated", response_model=PaginatedResponse[UserWithModerationResponse])
async def moderated_users(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    keyword: str | None = Query(default=None),
    db: Session = Depends(get_db),
    _: PlatformAdminUser = Depends(require_permission(PERMISSION_MANAGE_USERS)),
):
    items, total = list_moderated_users(db, skip=skip, limit=limit, keyword=keyword)
    return PaginatedResponse(items=items, total=total, skip=skip, limit=limit)


@router.get("/appeals", response_model=PaginatedResponse[ModerationAppealItemResponse])
async def user_appeals(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    keyword: str | None = Query(default=None),
    db: Session = Depends(get_db),
    _: PlatformAdminUser = Depends(require_permission(PERMISSION_MANAGE_USERS)),
):
    items, total = list_pending_appeals(
        db,
        scope="user",
        skip=skip,
        limit=limit,
        keyword=keyword,
    )
    return PaginatedResponse(items=items, total=total, skip=skip, limit=limit)


@router.post("/appeals/{appeal_id}/approve", status_code=status.HTTP_204_NO_CONTENT)
async def approve_user_moderation_appeal(
    appeal_id: int,
    db: Session = Depends(get_db),
    current_admin: PlatformAdminUser = Depends(require_permission(PERMISSION_MANAGE_USERS)),
):
    try:
        approve_user_appeal(db, appeal_id, current_admin)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return None


@router.post("/appeals/{appeal_id}/reject", status_code=status.HTTP_204_NO_CONTENT)
async def reject_user_moderation_appeal(
    appeal_id: int,
    request: ModerationAppealRejectRequest,
    db: Session = Depends(get_db),
    current_admin: PlatformAdminUser = Depends(require_permission(PERMISSION_MANAGE_USERS)),
):
    try:
        reject_appeal(db, appeal_id, current_admin, request.reason)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return None


@router.get("/invitations", response_model=PaginatedResponse[InvitationCodeResponse])
async def registration_invitations(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    keyword: str | None = Query(default=None),
    db: Session = Depends(get_db),
    _: PlatformAdminUser = Depends(require_permission(PERMISSION_MANAGE_USERS)),
):
    """分页读取注册邀请码列表。"""

    items, total = invitation_service.list_registration_invitations(
        db,
        skip=skip,
        limit=limit,
        keyword=keyword,
    )
    return PaginatedResponse(items=items, total=total, skip=skip, limit=limit)


@router.post(
    "/invitations",
    response_model=InvitationCodeResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_registration_invitation(
    request: InvitationCodeCreateRequest,
    db: Session = Depends(get_db),
    current_admin: PlatformAdminUser = Depends(require_permission(PERMISSION_MANAGE_USERS)),
):
    """为指定邮箱生成注册邀请码。"""

    try:
        return invitation_service.create_registration_invitation(
            db,
            str(request.email),
            request.prefix,
            current_admin,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


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


@router.post("/reports/{user_id}/violations", response_model=UserModerationResponse)
async def create_reported_user_violation(
    user_id: int,
    request: UserViolationRequest,
    db: Session = Depends(get_db),
    current_admin: PlatformAdminUser = Depends(require_permission(PERMISSION_MANAGE_USERS)),
):
    try:
        moderation = moderate_reported_user_as_admin(db, user_id, request, current_admin)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    status_data = moderation_to_status(moderation)
    return UserModerationResponse(user_id=user_id, **status_data.model_dump())


@router.post("/{user_id}/violations", response_model=UserModerationResponse)
async def create_user_violation(
    user_id: int,
    request: UserViolationRequest,
    db: Session = Depends(get_db),
    current_admin: PlatformAdminUser = Depends(require_permission(PERMISSION_MANAGE_USERS)),
):
    try:
        moderation, _ = apply_user_violation(
            db,
            user_id,
            request.category,
            current_admin,
            request.reason,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    status_data = moderation_to_status(moderation)
    return UserModerationResponse(user_id=user_id, **status_data.model_dump())


@router.delete("/{user_id}/restrictions/{category}", response_model=UserModerationResponse)
async def release_user_restriction(
    user_id: int,
    category: ViolationCategory,
    db: Session = Depends(get_db),
    current_admin: PlatformAdminUser = Depends(require_permission(PERMISSION_MANAGE_USERS)),
):
    """主动解除用户当前单项管控，保留历史违规累计次数。"""

    try:
        moderation = release_current_user_restriction(db, user_id, category, current_admin)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    status_data = moderation_to_status(moderation)
    return UserModerationResponse(user_id=user_id, **status_data.model_dump())
