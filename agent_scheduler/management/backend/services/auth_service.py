"""
Management Backend - 认证服务
"""

from datetime import datetime
from typing import Optional

from sqlmodel import Session, select

from agent_scheduler.management.backend.models.admin_user import AdminUser
from agent_scheduler.management.backend.core.security import verify_password, get_password_hash, create_access_token
from agent_scheduler.management.backend.core.config import get_config


def get_admin_by_username(db: Session, username: str) -> Optional[AdminUser]:
    """根据用户名获取管理员"""
    stmt = select(AdminUser).where(AdminUser.username == username)
    return db.exec(stmt).first()


def authenticate_admin(db: Session, username: str, password: str) -> Optional[AdminUser]:
    """验证管理员身份"""
    admin = get_admin_by_username(db, username)
    if not admin:
        return None
    if not verify_password(password, admin.password_hash):
        return None
    return admin


def create_admin_token(admin_id: int, username: str) -> str:
    """创建管理员 Token"""
    return create_access_token(data={"sub": str(admin_id), "username": username})


def update_last_login(db: Session, admin_id: int) -> None:
    """更新最后登录时间"""
    admin = db.get(AdminUser, admin_id)
    if admin:
        admin.last_login = datetime.utcnow()
        db.add(admin)
        db.commit()


def init_default_admin(db: Session) -> bool:
    """初始化默认管理员账号"""
    config = get_config()
    existing = get_admin_by_username(db, config.admin_username)
    if existing:
        return False

    admin = AdminUser(
        username=config.admin_username,
        password_hash=get_password_hash(config.admin_password),
    )
    db.add(admin)
    db.commit()
    return True
