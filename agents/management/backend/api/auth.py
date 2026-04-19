"""
Management Backend - 认证路由
"""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session

from agents.management.backend.core.database import get_db
from agents.management.backend.core.security import get_password_hash
from agents.management.backend.schemas import LoginRequest, LoginResponse, AdminUserResponse, UpdateProfileRequest
from agents.management.backend.models.admin_user import AdminUser
from agents.management.backend.services.auth_service import (
    authenticate_admin,
    create_admin_token,
    update_last_login,
    update_admin_profile,
)
from agents.management.backend.api.deps import get_current_admin

router = APIRouter()


@router.post("/login", response_model=LoginResponse)
def login(request: LoginRequest, db: Session = Depends(get_db)):
    """管理员登录"""
    admin = authenticate_admin(db, request.username, request.password)
    if not admin:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
        )

    update_last_login(db, admin.id)
    token = create_admin_token(admin.id, admin.username)

    return LoginResponse(access_token=token)


@router.post("/logout")
def logout(current_admin: AdminUser = Depends(get_current_admin)):
    """管理员登出（客户端删除 Token 即可）"""
    return {"message": "登出成功"}


@router.get("/me", response_model=AdminUserResponse)
def get_me(current_admin: AdminUser = Depends(get_current_admin)):
    """获取当前管理员信息"""
    return AdminUserResponse(
        id=current_admin.id,
        username=current_admin.username,
        created_at=current_admin.created_at,
        last_login=current_admin.last_login,
    )


@router.put("/profile", response_model=AdminUserResponse)
def update_profile(
    request: UpdateProfileRequest,
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin),
):
    """修改管理员用户名/密码"""
    try:
        admin = update_admin_profile(db, current_admin, request)
        return AdminUserResponse(
            id=admin.id,
            username=admin.username,
            created_at=admin.created_at,
            last_login=admin.last_login,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
