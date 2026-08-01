"""SMTP 邮件发件器单元测试。"""

from __future__ import annotations

from email import policy
from email.parser import Parser
from types import SimpleNamespace
from typing import Any

import pytest

from social_platform.app.domains.email.sender import EmailMessage, SmtpEmailSender


class FakeSmtpConnection:
    """记录 SMTP 投递参数的测试连接。"""

    def __init__(self) -> None:
        """初始化投递记录。"""

        self.sent_messages: list[tuple[str, str, str]] = []

    def __enter__(self) -> FakeSmtpConnection:
        """进入 SMTP 连接上下文。"""

        return self

    def __exit__(self, *args: Any) -> None:
        """退出 SMTP 连接上下文。"""

    def sendmail(self, sender: str, recipient: str, raw_message: str) -> None:
        """记录待投递邮件。

        Args:
            sender: SMTP 信封发件地址。
            recipient: SMTP 信封收件地址。
            raw_message: 序列化后的邮件内容。
        """

        self.sent_messages.append((sender, recipient, raw_message))


def test_send_email_encodes_chinese_sender_name_as_display_name(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """中文发件人名称编码后仍保留可解析的邮箱地址。"""

    settings = SimpleNamespace(
        SMTP_SENDER_NAME="宇宙和平论坛",
        SMTP_SENDER_EMAIL="sender@example.com",
    )
    connection = FakeSmtpConnection()
    sender = SmtpEmailSender(settings=settings)
    monkeypatch.setattr(sender, "_create_smtp_connection", lambda: connection)

    result = sender.send_email(
        EmailMessage(
            recipient_email="recipient@example.com",
            subject="登录验证码",
            text_body="验证码为 123456。",
        )
    )

    assert result is True
    envelope_sender, envelope_recipient, raw_message = connection.sent_messages[0]
    parsed_message = Parser(policy=policy.default).parsestr(raw_message)
    from_header = parsed_message["From"]

    assert envelope_sender == "sender@example.com"
    assert envelope_recipient == "recipient@example.com"
    assert len(from_header.addresses) == 1
    assert from_header.addresses[0].display_name == "宇宙和平论坛"
    assert from_header.addresses[0].addr_spec == "sender@example.com"
    assert from_header.defects == ()
