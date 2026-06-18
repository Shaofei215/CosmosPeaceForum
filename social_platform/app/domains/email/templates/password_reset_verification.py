"""密码重置验证码邮件模板。

该模板服务于真人用户忘记密码流程，只生成邮件主题和纯文本正文。
"""

from __future__ import annotations

from string import Template

from social_platform.app.domains.email.sender import EmailMessage


PASSWORD_RESET_EMAIL_TEMPLATE = Template(
    """$code 是您的重置密码验证码

验证码将在 $expire_minutes 分钟后过期，请尽快完成验证。

请勿将验证码泄露给他人，如果这不是您的操作，请立即检查账号安全。

---
此邮件由 CosmosPeaceForum 系统自动发送，请勿回复。
"""
)
"""密码重置验证码纯文本模板。"""


def build_password_reset_email(
    recipient_email: str,
    code: str,
    expire_minutes: int,
) -> EmailMessage:
    """构造密码重置验证码邮件。

    Args:
        recipient_email: 收件人邮箱地址。
        code: 明文验证码。
        expire_minutes: 验证码过期分钟数。

    Returns:
        EmailMessage: 已渲染的密码重置验证码邮件消息。
    """

    return EmailMessage(
        recipient_email=recipient_email,
        subject="【CosmosPeaceForum】密码重置验证码",
        text_body=PASSWORD_RESET_EMAIL_TEMPLATE.safe_substitute(
            code=code,
            expire_minutes=expire_minutes,
        ),
    )

