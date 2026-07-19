"""身份安全领域的账号验证编排用例。

本模块只保留跨验证码与用户账号状态的流程编排，例如注册验证码创建真人用户、
登录验证码消耗和密码重置；session 生命周期与验证码基础规则分别在邻近模块中。
"""

from datetime import datetime
from social_platform.app.core.timezone import local_now

from sqlalchemy.orm import Session

from social_platform.app.core.config import get_settings
from social_platform.app.core.security import get_password_hash
from social_platform.app.domains.identity import verification
from social_platform.app.domains.identity import sessions as session_service
from social_platform.app.domains.identity.models import EmailVerificationCode
from social_platform.app.domains.invitation import application as invitation_service
from social_platform.app.domains.user.models import User


settings = get_settings()


def _consume_matching_code(
    db: Session,
    verification_code: EmailVerificationCode,
    code: str,
    *,
    unified_error: bool = False,
) -> None:
    """校验验证码内容并在成功时标记为已使用。

    Args:
        db: 当前数据库会话。
        verification_code: 待校验的验证码记录。
        code: 用户提交的验证码。
        unified_error: 是否用统一错误隐藏验证码具体状态。

    Raises:
        verification.VerificationCodeAttemptsExceededError: 尝试次数超限。
        verification.VerificationCodeMismatchError: 验证码内容错误。
        verification.VerificationCodeInvalidError: 统一验证码错误。
    """

    if verification_code.is_expired():
        if unified_error:
            raise verification.VerificationCodeInvalidError()
        raise verification.VerificationCodeNotFoundError()
    if not verification_code.can_attempt(settings.EMAIL_CODE_MAX_ATTEMPTS):
        if unified_error:
            raise verification.VerificationCodeInvalidError()
        raise verification.VerificationCodeAttemptsExceededError(0)
    if verification_code.code != code:
        verification_code.attempt_count += 1
        db.commit()
        if unified_error:
            raise verification.VerificationCodeInvalidError()
        remaining = settings.EMAIL_CODE_MAX_ATTEMPTS - verification_code.attempt_count
        raise verification.VerificationCodeMismatchError(remaining)

    verification_code.used = True
    verification_code.used_at = local_now()


def register_human_user_with_code(
    db: Session,
    email: str,
    password: str,
    code: str,
    invitation_code: str | None = None,
) -> User:
    """验证注册验证码并创建真人用户。

    Args:
        db: 当前数据库会话。
        email: 注册邮箱。
        password: 明文密码。
        code: 用户提交的注册验证码。
        invitation_code: 邀请制开启时用户提交的邀请码。

    Returns:
        User: 创建后的真人用户。

    Raises:
        verification.EmailAlreadyRegisteredError: 邮箱已经被注册。
        invitation_service.InvitationRequiredError: 邀请制开启但未提交邀请码。
        invitation_service.InvitationInvalidError: 邀请码不存在、邮箱不匹配或已使用。
        verification.VerificationCodeNotFoundError: 注册验证码不存在或已失效。
        verification.VerificationCodeAttemptsExceededError: 尝试次数超限。
        verification.VerificationCodeMismatchError: 验证码内容错误。
    """

    normalized_email = email.lower()
    if db.query(User).filter(User.email == normalized_email).first():
        raise verification.EmailAlreadyRegisteredError()
    invitation = invitation_service.get_required_registration_invitation(
        db,
        normalized_email,
        invitation_code,
    )

    verification_code = verification.get_valid_verification(db, normalized_email, "register")
    if not verification_code:
        raise verification.VerificationCodeNotFoundError("注册信息无效，请重新获取验证码")
    _consume_matching_code(db, verification_code, code)

    db_user = User(
        username=f"用户_{verification_code.id}",
        password_hash=get_password_hash(password),
        email=normalized_email,
        email_verified=True,
        email_verified_at=local_now(),
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)

    verification_code.user_id = db_user.id
    invitation_service.consume_registration_invitation(db, invitation, db_user.id)
    db.commit()
    return db_user


def validate_login_verification_code(db: Session, user: User, email: str, code: str) -> None:
    """验证并消耗真人用户登录验证码。

    Args:
        db: 当前数据库会话。
        user: 已验证真人用户。
        email: 用户登录邮箱。
        code: 用户提交的登录验证码。

    Raises:
        verification.VerificationCodeInvalidError: 验证码不存在、过期、超限或内容错误。
    """

    verification_code = verification.get_valid_verification(db, email, "login", user_id=user.id)
    if not verification_code:
        raise verification.VerificationCodeInvalidError()

    _consume_matching_code(db, verification_code, code, unified_error=True)
    db.commit()


def reset_password_with_code(db: Session, email: str, code: str, new_password: str) -> None:
    """验证密码重置验证码并更新密码。

    Args:
        db: 当前数据库会话。
        email: 已绑定并验证的邮箱。
        code: 用户提交的密码重置验证码。
        new_password: 新明文密码。

    Raises:
        verification.VerifiedHumanUserNotFoundError: 邮箱未绑定已验证真人用户。
        verification.VerificationCodeNotFoundError: 重置验证码不存在或已失效。
        verification.VerificationCodeAttemptsExceededError: 尝试次数超限。
        verification.VerificationCodeMismatchError: 验证码内容错误。
    """

    normalized_email = email.lower()
    user = verification.verified_human_user_by_email(db, normalized_email)
    if user is None:
        raise verification.VerifiedHumanUserNotFoundError()

    verification_code = verification.get_valid_verification(
        db,
        normalized_email,
        "reset_password",
        user_id=user.id,
    )
    if not verification_code:
        raise verification.VerificationCodeNotFoundError()

    _consume_matching_code(db, verification_code, code)
    user.password_hash = get_password_hash(new_password)
    session_service.revoke_all_sessions(db, user.id, "user", commit=False)
    db.commit()
