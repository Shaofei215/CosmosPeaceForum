"""身份安全领域的邮箱验证码应用服务。

本模块封装验证码生成、频率限制、每日限额、一次性消耗和邮件发送端口调用。
具体的注册、登录和密码重置编排由 ``application.py`` 复用这些基础能力完成。
"""

from __future__ import annotations

import random
import string
from datetime import datetime, timedelta
from typing import Protocol

from sqlalchemy import and_, func
from sqlalchemy.orm import Session

from social_platform.app.core.config import get_settings
from social_platform.app.domains.identity.models import EmailVerificationCode
from social_platform.app.domains.identity.schemas import EmailCodeSendResponse
from social_platform.app.domains.invitation import application as invitation_service
from social_platform.app.domains.user.models import User


settings = get_settings()


class VerificationEmailSender(Protocol):
    """验证码邮件发送端口，隔离 identity 领域与具体邮件系统。"""

    def send_verification_email(self, email: str, code: str, purpose: str) -> bool:
        """发送验证码邮件。

        Args:
            email: 目标邮箱地址。
            code: 明文验证码。
            purpose: 验证码用途。

        Returns:
            bool: 发送成功返回 True，否则返回 False。
        """

        ...


class VerificationCodeFrequencyError(Exception):
    """验证码发送频率限制异常。"""

    def __init__(self, wait_seconds: int) -> None:
        """初始化验证码发送频率限制异常。

        Args:
            wait_seconds: 需要等待的秒数。
        """

        self.wait_seconds = wait_seconds
        super().__init__(f"发送过于频繁，请 {wait_seconds} 秒后再试")


class VerificationCodeDailyLimitError(Exception):
    """验证码每日发送次数限制异常。"""

    def __init__(self) -> None:
        """初始化验证码每日发送次数限制异常。"""

        super().__init__("今日发送次数已达上限，请明天再试")


class VerificationCodeNotFoundError(Exception):
    """验证码不存在或已失效异常。"""

    def __init__(self, message: str = "验证码无效，请重新获取") -> None:
        """初始化验证码不存在异常。

        Args:
            message: 对外展示的错误信息。
        """

        super().__init__(message)


class VerificationCodeExpiredError(Exception):
    """验证码已过期异常。"""

    def __init__(self) -> None:
        """初始化验证码过期异常。"""

        super().__init__("验证码已过期，请重新获取")


class VerificationCodeAttemptsExceededError(Exception):
    """验证码错误尝试次数超限异常。"""

    def __init__(self, remaining_attempts: int) -> None:
        """初始化验证码尝试次数超限异常。

        Args:
            remaining_attempts: 剩余尝试次数。
        """

        self.remaining_attempts = remaining_attempts
        super().__init__("验证失败次数过多，请重新获取验证码")


class VerificationCodeMismatchError(Exception):
    """验证码内容不匹配异常。"""

    def __init__(self, remaining_attempts: int) -> None:
        """初始化验证码不匹配异常。

        Args:
            remaining_attempts: 本次失败后剩余可尝试次数。
        """

        self.remaining_attempts = remaining_attempts
        super().__init__(f"验证码错误，还剩 {remaining_attempts} 次尝试机会")


class VerificationCodeInvalidError(Exception):
    """验证码统一无效异常，用于避免登录时泄露验证码状态。"""

    def __init__(self, message: str = "验证码错误") -> None:
        """初始化验证码统一无效异常。

        Args:
            message: 对外展示的错误信息。
        """

        super().__init__(message)


class EmailAlreadyRegisteredError(Exception):
    """邮箱已注册异常。"""

    def __init__(self) -> None:
        """初始化邮箱已注册异常。"""

        super().__init__("该邮箱已被注册")


class VerifiedHumanUserNotFoundError(Exception):
    """邮箱未绑定已验证真人用户异常。"""

    def __init__(self) -> None:
        """初始化已验证真人用户不存在异常。"""

        super().__init__("该邮箱未绑定任何已验证账号")


class EmailDeliveryError(Exception):
    """验证码邮件发送失败异常。"""

    def __init__(self) -> None:
        """初始化验证码邮件发送失败异常。"""

        super().__init__("邮件发送失败，请稍后重试")


def generate_verification_code(length: int = 6) -> str:
    """生成随机数字验证码。

    Args:
        length: 验证码长度。

    Returns:
        str: 随机数字验证码字符串。
    """

    return "".join(random.choices(string.digits, k=length))


