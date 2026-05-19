"""Management Backend - API 依赖注入"""

from collections.abc import Callable
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlmodel import Session

from agents.management.backend.core.database import get_db
from agents.management.backend.core.security import decode_access_token
from agents.management.backend.models.admin_user import AdminUser
from agents.management.backend.services import auth_service
from agents.management.backend.services.permissions import ALL_PERMISSIONS
from agents.management.backend.services.log_service import create_log

security = HTTPBearer()


def get_current_admin(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
) -> AdminUser:
    """获取当前认证的管理员"""
    payload = decode_access_token(credentials.credentials)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的认证凭证",
            headers={"WWW-Authenticate": "Bearer"},
        )

    scope = payload.get("scope")
    if scope not in (None, "management_admin"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的认证凭证",
        )

    admin: Optional[AdminUser] = None
    try:
        admin_id = int(payload.get("sub"))
        admin = auth_service.get_admin_by_id(db, admin_id)
    except (TypeError, ValueError):
        username: Optional[str] = payload.get("username")
        if username:
            admin = auth_service.get_admin_by_username(db, username)

    if admin is None or not admin.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="管理员不存在或已停用",
        )

    return admin


def require_permission(permission: str) -> Callable:
    def _require(admin: AdminUser = Depends(get_current_admin)) -> AdminUser:
        permissions = (
            ALL_PERMISSIONS
            if admin.is_super_admin
            else auth_service.parse_permissions(admin.permissions)
        )
        if permission not in permissions:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="缺少管理员权限")
        return admin

    return _require


def log_action(
    action: str,
    target_type: str,
    target_id: Optional[int] = None,
):
    """
    返回一个日志操作的依赖注入函数

    使用方式：
    @router.post("/agents")
    def create_agent(..., current_admin: AdminUser = Depends(get_current_admin)):
        ...
        log_fn = Depends(log_action("create_agent", "agent", agent.id))
    """
    def _log(
        db: Session = Depends(get_db),
        current_admin: AdminUser = Depends(get_current_admin),
    ):
        create_log(
            db=db,
            admin=current_admin,
            action=action,
            target_type=target_type,
            target_id=target_id,
        )
    return _log
