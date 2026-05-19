"""Management Backend - 认证路由"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session

from agents.management.backend.core.database import get_db
from agents.management.backend.schemas import LoginRequest, LoginResponse, AdminUserResponse
from agents.management.backend.models.admin_user import AdminUser
from agents.management.backend.services.auth_service import (
    authenticate_admin,
    admin_to_response,
    create_admin_token,
    update_last_login,
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
    db.refresh(admin)
    token = create_admin_token(admin.id, admin.username)

    return LoginResponse(access_token=token, admin=admin_to_response(admin))


@router.post("/logout")
def logout(current_admin: AdminUser = Depends(get_current_admin)):
    """管理员登出（客户端删除 Token 即可）"""
    return {"message": "登出成功"}


@router.get("/me", response_model=AdminUserResponse)
def get_me(current_admin: AdminUser = Depends(get_current_admin)):
    """获取当前管理员信息"""
    return admin_to_response(current_admin)