def check_send_frequency(db: Session, email: str, purpose: str) -> None:
    """检查同一邮箱同一用途验证码发送频率。

    Args:
        db: 当前数据库会话。
        email: 邮箱地址。
        purpose: 验证码用途。

    Raises:
        VerificationCodeFrequencyError: 发送间隔未达到配置要求。
    """

    interval = timedelta(minutes=settings.EMAIL_CODE_SEND_INTERVAL_MINUTES)
    latest_code = db.query(EmailVerificationCode).filter(
        and_(
            EmailVerificationCode.email == email,
            EmailVerificationCode.purpose == purpose,
        )
    ).order_by(EmailVerificationCode.created_at.desc()).first()

    if latest_code:
        time_since_last = datetime.utcnow() - latest_code.created_at
        if time_since_last < interval:
            remaining = int((interval - time_since_last).total_seconds())
            raise VerificationCodeFrequencyError(remaining)


def check_daily_limit(db: Session, email: str) -> None:
    """检查同一邮箱每日验证码发送次数限制。

    Args:
        db: 当前数据库会话。
        email: 邮箱地址。

    Raises:
        VerificationCodeDailyLimitError: 今日发送次数已达到配置上限。
    """

    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    count = db.query(func.count(EmailVerificationCode.id)).filter(
        and_(
            EmailVerificationCode.email == email,
            EmailVerificationCode.created_at >= today_start,
        )
    ).scalar()

    if count >= settings.EMAIL_CODE_DAILY_LIMIT:
        raise VerificationCodeDailyLimitError()


def create_verification_code(
    db: Session,
    email: str,
    purpose: str,
    user_id: int | None = None,
) -> tuple[EmailVerificationCode, str]:
    """创建验证码记录并返回明文验证码。

    Args:
        db: 当前数据库会话。
        email: 邮箱地址。
        purpose: 验证码用途。
        user_id: 已存在用户 ID，注册阶段可为空。

    Returns:
        tuple[EmailVerificationCode, str]: 验证码记录与明文验证码。

    Raises:
        VerificationCodeFrequencyError: 发送过于频繁。
        VerificationCodeDailyLimitError: 达到每日发送上限。
    """

    normalized_email = email.lower()
    check_send_frequency(db, normalized_email, purpose)
    check_daily_limit(db, normalized_email)

    code = generate_verification_code()
    expires_at = datetime.utcnow() + timedelta(minutes=settings.EMAIL_CODE_EXPIRE_MINUTES)
    verification = EmailVerificationCode(
        user_id=user_id,
        email=normalized_email,
        code=code,
        purpose=purpose,
        expires_at=expires_at,
    )

    db.add(verification)
    db.commit()
    db.refresh(verification)
    return verification, code


def verified_human_user_by_email(db: Session, email: str) -> User | None:
    """按邮箱查找已验证真人用户。

    Args:
        db: 当前数据库会话。
        email: 规范化后的邮箱地址。

    Returns:
        User | None: 找到则返回用户，否则返回 None。
    """

    return db.query(User).filter(
        and_(
            User.email == email,
            User.email_verified.is_(True),
            User.is_ai_agent.is_(False),
        )
    ).first()


def _send_code_response(email: str) -> EmailCodeSendResponse:
    """构造验证码发送成功响应。

    Args:
        email: 目标邮箱地址。

    Returns:
        EmailCodeSendResponse: API 响应 DTO。
    """

    return EmailCodeSendResponse(
        message="验证码已发送至您的邮箱",
        email=email,
        expires_in=settings.EMAIL_CODE_EXPIRE_MINUTES * 60,
    )


def _create_and_send_code(
    db: Session,
    email: str,
    purpose: str,
    email_sender: VerificationEmailSender,
    user_id: int | None = None,
) -> EmailCodeSendResponse:
    """创建验证码并通过注入的邮件端口发送。

    Args:
        db: 当前数据库会话。
        email: 目标邮箱地址。
        purpose: 验证码用途。
        email_sender: 验证码邮件发送端口。
        user_id: 已存在用户 ID，注册阶段可为空。

    Returns:
        EmailCodeSendResponse: 发送成功响应。

    Raises:
        EmailDeliveryError: 邮件发送端口返回失败。
    """

    _, code = create_verification_code(db, email, purpose, user_id=user_id)
    if not email_sender.send_verification_email(email, code, purpose):
        db.rollback()
        raise EmailDeliveryError()
    return _send_code_response(email)


