"""注册邀请码持久化模型。

本模块记录邮箱绑定的邀请码，以及邀请码被注册用户消费后的审计信息。
"""

from datetime import datetime
from social_platform.app.core.timezone import local_now

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from social_platform.app.db.session import Base


class RegistrationInvitation(Base):
    """注册邀请码记录。

    每条记录绑定一个邮箱，邀请码在管理端生成，在公开平台注册成功后写入使用人。
    """

    __tablename__ = "registration_invitations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    prefix: Mapped[str] = mapped_column(String(16), default="", nullable=False)
    code_suffix: Mapped[str] = mapped_column(String(6), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=local_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=local_now, nullable=False)
    created_by_admin_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("platform_admin_users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    used_by_user_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        unique=True,
        nullable=True,
        index=True,
    )
    used_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    created_by_admin = relationship("PlatformAdminUser", foreign_keys=[created_by_admin_id])
    used_by_user = relationship("User", foreign_keys=[used_by_user_id])

