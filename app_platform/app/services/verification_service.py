# 验证码业务逻辑层
# 实现邮箱验证码相关的核心业务逻辑，包括生成、验证、频率限制等
import random
import string
from datetime import datetime, timedelta
from typing import Optional, Tuple

from sqlalchemy.orm import Session
from sqlalchemy import and_, func

from app.models.email_verification import EmailVerificationCode
from app.core.config import get_settings


settings = get_settings()


class VerificationCodeFrequencyError(Exception):
    """
    自定义异常：发送频率限制

    当验证码发送过于频繁时抛出此异常
    """
    def __init__(self, wait_seconds: int):
        """
        初始化异常

        Args:
            wait_seconds: 需要等待的秒数
        """
        self.wait_seconds = wait_seconds
        super().__init__(f"发送过于频繁，请 {wait_seconds} 秒后再试")


class VerificationCodeDailyLimitError(Exception):
    """
    自定义异常：每日发送次数限制

    当验证码每日发送次数达到上限时抛出此异常
    """
    def __init__(self):
        """初始化异常"""
        super().__init__("今日发送次数已达上限，请明天再试")


class VerificationCodeNotFoundError(Exception):
    """
    自定义异常：验证码不存在

    当验证码记录不存在或已失效时抛出此异常
    """
    def __init__(self):
        """初始化异常"""
        super().__init__("验证码无效，请重新获取")


class VerificationCodeExpiredError(Exception):
    """
    自定义异常：验证码已过期

    当验证码已过期时抛出此异常
    """
    def __init__(self):
        """初始化异常"""
        super().__init__("验证码已过期，请重新获取")


class VerificationCodeAttemptsExceededError(Exception):
    """
    自定义异常：验证码尝试次数超限

    当验证码错误尝试次数超过限制时抛出此异常
    """
    def __init__(self, remaining_attempts: int):
        """
        初始化异常

        Args:
            remaining_attempts: 剩余尝试次数
        """
        self.remaining_attempts = remaining_attempts
        super().__init__(f"验证失败次数过多，请重新获取验证码")


def generate_verification_code(length: int = 6) -> str:
    """
    生成随机数字验证码

    Args:
        length: 验证码长度，默认6位

    Returns:
        str: 随机数字验证码字符串
    """
    return ''.join(random.choices(string.digits, k=length))


def check_send_frequency(
    db: Session,
    email: str,
    purpose: str
) -> None:
    """
    检查发送频率限制

    检查同一邮箱在指定时间间隔内是否已发送过同类验证码

    Args:
        db: 数据库会话
        email: 邮箱地址
        purpose: 验证码用途，用于区分注册和密码重置

    Raises:
        VerificationCodeFrequencyError: 发送过于频繁时抛出
    """
    interval = timedelta(minutes=settings.EMAIL_CODE_SEND_INTERVAL_MINUTES)

    latest_code = db.query(EmailVerificationCode).filter(
        and_(
            EmailVerificationCode.email == email,
            EmailVerificationCode.purpose == purpose
        )
    ).order_by(EmailVerificationCode.created_at.desc()).first()

    if latest_code:
        time_since_last = datetime.utcnow() - latest_code.created_at
        if time_since_last < interval:
            remaining = int((interval - time_since_last).total_seconds())
            raise VerificationCodeFrequencyError(remaining)


def check_daily_limit(db: Session, email: str) -> None:
    """
    检查每日发送次数限制

    检查同一邮箱今日已发送验证码次数是否达到上限

    Args:
        db: 数据库会话
        email: 邮箱地址

    Raises:
        VerificationCodeDailyLimitError: 达到每日上限时抛出
    """
    today_start = datetime.utcnow().replace(
        hour=0, minute=0, second=0, microsecond=0
    )

    count = db.query(func.count(EmailVerificationCode.id)).filter(
        and_(
            EmailVerificationCode.email == email,
            EmailVerificationCode.created_at >= today_start
        )
    ).scalar()

    if count >= settings.EMAIL_CODE_DAILY_LIMIT:
        raise VerificationCodeDailyLimitError()


