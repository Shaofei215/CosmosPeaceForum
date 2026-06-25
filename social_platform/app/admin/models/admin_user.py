from datetime import datetime
from social_platform.app.core.timezone import local_now

from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text

from social_platform.app.db.session import Base


class PlatformAdminUser(Base):
    """公开平台管理员账号。"""

    __tablename__ = "platform_admin_users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    email = Column(String(255), nullable=True)
    password_hash = Column(String(255), nullable=False)
    permissions = Column(Text, nullable=False, default="[]")
    is_active = Column(Boolean, default=True, nullable=False)
    is_super_admin = Column(Boolean, default=False, nullable=False)
    must_change_credentials = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=local_now, nullable=False)
    updated_at = Column(DateTime, default=local_now, onupdate=local_now, nullable=False)
    last_login = Column(DateTime, nullable=True)
