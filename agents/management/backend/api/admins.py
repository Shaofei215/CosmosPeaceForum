"""Management Backend - 管理员管理路由"""

from datetime import datetime
from agents.management.backend.core.timezone import local_now

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlmodel import Session, select

from agents.management.backend.api.deps import require_permission
from agents.management.backend.core.database import get_db
from agents.management.backend.core.security import get_password_hash
from agents.management.backend.models.admin_user import AdminUser
from agents.management.backend.schemas import (
    AdminCreateRequest,
    AdminListResponse,
    AdminUpdateRequest,
    AdminUserResponse,
)
from agents.management.backend.services import auth_service
from agents.management.backend.services.log_service import create_log
from agents.management.backend.services.permissions import PERMISSION_MANAGE_ADMINS

router = APIRouter()


@router.get("/", response_model=AdminListResponse)
def list_admins(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    _: AdminUser = Depends(require_permission(PERMISSION_MANAGE_ADMINS)),
):
    stmt = select(AdminUser)
    items = db.exec(
        stmt.order_by(AdminUser.created_at.desc()).offset(skip).limit(limit)
    ).all()
    total = len(db.exec(stmt).all())
    return AdminListResponse(
        items=[auth_service.admin_to_response(item) for item in items],
        total=total,
        skip=skip,
        limit=limit,
    )


@router.post("/", response_model=AdminUserResponse, status_code=status.HTTP_201_CREATED)
def create_admin(
    request: AdminCreateRequest,
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(require_permission(PERMISSION_MANAGE_ADMINS)),
):
    if auth_service.get_admin_by_username(db, request.username):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="用户名已存在")

    admin = AdminUser(
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
    create_log(
        db,
        current_admin,
        "create_admin",
        "admin",
        admin.id,
        details={"username": admin.username, "is_super_admin": admin.is_super_admin},
    )
    db.refresh(admin)
    return auth_service.admin_to_response(admin)


@router.put("/{admin_id}", response_model=AdminUserResponse)
def update_admin(
    admin_id: int,
    request: AdminUpdateRequest,
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(require_permission(PERMISSION_MANAGE_ADMINS)),
):
    admin = db.get(AdminUser, admin_id)
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
        if admin.id == current_admin.id and not request.is_super_admin:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="不能取消自己的超级管理员权限")
        admin.is_super_admin = request.is_super_admin
    admin.updated_at = local_now()
    db.add(admin)
    db.flush()
    create_log(
        db,
        current_admin,
        "update_admin",
        "admin",
        admin_id,
        details={"username": admin.username},
    )
    db.refresh(admin)
    return auth_service.admin_to_response(admin)