def send_register_verification_code(
    db: Session,
    email: str,
    email_sender: VerificationEmailSender,
    invitation_code: str | None = None,
) -> EmailCodeSendResponse:
    """发送真人用户注册验证码。

    Args:
        db: 当前数据库会话。
        email: 目标邮箱地址。
        email_sender: 验证码邮件发送端口。
        invitation_code: 邀请制开启时用户提交的邀请码。

    Returns:
        EmailCodeSendResponse: 发送成功响应。

    Raises:
        EmailAlreadyRegisteredError: 邮箱已经被注册。
        invitation_service.InvitationRequiredError: 邀请制开启但未提交邀请码。
        invitation_service.InvitationInvalidError: 邀请码不存在、邮箱不匹配或已使用。
        VerificationCodeFrequencyError: 发送过于频繁。
        VerificationCodeDailyLimitError: 达到每日发送上限。
        EmailDeliveryError: 邮件发送失败。
    """

    normalized_email = email.lower()
    if db.query(User).filter(User.email == normalized_email).first():
        raise EmailAlreadyRegisteredError()
    invitation_service.get_required_registration_invitation(db, normalized_email, invitation_code)
    return _create_and_send_code(db, normalized_email, "register", email_sender)


def send_login_verification_code(
    db: Session,
    email: str,
    email_sender: VerificationEmailSender,
) -> EmailCodeSendResponse:
    """发送真人用户验证码登录邮件。

    Args:
        db: 当前数据库会话。
        email: 目标邮箱地址。
        email_sender: 验证码邮件发送端口。

    Returns:
        EmailCodeSendResponse: 发送成功响应。

    Raises:
        VerifiedHumanUserNotFoundError: 邮箱未绑定已验证真人用户。
        VerificationCodeFrequencyError: 发送过于频繁。
        VerificationCodeDailyLimitError: 达到每日发送上限。
        EmailDeliveryError: 邮件发送失败。
    """

    normalized_email = email.lower()
    user = verified_human_user_by_email(db, normalized_email)
    if user is None:
        raise VerifiedHumanUserNotFoundError()
    return _create_and_send_code(db, normalized_email, "login", email_sender, user_id=user.id)


def send_password_reset_code(
    db: Session,
    email: str,
    email_sender: VerificationEmailSender,
) -> EmailCodeSendResponse:
    """发送密码重置验证码。

    Args:
        db: 当前数据库会话。
        email: 目标邮箱地址。
        email_sender: 验证码邮件发送端口。

    Returns:
        EmailCodeSendResponse: 发送成功响应。

    Raises:
        VerifiedHumanUserNotFoundError: 邮箱未绑定已验证真人用户。
        VerificationCodeFrequencyError: 发送过于频繁。
        VerificationCodeDailyLimitError: 达到每日发送上限。
        EmailDeliveryError: 邮件发送失败。
    """

    normalized_email = email.lower()
    user = verified_human_user_by_email(db, normalized_email)
    if user is None:
        raise VerifiedHumanUserNotFoundError()
    return _create_and_send_code(db, normalized_email, "reset_password", email_sender, user_id=user.id)


def get_valid_verification(
    db: Session,
    email: str,
    purpose: str,
    user_id: int | None = None,
) -> EmailVerificationCode | None:
    """获取最新有效验证码记录。

    Args:
        db: 当前数据库会话。
        email: 邮箱地址。
        purpose: 验证码用途。
        user_id: 已存在用户 ID，注册阶段可为空。

    Returns:
        EmailVerificationCode | None: 最新有效验证码；不存在则返回 None。
    """

    normalized_email = email.lower()
    query = db.query(EmailVerificationCode).filter(
        and_(
            EmailVerificationCode.email == normalized_email,
            EmailVerificationCode.purpose == purpose,
            EmailVerificationCode.used.is_(False),
            EmailVerificationCode.expires_at > datetime.utcnow(),
        )
    )

    if user_id is not None:
        query = query.filter(EmailVerificationCode.user_id == user_id)

    return query.order_by(EmailVerificationCode.created_at.desc()).first()


def mark_verification_used(db: Session, verification: EmailVerificationCode) -> None:
    """标记验证码为已使用。

    Args:
        db: 当前数据库会话。
        verification: 待标记的验证码记录。
    """

    verification.used = True
    verification.used_at = datetime.utcnow()
    db.commit()


def validate_verification_code(
    db: Session,
    email: str,
    code: str,
    purpose: str,
    user_id: int | None = None,
) -> tuple[bool, EmailVerificationCode]:
    """验证通用邮箱验证码是否正确。

    Args:
        db: 当前数据库会话。
        email: 邮箱地址。
        code: 用户提交的验证码。
        purpose: 验证码用途。
        user_id: 已存在用户 ID，注册阶段可为空。

    Returns:
        tuple[bool, EmailVerificationCode]: 验证成功标记和验证码记录。

    Raises:
        VerificationCodeNotFoundError: 验证码不存在或已失效。
        VerificationCodeExpiredError: 验证码已过期。
        VerificationCodeAttemptsExceededError: 尝试次数超限。
    """

    verification = get_valid_verification(db, email, purpose, user_id=user_id)
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

    return True, verification
