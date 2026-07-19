from datetime import datetime
from social_platform.app.core.timezone import local_now

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from social_platform.app.admin.api.deps import require_permission
from social_platform.app.admin.models.admin_user import PlatformAdminUser
from social_platform.app.admin.schemas import (
    AdminCreateRequest,
    AdminResponse,
    AdminUpdateRequest,
    PaginatedResponse,
)
from social_platform.app.admin.services import auth_service
from social_platform.app.admin.services.log_service import create_operation_log
from social_platform.app.admin.services.permissions import (
    PERMISSION_MANAGE_ADMINS,
    normalize_permissions,
)
from social_platform.app.api.deps import get_db
from social_platform.app.core.security import get_password_hash

router = APIRouter(prefix="/admins", tags=["platform-admin-admins"])


def _ensure_super_admin_boundary(
    current_admin: PlatformAdminUser,
    *,
    target_admin: PlatformAdminUser | None = None,
    requested_super_admin: bool | None = None,
) -> None:
    """阻止非超级管理员创建、提升或修改超级管理员。"""

    if current_admin.is_super_admin:
        return
    if (target_admin is not None and target_admin.is_super_admin) or requested_super_admin is True:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="只有超级管理员可以创建或管理超级管理员",
        )


def _ensure_permission_delegation(
    current_admin: PlatformAdminUser,
    requested_permissions: list[str],
    *,
    existing_permissions: list[str] | None = None,
) -> None:
    """限制非超级管理员只能变更自己已经拥有的权限。"""

    if current_admin.is_super_admin:
        return
    operator_permissions = set(auth_service.parse_permissions(current_admin.permissions))
    requested = set(normalize_permissions(requested_permissions))
    existing = set(normalize_permissions(existing_permissions))
    if (requested ^ existing) - operator_permissions:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="不能授予或撤销当前账号不具备的权限",
        )


@router.get("/", response_model=PaginatedResponse[AdminResponse])
async def list_admins(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    _: PlatformAdminUser = Depends(require_permission(PERMISSION_MANAGE_ADMINS)),
):
    query = db.query(PlatformAdminUser)
    total = query.count()
    items = query.order_by(PlatformAdminUser.created_at.desc()).offset(skip).limit(limit).all()
    return PaginatedResponse(
        items=[auth_service.admin_to_response(item) for item in items],
        total=total,
        skip=skip,
        limit=limit,
    )


@router.post("/", response_model=AdminResponse, status_code=status.HTTP_201_CREATED)
async def create_admin(
    request: AdminCreateRequest,
    db: Session = Depends(get_db),
    current_admin: PlatformAdminUser = Depends(require_permission(PERMISSION_MANAGE_ADMINS)),
):
    _ensure_super_admin_boundary(
        current_admin,
        requested_super_admin=request.is_super_admin,
    )
    _ensure_permission_delegation(current_admin, request.permissions)
    if auth_service.get_admin_by_username(db, request.username):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="用户名已存在")
    admin = PlatformAdminUser(
        username=request.username,
        email=str(request.email).lower() if request.email else None,
        password_hash=get_password_hash(request.password),
        permissions=auth_service.dump_permissions(request.permissions),
        is_active=request.is_active,
        is_super_admin=request.is_super_admin,
        must_change_credentials=False,
    )
    try:
        db.add(admin)
        db.flush()
        create_operation_log(db, current_admin, "create_admin", "admin", admin.id)
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="用户名已存在",
        ) from exc
    db.refresh(admin)
    return auth_service.admin_to_response(admin)


@router.put("/{admin_id}", response_model=AdminResponse)
async def update_admin(
    admin_id: int,
    request: AdminUpdateRequest,
    db: Session = Depends(get_db),
    current_admin: PlatformAdminUser = Depends(require_permission(PERMISSION_MANAGE_ADMINS)),
):
    admin = db.query(PlatformAdminUser).filter(PlatformAdminUser.id == admin_id).first()
    if not admin:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="管理员不存在")
    _ensure_super_admin_boundary(
        current_admin,
        target_admin=admin,
        requested_super_admin=request.is_super_admin,
    )
    if request.permissions is not None:
        _ensure_permission_delegation(
            current_admin,
            request.permissions,
            existing_permissions=auth_service.parse_permissions(admin.permissions),
        )
        admin.permissions = auth_service.dump_permissions(request.permissions)
    if "email" in request.model_fields_set:
        admin.email = str(request.email).lower() if request.email else None
    if request.is_active is not None:
        if admin.id == current_admin.id and not request.is_active:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="不能停用当前账号")
        admin.is_active = request.is_active
    if request.is_super_admin is not None:
        if admin.id == current_admin.id and not request.is_super_admin:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="不能取消自己的超级管理员权限",
            )
        admin.is_super_admin = request.is_super_admin
    admin.updated_at = local_now()
    create_operation_log(db, current_admin, "update_admin", "admin", admin_id)
    db.commit()
    db.refresh(admin)
    return auth_service.admin_to_response(admin)
