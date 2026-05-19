"""
Management Backend - 认证服务
"""

import json
from datetime import datetime
from typing import Optional

from sqlmodel import Session, select

from agents.management.backend.models.admin_user import AdminUser
from agents.management.backend.core.security import verify_password, get_password_hash, create_access_token
from agents.management.backend.core.config import get_config
from agents.management.backend.schemas import AdminUserResponse
from agents.management.backend.services.permissions import ALL_PERMISSIONS, normalize_permissions


def parse_permissions(raw_permissions: str | None) -> list[str]:
    try:
        value = json.loads(raw_permissions or "[]")
    except json.JSONDecodeError:
        return []
    if not isinstance(value, list):
        return []
    return normalize_permissions([str(item) for item in value])


def dump_permissions(permissions: list[str] | None) -> str:
    return json.dumps(normalize_permissions(permissions), ensure_ascii=False)


def admin_to_response(admin: AdminUser) -> AdminUserResponse:
    permissions = ALL_PERMISSIONS if admin.is_super_admin else parse_permissions(admin.permissions)
    return AdminUserResponse(
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


def get_admin_by_username(db: Session, username: str) -> Optional[AdminUser]:
    """根据用户名获取管理员"""
    stmt = select(AdminUser).where(AdminUser.username == username)
    return db.exec(stmt).first()


def get_admin_by_id(db: Session, admin_id: int) -> Optional[AdminUser]:
    """根据 ID 获取管理员"""
    return db.get(AdminUser, admin_id)


def authenticate_admin(db: Session, username: str, password: str) -> Optional[AdminUser]:
    """验证管理员身份"""
    admin = get_admin_by_username(db, username)
    if not admin or not admin.is_active:
        return None
    if not verify_password(password, admin.password_hash):
        return None
    return admin


def create_admin_token(admin_id: int, username: str) -> str:
    """创建管理员 Token"""
    return create_access_token(
        data={"sub": str(admin_id), "username": username, "scope": "management_admin"}
    )


def update_last_login(db: Session, admin_id: int) -> None:
    """更新最后登录时间"""
    admin = db.get(AdminUser, admin_id)
    if admin:
        admin.last_login = datetime.utcnow()
        db.add(admin)
        db.commit()


def init_default_admin(db: Session) -> bool:
    """按 agents/.env 初始化首个管理员。"""
    config = get_config()
    existing = db.exec(select(AdminUser.id)).first()
    if existing is not None:
        return False

    admin = AdminUser(
        username=config.admin_username,
        password_hash=get_password_hash(config.admin_password),
        permissions=dump_permissions(ALL_PERMISSIONS),
        is_active=True,
        is_super_admin=True,
        must_change_credentials=False,
    )
    db.add(admin)
    db.commit()
    return True
