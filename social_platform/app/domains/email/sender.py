"""通用 SMTP 邮件发件器。

本模块只负责把已经构造好的邮件消息通过 SMTP 投递，不关心验证码、通知等具体
业务含义。业务领域应先生成邮件主题和正文，再调用发件器完成发送。
"""

from __future__ import annotations

import logging
import smtplib
import ssl
from dataclasses import dataclass
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Protocol

from social_platform.app.core.config import Settings, get_settings


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class EmailMessage:
    """待投递的纯文本邮件消息。

    Attributes:
        recipient_email: 收件人邮箱地址。
        subject: 邮件主题。
        text_body: 纯文本邮件正文。
    """

    recipient_email: str
    subject: str
    text_body: str


class EmailSender(Protocol):
    """通用邮件发件器端口，供业务领域依赖。"""

    def send_email(self, message: EmailMessage) -> bool:
        """发送一封邮件。

        Args:
            message: 已经包含收件人、主题和正文的邮件消息。

        Returns:
            bool: 发送成功返回 True，发送失败返回 False。
        """

        ...


class SmtpEmailSender:
    """基于 SMTP 的通用邮件发件器。

    该类从应用配置中读取 SMTP 服务器、账号和发件人信息，只承担连接、认证和投递
    职责，不在内部拼装任何业务邮件内容。
    """

    def __init__(self, settings: Settings | None = None) -> None:
        """初始化 SMTP 发件器。

        Args:
            settings: 可选应用配置；测试或替代环境可注入自定义配置。
        """

        self.settings = settings or get_settings()

    def _create_smtp_connection(self) -> smtplib.SMTP:
        """创建并登录 SMTP 连接。

        Returns:
            smtplib.SMTP: 已完成登录的 SMTP 连接对象。

        Raises:
            smtplib.SMTPException: SMTP 连接或认证失败时抛出。
            OSError: 网络连接失败时抛出。
        """

        context = ssl.create_default_context()
        if self.settings.SMTP_USE_SSL:
            server = smtplib.SMTP_SSL(
                self.settings.SMTP_HOST,
                self.settings.SMTP_PORT,
                context=context,
            )
        else:
            server = smtplib.SMTP(self.settings.SMTP_HOST, self.settings.SMTP_PORT)
            server.starttls(context=context)

        server.login(self.settings.SMTP_USER, self.settings.SMTP_PASSWORD)
        return server

    def send_email(self, message: EmailMessage) -> bool:
        """通过 SMTP 发送纯文本邮件。

        Args:
            message: 已渲染完成的邮件消息。

        Returns:
            bool: SMTP 投递成功返回 True，失败时记录日志并返回 False。
        """

        try:
            mime_message = MIMEMultipart("alternative")
            mime_message["Subject"] = message.subject
            mime_message["From"] = (
                f"{self.settings.SMTP_SENDER_NAME} <{self.settings.SMTP_SENDER_EMAIL}>"
            )
            mime_message["To"] = message.recipient_email
            mime_message.attach(MIMEText(message.text_body, "plain", "utf-8"))

            with self._create_smtp_connection() as server:
                server.sendmail(
                    self.settings.SMTP_SENDER_EMAIL,
                    message.recipient_email,
                    mime_message.as_string(),
                )

            return True
        except Exception:
            logger.exception("SMTP 邮件发送失败 recipient=%s", message.recipient_email)
            return False


smtp_email_sender = SmtpEmailSender()
"""默认 SMTP 邮件发件器实例，供 HTTP 适配层或业务适配器复用。"""

