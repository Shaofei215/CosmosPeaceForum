"""身份安全领域持久化模型。

本模块拥有服务端会话和邮箱验证码两类安全事实：会话用于支持 access token
即时撤销与 refresh token 轮换，邮箱验证码用于注册、登录和密码重置验证。
"""

from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import relationship

from social_platform.app.db.session import Base


class UserSession(Base):
    """公开平台账号会话，保存可撤销 session 与 refresh token 哈希。"""

    __tablename__ = "user_sessions"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String(64), unique=True, nullable=False, index=True)
    account_id = Column(Integer, nullable=False, index=True)
    scope = Column(String(32), nullable=False, index=True)
    client_type = Column(String(32), nullable=False, index=True)
    refresh_token_hash = Column(String(64), nullable=False, unique=True, index=True)
    revoked_at = Column(DateTime, nullable=True, index=True)
    expires_at = Column(DateTime, nullable=False, index=True)
    last_seen_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    user_agent = Column(Text, nullable=True)
    ip_address = Column(String(64), nullable=True)
    remember_me = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


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

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    email = Column(String(255), nullable=False, index=True)
    code = Column(String(6), nullable=False, index=True)
    purpose = Column(String(20), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=False)
    used = Column(Boolean, default=False, nullable=False)
    used_at = Column(DateTime, nullable=True)
    attempt_count = Column(Integer, default=0, nullable=False)

    user = relationship("User", back_populates="email_codes")

    def is_expired(self) -> bool:
        """判断验证码是否已经超过有效期。

        Returns:
            bool: 已过期返回 True，否则返回 False。
        """

        return datetime.utcnow() > self.expires_at

    def can_attempt(self, max_attempts: int = 5) -> bool:
        """判断验证码是否仍可继续尝试。

        Args:
            max_attempts: 允许的最大错误尝试次数。

        Returns:
            bool: 未超过尝试次数返回 True，否则返回 False。
        """

        return self.attempt_count < max_attempts
