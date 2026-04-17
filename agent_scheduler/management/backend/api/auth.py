"""
Management Backend - 认证路由
"""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session

from agent_scheduler.management.backend.core.database import get_db
from agent_scheduler.management.backend.core.security import get_password_hash
from agent_scheduler.management.backend.schemas import LoginRequest, LoginResponse, AdminUserResponse
from agent_scheduler.management.backend.models.admin_user import AdminUser
from agent_scheduler.management.backend.services.auth_service import (
    authenticate_admin,
    create_admin_token,
    update_last_login,
)
from agent_scheduler.management.backend.api.deps import get_current_admin

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
