"""身份安全领域迁移测试。

该模块覆盖 identity 领域中的验证码聚合与 session 轮换行为，确保迁移后旧 API
依赖的核心认证语义保持稳定。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from collections.abc import Generator
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from social_platform.app.core import security as core_security
from social_platform.app.db.session import Base
from social_platform.app.domains.email.application import VerificationEmailSenderAdapter
from social_platform.app.domains.email.sender import EmailMessage
from social_platform.app.domains.email.templates import build_verification_email
from social_platform.app.domains import registry as domain_models  # noqa: F401
from social_platform.app.domains.identity import application, sessions, verification
from social_platform.app.domains.identity.models import EmailVerificationCode
from social_platform.app.domains.user.models import User


@dataclass
class SentVerificationEmail:
    """测试用已发送验证码邮件记录。"""

    email: str
    code: str
    purpose: str


@dataclass
class FakeEmailSender:
    """测试用验证码邮件发送端口，记录调用但不发送真实邮件。"""

    sent: list[SentVerificationEmail] = field(default_factory=list)
    should_succeed: bool = True

    def send_verification_email(self, email: str, code: str, purpose: str) -> bool:
        """记录验证码邮件发送请求。

        Args:
            email: 目标邮箱地址。
            code: 明文验证码。
            purpose: 验证码用途。

        Returns:
            bool: 预设的发送结果。
        """

        self.sent.append(SentVerificationEmail(email=email, code=code, purpose=purpose))
        return self.should_succeed


@dataclass
class FakeGenericEmailSender:
    """测试用通用邮件发件器，记录已渲染邮件但不连接 SMTP。"""

    sent: list[EmailMessage] = field(default_factory=list)
    should_succeed: bool = True

    def send_email(self, message: EmailMessage) -> bool:
        """记录邮件发送请求。

        Args:
            message: 已渲染完成的邮件消息。

        Returns:
            bool: 预设的发送结果。
        """

        self.sent.append(message)
        return self.should_succeed


@pytest.fixture()
def db_session() -> Generator[Session, None, None]:
    """创建身份安全领域测试使用的内存数据库会话。

    Yields:
        Session: 已创建全部领域表的 SQLAlchemy 会话。
    """

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    testing_session_local = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = testing_session_local()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture(autouse=True)
def identity_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    """隔离 identity 测试所需的配置值。

    Args:
        monkeypatch: pytest 提供的属性替换工具。
    """

    settings = SimpleNamespace(
        EMAIL_CODE_EXPIRE_MINUTES=10,
        EMAIL_CODE_SEND_INTERVAL_MINUTES=1,
        EMAIL_CODE_DAILY_LIMIT=5,
        EMAIL_CODE_MAX_ATTEMPTS=3,
        ACCESS_TOKEN_EXPIRE_MINUTES=15,
        REFRESH_TOKEN_EXPIRE_HOURS=12,
        REMEMBER_ME_REFRESH_TOKEN_EXPIRE_DAYS=30,
        ADMIN_ACCESS_TOKEN_EXPIRE_MINUTES=10,
        ADMIN_REFRESH_TOKEN_EXPIRE_HOURS=8,
        ADMIN_REMEMBER_ME_REFRESH_TOKEN_EXPIRE_DAYS=14,
        AI_ACCESS_TOKEN_EXPIRE_HOURS=24,
        AI_REFRESH_TOKEN_EXPIRE_HOURS=72,
        JWT_SECRET_KEY="identity-test-secret",
        JWT_ALGORITHM="HS256",
    )
    monkeypatch.setattr(verification, "settings", settings)
    monkeypatch.setattr(application, "settings", settings)
    monkeypatch.setattr(sessions, "settings", settings)
    monkeypatch.setattr(core_security, "settings", settings)


def test_register_code_send_persists_record_and_enforces_frequency(db_session: Session) -> None:
    """注册验证码发送会落库，并对同邮箱同用途执行频率限制。"""

    sender = FakeEmailSender()

    response = verification.send_register_verification_code(
        db_session,
        "Test@Example.com",
        sender,
    )

    stored_code = db_session.query(EmailVerificationCode).one()
    assert response.email == "test@example.com"
    assert stored_code.email == "test@example.com"
    assert stored_code.purpose == "register"
    assert sender.sent == [
        SentVerificationEmail(
            email="test@example.com",
            code=stored_code.code,
            purpose="register",
        )
    ]

    with pytest.raises(verification.VerificationCodeFrequencyError):
        verification.send_register_verification_code(db_session, "test@example.com", sender)


def test_verification_email_sender_adapter_renders_template_and_delegates() -> None:
    """验证码邮件适配器会渲染业务模板，再委托通用发件器发送。"""

    sender = FakeGenericEmailSender()
    adapter = VerificationEmailSenderAdapter(
        email_sender=sender,
        settings=SimpleNamespace(EMAIL_CODE_EXPIRE_MINUTES=7),
    )

    assert adapter.send_verification_email("person@example.com", "123456", "login") is True

    assert len(sender.sent) == 1
    message = sender.sent[0]
    assert message.recipient_email == "person@example.com"
    assert message.subject == "【宇宙和平论坛】登录验证码"
    assert "123456 是您的登录验证码" in message.text_body
    assert "7 分钟后过期" in message.text_body


def test_build_verification_email_rejects_unknown_purpose() -> None:
    """未知验证码用途不会落到默认模板。"""

    with pytest.raises(ValueError):
        build_verification_email("person@example.com", "123456", "unknown", 10)


def test_register_human_user_with_code_consumes_verification(db_session: Session) -> None:
    """注册验证码验证成功后会创建真人用户并标记验证码已使用。"""

    sender = FakeEmailSender()
    verification.send_register_verification_code(db_session, "person@example.com", sender)

    user = application.register_human_user_with_code(
        db_session,
        "person@example.com",
        "secret-password",
        sender.sent[0].code,
    )
    stored_code = db_session.query(EmailVerificationCode).one()

    assert user.email == "person@example.com"
    assert user.email_verified is True
    assert stored_code.used is True
    assert stored_code.user_id == user.id


def test_refresh_token_pair_rotates_refresh_token(db_session: Session) -> None:
    """refresh token 成功使用后会被轮换，旧 token 立即失效。"""

    first_pair = sessions.create_session_token_pair(
        db=db_session,
        account_id=42,
        scope="user",
        client_type="desktop",
        remember_me=False,
        user_agent="pytest",
        ip_address="127.0.0.1",
    )

    next_pair = sessions.refresh_token_pair(
        db=db_session,
        refresh_token=str(first_pair["refresh_token"]),
        expected_scope="user",
        user_agent="pytest-next",
        ip_address="127.0.0.2",
    )

    assert next_pair["session_id"] == first_pair["session_id"]
    assert next_pair["refresh_token"] != first_pair["refresh_token"]

    with pytest.raises(sessions.RefreshTokenInvalidError):
        sessions.refresh_token_pair(
            db=db_session,
            refresh_token=str(first_pair["refresh_token"]),
            expected_scope="user",
            user_agent="pytest-old",
            ip_address="127.0.0.3",
        )


def test_password_reset_revokes_all_existing_user_sessions(db_session: Session) -> None:
    """密码重置与验证码消费、全部用户 Session 撤销在同一事务内完成。"""

    user = User(
        username="reset-user",
        email="reset@example.com",
        email_verified=True,
        password_hash=core_security.get_password_hash("old-password"),
    )
    db_session.add(user)
    db_session.commit()
    sender = FakeEmailSender()
    verification.send_password_reset_code(db_session, user.email, sender)
    first = sessions.create_session_token_pair(
        db=db_session,
        account_id=user.id,
        scope="user",
        client_type="desktop",
        remember_me=False,
        user_agent="pytest-desktop",
        ip_address="127.0.0.1",
        revoke_same_client=False,
    )
    sessions.create_session_token_pair(
        db=db_session,
        account_id=user.id,
        scope="user",
        client_type="mobile",
        remember_me=True,
        user_agent="pytest-mobile",
        ip_address="127.0.0.2",
        revoke_same_client=False,
    )

    application.reset_password_with_code(
        db_session,
        user.email,
        sender.sent[0].code,
        "new-password",
    )

    assert sessions.list_sessions(db_session, user.id, "user") == []
    with pytest.raises(sessions.RefreshTokenInvalidError):
        sessions.refresh_token_pair(
            db=db_session,
            refresh_token=str(first["refresh_token"]),
            expected_scope="user",
            user_agent="pytest-old",
            ip_address="127.0.0.3",
        )
    db_session.refresh(user)
    assert core_security.verify_password("new-password", user.password_hash)