def create_verification_code(
    db: Session,
    email: str,
    purpose: str,
    user_id: Optional[int] = None
) -> Tuple[EmailVerificationCode, str]:
    """
    创建验证码记录并返回

    Args:
        db: 数据库会话
        email: 邮箱地址
        purpose: 验证码用途
        user_id: 用户ID（可选，用于已注册用户的验证码）

    Returns:
        Tuple[EmailVerificationCode, str]: (验证码记录, 纯文本验证码)

    Raises:
        VerificationCodeFrequencyError: 发送过于频繁
        VerificationCodeDailyLimitError: 达到每日上限
    """
    email = email.lower()

    check_send_frequency(db, email, purpose)
    check_daily_limit(db, email)

    code = generate_verification_code()
    expires_at = datetime.utcnow() + timedelta(
        minutes=settings.EMAIL_CODE_EXPIRE_MINUTES
    )

    verification = EmailVerificationCode(
        user_id=user_id,
        email=email,
        code=code,
        purpose=purpose,
        expires_at=expires_at
    )

    db.add(verification)
    db.commit()
    db.refresh(verification)

    return (verification, code)


def validate_verification_code(
    db: Session,
    email: str,
    code: str,
    purpose: str,
    user_id: Optional[int] = None
) -> Tuple[bool, EmailVerificationCode]:
    """
    验证验证码是否正确

    Args:
        db: 数据库会话
        email: 邮箱地址
        code: 用户输入的验证码
        purpose: 验证码用途
        user_id: 用户ID（可选）

    Returns:
        Tuple[bool, EmailVerificationCode]: (验证是否成功, 验证码记录)

    Raises:
        VerificationCodeNotFoundError: 验证码不存在
        VerificationCodeExpiredError: 验证码已过期
        VerificationCodeAttemptsExceededError: 尝试次数超限
    """
    email = email.lower()

    query = db.query(EmailVerificationCode).filter(
        and_(
            EmailVerificationCode.email == email,
            EmailVerificationCode.purpose == purpose,
            EmailVerificationCode.used == False,
            EmailVerificationCode.expires_at > datetime.utcnow()
        )
    )

    if user_id is not None:
        query = query.filter(EmailVerificationCode.user_id == user_id)

    verification = query.order_by(EmailVerificationCode.created_at.desc()).first()

    if not verification:
        raise VerificationCodeNotFoundError()

    if verification.is_expired():
        raise VerificationCodeExpiredError()

    if not verification.can_attempt(settings.EMAIL_CODE_MAX_ATTEMPTS):
        raise VerificationCodeAttemptsExceededError(0)

    if verification.code != code:
        verification.attempt_count += 1
        db.commit()
        remaining = settings.EMAIL_CODE_MAX_ATTEMPTS - verification.attempt_count
        if remaining <= 0:
            raise VerificationCodeAttemptsExceededError(0)
        raise VerificationCodeAttemptsExceededError(remaining)

    return (True, verification)


def mark_verification_used(
    db: Session,
    verification: EmailVerificationCode
) -> None:
    """
    标记验证码为已使用

    Args:
        db: 数据库会话
        verification: 验证码记录
    """
    verification.used = True
    verification.used_at = datetime.utcnow()
    db.commit()


def get_valid_verification(
    db: Session,
    email: str,
    purpose: str,
    user_id: Optional[int] = None
) -> Optional[EmailVerificationCode]:
    """
    获取有效的验证码记录

    Args:
        db: 数据库会话
        email: 邮箱地址
        purpose: 验证码用途
        user_id: 用户ID（可选）

    Returns:
        Optional[EmailVerificationCode]: 有效的验证码记录，不存在则返回 None
    """
    email = email.lower()

    query = db.query(EmailVerificationCode).filter(
        and_(
            EmailVerificationCode.email == email,
            EmailVerificationCode.purpose == purpose,
            EmailVerificationCode.used == False,
            EmailVerificationCode.expires_at > datetime.utcnow()
        )
    )

    if user_id is not None:
        query = query.filter(EmailVerificationCode.user_id == user_id)

    return query.order_by(EmailVerificationCode.created_at.desc()).first()
