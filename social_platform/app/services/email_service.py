# 邮件服务业务逻辑层
# 提供基于 SMTP 的邮件发送功能，用于发送验证码邮件
import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from string import Template

from social_platform.app.core.config import get_settings


settings = get_settings()


EMAIL_REGISTER_TEMPLATE = Template("""$code 是您的注册验证码

验证码将在 $expire_minutes 分钟后过期，请尽快完成验证。

请勿将验证码泄露给他人，如有疑虑请忽略此邮件。

---
此邮件由 Imaginary Tree 系统自动发送，请勿回复。
""")

EMAIL_RESET_TEMPLATE = Template("""$code 是您的重置密码

验证码将在 $expire_minutes 分钟后过期，请尽快完成验证。

请勿将验证码泄露给他人，如果这不是您的操作，请立即检查账号安全。

---
此邮件由 Imaginary Tree 系统自动发送，请勿回复。
""")

EMAIL_LOGIN_TEMPLATE = Template("""$code 是您的登录验证码

验证码将在 $expire_minutes 分钟后过期，请尽快完成验证。

请勿将验证码泄露给他人，如果这不是您的操作，请立即检查账号安全。    

---
此邮件由 Imaginary Tree 系统自动发送，请勿回复。
""")


class EmailService:
    """
    SMTP 邮件服务类

    提供邮件发送功能，支持 SSL/TLS 加密连接
    """

    def __init__(self):
        """初始化邮件服务，使用配置中的 SMTP 设置"""
        self.smtp_host = settings.SMTP_HOST
        self.smtp_port = settings.SMTP_PORT
        self.smtp_user = settings.SMTP_USER
        self.smtp_password = settings.SMTP_PASSWORD
        self.use_ssl = settings.SMTP_USE_SSL
        self.sender_name = settings.SMTP_SENDER_NAME
        self.sender_email = settings.SMTP_SENDER_EMAIL

    def _create_smtp_connection(self) -> smtplib.SMTP_SSL:
        """
        创建 SMTP 连接

        根据配置选择 SSL 或 TLS 连接方式

        Returns:
            smtplib.SMTP_SSL: SMTP 连接对象

        Raises:
            smtplib.SMTPException: 连接失败时抛出
        """
        if self.use_ssl:
            context = ssl.create_default_context()
            server = smtplib.SMTP_SSL(
                self.smtp_host,
                self.smtp_port,
                context=context
            )
            server.login(self.smtp_user, self.smtp_password)
        else:
            context = ssl.create_default_context()
            server = smtplib.SMTP(self.smtp_host, self.smtp_port)
            server.starttls(context=context)
            server.login(self.smtp_user, self.smtp_password)

        return server

    def send_verification_email(
        self,
        to_email: str,
        code: str,
        purpose: str = "register"
    ) -> bool:
        """
        发送验证码邮件

        Args:
            to_email: 收件人邮箱地址
            code: 6位数字验证码
            purpose: 验证码用途，"register" / "login" / "reset_password"

        Returns:
            bool: 发送成功返回 True，失败返回 False
        """
        try:
            if purpose == "reset_password":
                template = EMAIL_RESET_TEMPLATE
                subject = "【Imaginary Tree】密码重置验证码"
            elif purpose == "login":
                template = EMAIL_LOGIN_TEMPLATE
                subject = "【Imaginary Tree】登录验证码"
            else:
                template = EMAIL_REGISTER_TEMPLATE
                subject = "【Imaginary Tree】注册验证码"

            text_content = template.safe_substitute(
                code=code,
                expire_minutes=settings.EMAIL_CODE_EXPIRE_MINUTES
            )

            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = f"{self.sender_name} <{self.sender_email}>"
            msg['To'] = to_email

            text_part = MIMEText(text_content, 'plain', 'utf-8')
            msg.attach(text_part)

            with self._create_smtp_connection() as server:
                server.sendmail(
                    self.sender_email,
                    to_email,
                    msg.as_string()
                )

            return True

        except Exception as e:
            print(f"发送邮件失败: {e}")
            return False


email_service = EmailService()
