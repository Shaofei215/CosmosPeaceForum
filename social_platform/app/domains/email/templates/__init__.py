"""公共邮件领域模板入口。

本包按邮件用途拆分模板文件，并提供统一的模板选择函数。模板只负责构造邮件内容，
不负责 SMTP 连接或实际投递。
"""

from __future__ import annotations

from social_platform.app.domains.email.sender import EmailMessage
from social_platform.app.domains.email.templates.login_verification import build_login_email
from social_platform.app.domains.email.templates.password_reset_verification import (
    build_password_reset_email,
)
from social_platform.app.domains.email.templates.register_verification import build_register_email


def build_verification_email(
    recipient_email: str,
    code: str,
    purpose: str,
    expire_minutes: int,
) -> EmailMessage:
    """按验证码用途构造邮件消息。

    Args:
        recipient_email: 收件人邮箱地址。
        code: 明文验证码。
        purpose: 验证码用途，支持 register、login、reset_password。
        expire_minutes: 验证码过期分钟数。

    Returns:
        EmailMessage: 已渲染完成的验证码邮件消息。

    Raises:
        ValueError: 验证码用途不受支持。
    """

    if purpose == "register":
        return build_register_email(recipient_email, code, expire_minutes)
    if purpose == "login":
        return build_login_email(recipient_email, code, expire_minutes)
    if purpose == "reset_password":
        return build_password_reset_email(recipient_email, code, expire_minutes)
    raise ValueError(f"不支持的验证码邮件用途: {purpose}")

