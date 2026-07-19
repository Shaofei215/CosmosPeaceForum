from datetime import datetime
from social_platform.app.core.timezone import local_now

from sqlalchemy import Boolean, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from social_platform.app.db.session import Base


class PlatformAdminUser(Base):
    """公开平台管理员账号。"""

    __tablename__ = "platform_admin_users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    permissions: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_super_admin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    must_change_credentials: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=local_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=local_now, onupdate=local_now, nullable=False)
    last_login: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
