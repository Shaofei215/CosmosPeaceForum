from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
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
from social_platform.app.admin.services.permissions import PERMISSION_MANAGE_ADMINS
from social_platform.app.api.deps import get_db
from social_platform.app.core.security import get_password_hash

router = APIRouter(prefix="/admins", tags=["platform-admin-admins"])


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
    db.add(admin)
    db.flush()
    create_operation_log(db, current_admin, "create_admin", "admin", admin.id)
    db.commit()
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
    if request.permissions is not None:
        admin.permissions = auth_service.dump_permissions(request.permissions)
    if "email" in request.model_fields_set:
        admin.email = str(request.email).lower() if request.email else None
    if request.is_active is not None:
        if admin.id == current_admin.id and not request.is_active:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="不能停用当前账号")
        admin.is_active = request.is_active
    if request.is_super_admin is not None:
        admin.is_super_admin = request.is_super_admin
    if request.new_password:
        admin.password_hash = get_password_hash(request.new_password)
    admin.updated_at = datetime.utcnow()
    create_operation_log(db, current_admin, "update_admin", "admin", admin_id)
    db.commit()
    db.refresh(admin)
    return auth_service.admin_to_response(admin)
