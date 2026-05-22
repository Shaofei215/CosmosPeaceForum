# 邮箱验证码数据模型
# 存储邮箱验证码相关信息，用于注册验证和密码重置
from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime

from social_platform.app.db.session import Base


class EmailVerificationCode(Base):
    """
    邮箱验证码模型

    存储邮箱验证码相关信息，用于：
    - 用户注册时的邮箱验证
    - 密码重置时的身份验证

    验证码设计为一次性使用，有效期为10分钟
    """
    __tablename__ = "email_verification_codes"

    # 记录唯一标识符
    id = Column(Integer, primary_key=True, index=True)

    # 关联用户ID
    # 注册阶段用户尚未创建，此时为 NULL
    # 密码重置时关联到已存在的用户
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=True,
        index=True
    )

    # 目标邮箱地址
    email = Column(String(255), nullable=False, index=True)

    # 6位数字验证码
    code = Column(String(6), nullable=False, index=True)

    # 验证码用途
    # - register: 用户注册
    # - reset_password: 密码重置
    purpose = Column(String(20), nullable=False)

    # 创建时间
    created_at = Column(DateTime, default=datetime.utcnow)

    # 过期时间
    expires_at = Column(DateTime, nullable=False)

    # 是否已使用
    used = Column(Boolean, default=False, nullable=False)

    # 使用时间
    used_at = Column(DateTime, nullable=True)

    # 验证尝试次数
    # 超过最大次数后验证码失效
    attempt_count = Column(Integer, default=0, nullable=False)

    # 关联关系：所属用户
    user = relationship("User", back_populates="email_codes")

    def is_expired(self) -> bool:
        """
        检查验证码是否已过期

        Returns:
            bool: 验证码已过期返回 True，否则返回 False
        """
        return datetime.utcnow() > self.expires_at

    def can_attempt(self, max_attempts: int = 5) -> bool:
        """
        检查是否还可以尝试验证

        Args:
            max_attempts: 最大尝试次数，默认5次

        Returns:
            bool: 还可以尝试返回 True，否则返回 False
        """
        return self.attempt_count < max_attempts
