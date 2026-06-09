"""Management Backend - API 依赖注入"""

from collections.abc import Callable
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlmodel import Session

from agents.management.backend.core.database import get_db
from agents.management.backend.core.security import decode_access_token
from agents.management.backend.models.admin_user import AdminUser
from agents.management.backend.services import auth_service, session_service
from agents.management.backend.services.permissions import ALL_PERMISSIONS
from agents.management.backend.services.log_service import create_log

security = HTTPBearer()


def _unauthorized(detail: str = "无效的认证凭证") -> HTTPException:
    """构造统一的 management Bearer 认证失败响应。"""
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_management_access_payload(token: str, db: Session) -> dict:
    """验证 management admin access token 与服务端 admin session 是否同时有效。

    管理端 access token 必须携带 typ=access、scope=management_admin 和 sid；
    sid 回查 admin_sessions 后仍 active，才允许继续访问管理 API。
    """
    payload = decode_access_token(token)
    if payload is None or payload.get("typ") != "access" or payload.get("scope") != "management_admin":
        raise _unauthorized()

    session_id = payload.get("sid")
    if not session_id:
        raise _unauthorized()

    session = session_service.get_active_session(db, session_id)
    if session is None:
        raise _unauthorized("会话已失效，请重新登录")

    try:
        admin_id = int(payload.get("sub"))
    except (TypeError, ValueError):
        raise _unauthorized()

    if session.admin_id != admin_id:
        raise _unauthorized()

    return payload


def get_current_admin(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
) -> AdminUser:
    """获取当前认证管理员；会话撤销后旧 access token 也会失效。"""
    payload = get_management_access_payload(credentials.credentials, db)

    admin: Optional[AdminUser] = None
    try:
        admin_id = int(payload.get("sub"))
        admin = auth_service.get_admin_by_id(db, admin_id)
    except (TypeError, ValueError):
        admin = None

    if admin is None or not admin.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="管理员不存在或已停用",
        )

    return admin


def require_permission(permission: str) -> Callable:
    """生成权限检查依赖，沿用 management 管理端现有权限模型。"""

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
