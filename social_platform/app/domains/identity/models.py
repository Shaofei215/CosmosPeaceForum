"""身份安全领域持久化模型。

本模块拥有服务端会话和邮箱验证码两类安全事实：会话用于支持 access token
即时撤销与 refresh token 轮换，邮箱验证码用于注册、登录和密码重置验证。
"""

from datetime import datetime
from social_platform.app.core.timezone import local_now

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from social_platform.app.db.session import Base


class UserSession(Base):
    """公开平台账号会话，保存可撤销 session 与 refresh token 哈希。"""

    __tablename__ = "user_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    session_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    account_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    scope: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    client_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    refresh_token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime, default=local_now, nullable=False)
    user_agent: Mapped[str | None] = mapped_column(Text, nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)
    remember_me: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=local_now, nullable=False)


Index(
    "ix_user_sessions_account_scope_client",
    UserSession.account_id,
    UserSession.scope,
    UserSession.client_type,
)


class EmailVerificationCode(Base):
    """邮箱验证码记录，用于注册验证、验证码登录和密码重置。

    验证码设计为一次性使用，并通过 ``attempt_count`` 控制错误尝试次数。
    """

    __tablename__ = "email_verification_codes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    code: Mapped[str] = mapped_column(String(6), nullable=False, index=True)
    purpose: Mapped[str] = mapped_column(String(20), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=local_now, nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    used: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    attempt_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    user = relationship("User", back_populates="email_codes")

    def is_expired(self) -> bool:
        """判断验证码是否已经超过有效期。

        Returns:
            bool: 已过期返回 True，否则返回 False。
        """

        return local_now() > self.expires_at

    def can_attempt(self, max_attempts: int = 5) -> bool:
        """判断验证码是否仍可继续尝试。

        Args:
            max_attempts: 允许的最大错误尝试次数。

        Returns:
            bool: 未超过尝试次数返回 True，否则返回 False。
        """

        return self.attempt_count < max_attempts
