"""注册验证码邮件模板。

该模板服务于真人用户邮箱注册流程，只生成邮件主题和纯文本正文。
"""

from __future__ import annotations

from string import Template

from social_platform.app.core.branding import get_platform_display_name
from social_platform.app.domains.email.sender import EmailMessage


REGISTER_EMAIL_TEMPLATE = Template(
    """$code 是您的注册验证码

验证码将在 $expire_minutes 分钟后过期，请尽快完成验证。

请勿将验证码泄露给他人，如有疑虑请忽略此邮件。

---
此邮件由 $platform_name 系统自动发送，请勿回复。
"""
)
"""注册验证码纯文本模板。"""


def build_register_email(recipient_email: str, code: str, expire_minutes: int) -> EmailMessage:
    """构造注册验证码邮件。

    Args:
        recipient_email: 收件人邮箱地址。
        code: 明文验证码。
        expire_minutes: 验证码过期分钟数。

    Returns:
        EmailMessage: 已渲染的注册验证码邮件消息。
    """

    platform_name = get_platform_display_name()
    return EmailMessage(
        recipient_email=recipient_email,
        subject=f"【{platform_name}】注册验证码",
        text_body=REGISTER_EMAIL_TEMPLATE.safe_substitute(
            code=code,
            expire_minutes=expire_minutes,
            platform_name=platform_name,
        ),
    )
