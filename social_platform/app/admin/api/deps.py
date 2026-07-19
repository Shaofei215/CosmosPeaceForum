from collections.abc import Callable
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from social_platform.app.admin.models.admin_user import PlatformAdminUser
from social_platform.app.admin.services import auth_service
from social_platform.app.admin.services.permissions import ALL_PERMISSIONS
from social_platform.app.api.deps import get_access_payload, get_db


admin_security = HTTPBearer()


def get_current_admin(
    credentials: HTTPAuthorizationCredentials = Depends(admin_security),
    db: Session = Depends(get_db),
) -> PlatformAdminUser:
    """获取平台内管理员；要求 access token 绑定 active platform_admin session。"""
    try:
        payload = get_access_payload(credentials.credentials, db, "platform_admin")
        admin_id = int(payload["sub"])
    except (TypeError, ValueError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="无效的管理员认证凭证")

    admin = auth_service.get_admin_by_id(db, admin_id)
    if admin is None or not admin.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="管理员不存在或已停用")
    return admin


def require_admin_ready(admin: PlatformAdminUser = Depends(get_current_admin)) -> PlatformAdminUser:
    """阻止尚未完成初始凭据修改的管理员访问正式管理能力。"""
    if admin.must_change_credentials:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="首次登录必须修改用户名和密码")
    return admin


def require_permission(permission: str) -> Callable:
    """生成平台内管理员权限检查依赖。"""

    def _require(admin: PlatformAdminUser = Depends(require_admin_ready)) -> PlatformAdminUser:
        permissions = (
            ALL_PERMISSIONS
            if admin.is_super_admin
            else auth_service.parse_permissions(admin.permissions)
        )
        if permission not in permissions:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="缺少管理员权限")
        return admin

    return _require
