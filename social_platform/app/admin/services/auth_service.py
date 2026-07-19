"""管理端认证与管理员账号服务。"""

import json
from datetime import datetime
from social_platform.app.core.timezone import local_now
from typing import Optional

from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from social_platform.app.admin.models.admin_user import PlatformAdminUser
from social_platform.app.admin.schemas import AdminResponse, AdminProfileUpdateRequest
from social_platform.app.admin.services.permissions import ALL_PERMISSIONS, normalize_permissions
from social_platform.app.core.config import get_settings
from social_platform.app.core.security import create_access_token, get_password_hash, verify_password


def parse_permissions(raw_permissions: str | None) -> list[str]:
    """解析管理员权限 JSON 字符串并过滤未知权限。"""

    try:
        value = json.loads(raw_permissions or "[]")
    except json.JSONDecodeError:
        return []
    if not isinstance(value, list):
        return []
    return normalize_permissions([str(item) for item in value])


def dump_permissions(permissions: list[str] | None) -> str:
    """把管理员权限列表序列化为稳定 JSON 字符串。"""

    return json.dumps(normalize_permissions(permissions), ensure_ascii=False)


def admin_to_response(admin: PlatformAdminUser) -> AdminResponse:
    """把管理员模型转换为管理端资料响应。"""

    permissions = ALL_PERMISSIONS if admin.is_super_admin else parse_permissions(admin.permissions)
    return AdminResponse(
        id=admin.id,
        username=admin.username,
        email=admin.email,
        permissions=permissions,
        is_active=admin.is_active,
        is_super_admin=admin.is_super_admin,
        must_change_credentials=admin.must_change_credentials,
        created_at=admin.created_at,
        updated_at=admin.updated_at,
        last_login=admin.last_login,
    )


def get_admin_by_username(db: Session, username: str) -> Optional[PlatformAdminUser]:
    """按用户名读取管理员账号。"""

    return db.query(PlatformAdminUser).filter(PlatformAdminUser.username == username).first()


def get_admin_by_id(db: Session, admin_id: int) -> Optional[PlatformAdminUser]:
    """按 ID 读取管理员账号。"""

    return db.query(PlatformAdminUser).filter(PlatformAdminUser.id == admin_id).first()


def authenticate_admin(db: Session, username: str, password: str) -> Optional[PlatformAdminUser]:
    """校验管理员用户名、密码和启用状态。"""

    admin = get_admin_by_username(db, username)
    if not admin or not admin.is_active:
        return None
    if not verify_password(password, admin.password_hash):
        return None
    return admin


def create_admin_token(admin: PlatformAdminUser) -> str:
    """为管理员创建带 platform_admin scope 的访问令牌。"""

    return create_access_token(
        data={
            "sub": str(admin.id),
            "username": admin.username,
            "scope": "platform_admin",
        }
    )


def ensure_initial_admin(db: Session) -> bool:
    """按 .env 初始化首个管理员，并强制其首次修改用户名与密码。"""
    if db.query(PlatformAdminUser.id).first() is not None:
        return False

    settings = get_settings()
    admin = PlatformAdminUser(
        username=settings.PLATFORM_ADMIN_INITIAL_USERNAME,
        password_hash=get_password_hash(settings.PLATFORM_ADMIN_INITIAL_PASSWORD),
        permissions=dump_permissions(ALL_PERMISSIONS),
        is_active=True,
        is_super_admin=True,
        must_change_credentials=True,
    )
    db.add(admin)
    db.commit()
    return True


def update_last_login(db: Session, admin: PlatformAdminUser) -> None:
    """更新管理员最近登录时间。"""

    admin.last_login = local_now()
    db.add(admin)
    db.commit()


def update_profile(
    db: Session,
    admin: PlatformAdminUser,
    request: AdminProfileUpdateRequest,
) -> PlatformAdminUser:
    """更新管理员自己的用户名或密码。"""

    if not verify_password(request.current_password, admin.password_hash):
        raise ValueError("当前密码不正确")

    if request.username and request.username != admin.username:
        existing = get_admin_by_username(db, request.username)
        if existing is not None:
            raise ValueError("用户名已存在")
        admin.username = request.username

    if request.new_password:
        admin.password_hash = get_password_hash(request.new_password)

    if request.username or request.new_password:
        admin.must_change_credentials = False
    admin.updated_at = local_now()
    db.add(admin)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise ValueError("用户名已存在") from exc
    db.refresh(admin)
    return admin
