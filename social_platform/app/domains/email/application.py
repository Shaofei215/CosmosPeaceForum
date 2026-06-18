"""公共邮件领域应用服务。

本模块负责把平台业务邮件内容与通用发件器组合起来。上游业务领域只表达“需要发送
哪类邮件”的意图，具体模板选择、正文渲染和发件器委托都收敛在公共 email 领域。
"""

from __future__ import annotations

import logging

from social_platform.app.core.config import Settings, get_settings
from social_platform.app.domains.email.sender import EmailSender, smtp_email_sender
from social_platform.app.domains.email.templates import build_verification_email


logger = logging.getLogger(__name__)


class VerificationEmailSenderAdapter:
    """验证码邮件发送适配器。

    该适配器服务于 identity 领域定义的验证码邮件发送端口，但实现归属公共 email
    领域：先根据用途渲染公共邮件模板，再委托通用邮件发件器投递。
    """

    def __init__(
        self,
        email_sender: EmailSender = smtp_email_sender,
        settings: Settings | None = None,
    ) -> None:
        """初始化验证码邮件发送适配器。

        Args:
            email_sender: 通用邮件发件器端口。
            settings: 可选应用配置，用于读取验证码过期分钟数。
        """

        self.email_sender = email_sender
        self.settings = settings or get_settings()

    def send_verification_email(self, email: str, code: str, purpose: str) -> bool:
        """发送验证码邮件。

        Args:
            email: 目标邮箱地址。
            code: 明文验证码。
            purpose: 验证码用途，支持 register、login、reset_password。

        Returns:
            bool: 模板构造和邮件投递均成功返回 True，否则返回 False。
        """

        try:
            message = build_verification_email(
                recipient_email=email,
                code=code,
                purpose=purpose,
                expire_minutes=self.settings.EMAIL_CODE_EXPIRE_MINUTES,
            )
        except ValueError:
            logger.exception("验证码邮件模板选择失败 purpose=%s", purpose)
            return False
        return self.email_sender.send_email(message)


verification_email_sender = VerificationEmailSenderAdapter()
"""默认验证码邮件发送适配器实例，供认证路由注入 identity 验证码服务。"""

