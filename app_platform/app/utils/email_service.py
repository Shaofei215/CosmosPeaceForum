# 邮件服务模块
# 提供基于 SMTP 的邮件发送功能，用于发送验证码邮件
import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from string import Template

from app.core.config import get_settings


settings = get_settings()


# 注册验证码邮件 HTML 模板
# 设计规范参考 frontend/docs/style-guide.md
# - 玻璃态设计：统一毛玻璃效果，无边框无阴影
# - 多层渐变背景
# - 圆角：rounded-xl (12px)
# - 主色调：紫色系
# - 文本框：border-0 shadow-none bg-muted/50 rounded-lg
# - 字体：HYWH65S
EMAIL_REGISTER_TEMPLATE = Template("""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        /* ========== CSS 变量定义（参考 style-guide.md）========== */
        :root {
            --background: 0 0% 100%;
            --foreground: 222.2 84% 4.9%;
            --card: 0 0% 100%;
            --card-foreground: 222.2 84% 4.9%;
            --primary: 222.2 47.4% 11.2%;
            --primary-foreground: 210 40% 98%;
            --secondary: 210 40% 96.1%;
            --muted: 210 40% 96.1%;
            --muted-foreground: 215.4 16.3% 46.9%;
            --theme-primary: 262 83% 58%;
            --theme-primary-light: 262 83% 65%;
            --theme-primary-dark: 262 83% 45%;
            --radius: 0.5rem;
        }

        /* ========== 基础样式 ========== */
        * {
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }

        body {
            font-family: 'HYWH65S', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            line-height: 1.6;
            color: hsl(var(--foreground));
            background-color: hsl(var(--background));
        }

        /* ========== 页面背景（多层渐变，参考 style-guide.md 9.1）========== */
        .page-background {
            background:
                radial-gradient(ellipse at left top, hsl(230 70% 55% / 0.55) 0%, transparent 50%),
                radial-gradient(ellipse at right top, hsl(210 75% 60% / 0.5) 0%, transparent 50%),
                radial-gradient(ellipse at left bottom, hsl(220 70% 62% / 0.5) 0%, transparent 50%),
                radial-gradient(ellipse at right bottom, hsl(200 80% 65% / 0.55) 0%, transparent 50%),
                radial-gradient(ellipse at center, hsl(215 65% 65% / 0.25) 0%, transparent 70%);
            min-height: 100vh;
            padding: 40px 20px;
        }

        /* ========== 容器样式 ========== */
        .container {
            max-width: 600px;
            margin: 0 auto;
        }

        /* ========== 玻璃态卡片（统一毛玻璃，无边框无阴影）========== */
        .glass-card {
            border-radius: 12px;
            background: rgba(255, 255, 255, 0.4);
            backdrop-filter: blur(12px);
            -webkit-backdrop-filter: blur(12px);
            border: none;
            box-shadow: none;
        }

        /* ========== 头部样式 ========== */
        .header {
            background: linear-gradient(135deg, hsl(var(--theme-primary)) 0%, hsl(var(--theme-primary-dark)) 100%);
            color: white;
            padding: 32px 24px;
            text-align: center;
            border-radius: 12px 12px 0 0;
        }

        .header h1 {
            font-size: 24px;
            font-weight: 700;
            line-height: 1.2;
            margin-bottom: 8px;
        }

        .header p {
            font-size: 14px;
            font-weight: 500;
            opacity: 0.9;
        }

        /* ========== 内容区域（毛玻璃）========== */
        .content {
            padding: 32px 24px;
            background: rgba(255, 255, 255, 0.3);
            backdrop-filter: blur(8px);
            -webkit-backdrop-filter: blur(8px);
            border-radius: 0;
        }

        .content p {
            font-size: 14px;
            line-height: 1.6;
            color: hsl(var(--foreground));
            margin-bottom: 16px;
        }

        .content p:last-child {
            margin-bottom: 0;
        }

        /* ========== 验证码输入框样式（参考 style-guide.md 6.2 无边框变体）========== */
        .code-input {
            width: 100%;
            border: 0;
            box-shadow: none;
            background: hsl(var(--muted) / 0.5);
            border-radius: 8px;
            padding: 20px 24px;
            margin: 24px 0;
            text-align: center;
        }

        .code-input:focus {
            outline: none;
            background: hsl(var(--muted) / 0.7);
        }

        .code-text {
            font-size: 32px;
            font-weight: 700;
            color: hsl(var(--theme-primary));
            letter-spacing: 12px;
            border: none;
            background: transparent;
            text-align: center;
            width: 100%;
        }

        .code-text:focus {
            outline: none;
        }

        /* ========== 警告提示 ========== */
        .warning {
            color: hsl(0 84.2% 60.2%);
            font-size: 12px;
            background: hsl(0 84.2% 60.2% / 0.1);
            padding: 12px 16px;
            border-radius: 8px;
            margin-top: 20px;
            text-align: center;
        }

        /* ========== 底部信息 ========== */
        .footer {
            padding: 24px;
            text-align: center;
            background: rgba(255, 255, 255, 0.2);
            backdrop-filter: blur(8px);
            -webkit-backdrop-filter: blur(8px);
            border-radius: 0 0 12px 12px;
        }

        .footer p {
            font-size: 12px;
            color: hsl(var(--muted-foreground));
            line-height: 1.5;
        }

        /* ========== 辅助信息 ========== */
        .meta-info {
            font-size: 12px;
            color: hsl(var(--muted-foreground));
            margin-top: 8px;
            text-align: center;
        }
    </style>
</head>
<body>
    <div class="page-background">
        <div class="container">
            <div class="glass-card">
                <!-- 头部 -->
                <div class="header">
                    <h1>🌳 Herta-Tree</h1>
                    <p>账号注册验证</p>
                </div>

                <!-- 内容 -->
                <div class="content">
                    <p>您好，</p>
                    <p>欢迎注册 Herta-Tree 账号！请使用以下验证码完成注册：</p>

                    <!-- 验证码输入框样式 -->
                    <div class="code-input">
                        <input type="text" class="code-text" value="$code" readonly />
                    </div>

                    <!-- 有效期信息 -->
                    <p class="meta-info">验证码将在 $expire_minutes 分钟后过期，请尽快完成验证。</p>

                    <!-- 警告 -->
                    <div class="warning">
                        ⚠️ 请勿将验证码泄露给他人，如有疑虑请忽略此邮件。
                    </div>
                </div>

                <!-- 底部 -->
                <div class="footer">
                    <p>此邮件由 Herta-Tree 系统自动发送，请勿回复。</p>
                </div>
            </div>
        </div>
    </div>
</body>
</html>
""")

# 密码重置验证码邮件 HTML 模板
# 设计规范与注册邮件一致，保持统一的视觉风格
EMAIL_RESET_TEMPLATE = Template("""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        /* ========== CSS 变量定义（参考 style-guide.md）========== */
        :root {
            --background: 0 0% 100%;
            --foreground: 222.2 84% 4.9%;
            --card: 0 0% 100%;
            --card-foreground: 222.2 84% 4.9%;
            --primary: 222.2 47.4% 11.2%;
            --primary-foreground: 210 40% 98%;
            --secondary: 210 40% 96.1%;
            --muted: 210 40% 96.1%;
            --muted-foreground: 215.4 16.3% 46.9%;
            --theme-primary: 262 83% 58%;
            --theme-primary-light: 262 83% 65%;
            --theme-primary-dark: 262 83% 45%;
            --radius: 0.5rem;
        }

        /* ========== 基础样式 ========== */
        * {
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }

        body {
            font-family: 'HYWH65S', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            line-height: 1.6;
            color: hsl(var(--foreground));
            background-color: hsl(var(--background));
        }

        /* ========== 页面背景（多层渐变）========== */
        .page-background {
            background:
                radial-gradient(ellipse at left top, hsl(230 70% 55% / 0.55) 0%, transparent 50%),
                radial-gradient(ellipse at right top, hsl(210 75% 60% / 0.5) 0%, transparent 50%),
                radial-gradient(ellipse at left bottom, hsl(220 70% 62% / 0.5) 0%, transparent 50%),
                radial-gradient(ellipse at right bottom, hsl(200 80% 65% / 0.55) 0%, transparent 50%),
                radial-gradient(ellipse at center, hsl(215 65% 65% / 0.25) 0%, transparent 70%);
            min-height: 100vh;
            padding: 40px 20px;
        }

        /* ========== 容器样式 ========== */
        .container {
            max-width: 600px;
            margin: 0 auto;
        }

        /* ========== 玻璃态卡片（统一毛玻璃，无边框无阴影）========== */
        .glass-card {
            border-radius: 12px;
            background: rgba(255, 255, 255, 0.4);
            backdrop-filter: blur(12px);
            -webkit-backdrop-filter: blur(12px);
            border: none;
            box-shadow: none;
        }

        /* ========== 头部样式 ========== */
        .header {
            background: linear-gradient(135deg, hsl(var(--theme-primary)) 0%, hsl(var(--theme-primary-dark)) 100%);
            color: white;
            padding: 32px 24px;
            text-align: center;
            border-radius: 12px 12px 0 0;
        }

        .header h1 {
            font-size: 24px;
            font-weight: 700;
            line-height: 1.2;
            margin-bottom: 8px;
        }

        .header p {
            font-size: 14px;
            font-weight: 500;
            opacity: 0.9;
        }

        /* ========== 内容区域（毛玻璃）========== */
        .content {
            padding: 32px 24px;
            background: rgba(255, 255, 255, 0.3);
            backdrop-filter: blur(8px);
            -webkit-backdrop-filter: blur(8px);
            border-radius: 0;
        }

        .content p {
            font-size: 14px;
            line-height: 1.6;
            color: hsl(var(--foreground));
            margin-bottom: 16px;
        }

        .content p:last-child {
            margin-bottom: 0;
        }

        /* ========== 验证码输入框样式（参考 style-guide.md 6.2 无边框变体）========== */
        .code-input {
            width: 100%;
            border: 0;
            box-shadow: none;
            background: hsl(var(--muted) / 0.5);
            border-radius: 8px;
            padding: 20px 24px;
            margin: 24px 0;
            text-align: center;
        }

        .code-input:focus {
            outline: none;
            background: hsl(var(--muted) / 0.7);
        }

        .code-text {
            font-size: 32px;
            font-weight: 700;
            color: hsl(var(--theme-primary));
            letter-spacing: 12px;
            border: none;
            background: transparent;
            text-align: center;
            width: 100%;
        }

        .code-text:focus {
            outline: none;
        }

        /* ========== 警告提示 ========== */
        .warning {
            color: hsl(0 84.2% 60.2%);
            font-size: 12px;
            background: hsl(0 84.2% 60.2% / 0.1);
            padding: 12px 16px;
            border-radius: 8px;
            margin-top: 20px;
            text-align: center;
        }

        /* ========== 底部信息 ========== */
        .footer {
            padding: 24px;
            text-align: center;
            background: rgba(255, 255, 255, 0.2);
            backdrop-filter: blur(8px);
            -webkit-backdrop-filter: blur(8px);
            border-radius: 0 0 12px 12px;
        }

        .footer p {
            font-size: 12px;
            color: hsl(var(--muted-foreground));
            line-height: 1.5;
        }

        /* ========== 辅助信息 ========== */
        .meta-info {
            font-size: 12px;
            color: hsl(var(--muted-foreground));
            margin-top: 8px;
            text-align: center;
        }
    </style>
</head>
<body>
    <div class="page-background">
        <div class="container">
            <div class="glass-card">
                <!-- 头部 -->
                <div class="header">
                    <h1>🌳 Herta-Tree</h1>
                    <p>密码重置验证</p>
                </div>

                <!-- 内容 -->
                <div class="content">
                    <p>您好，</p>
                    <p>您正在重置 Herta-Tree 账号密码。请使用以下验证码完成操作：</p>

                    <!-- 验证码输入框样式 -->
                    <div class="code-input">
                        <input type="text" class="code-text" value="$code" readonly />
                    </div>

                    <!-- 有效期信息 -->
                    <p class="meta-info">验证码将在 $expire_minutes 分钟后过期，请尽快完成验证。</p>

                    <!-- 警告 -->
                    <div class="warning">
                        ⚠️ 请勿将验证码泄露给他人，如果这不是您的操作，请立即检查账号安全。
                    </div>
                </div>

                <!-- 底部 -->
                <div class="footer">
                    <p>此邮件由 Herta-Tree 系统自动发送，请勿回复。</p>
                </div>
            </div>
        </div>
    </div>
</body>
</html>
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
            purpose: 验证码用途，"register" 或 "reset_password"

        Returns:
            bool: 发送成功返回 True，失败返回 False
        """
        try:
            if purpose == "reset_password":
                template = EMAIL_RESET_TEMPLATE
                subject = "【Herta-Tree】密码重置验证码"
            else:
                template = EMAIL_REGISTER_TEMPLATE
                subject = "【Herta-Tree】注册验证码"

            html_content = template.safe_substitute(
                code=code,
                expire_minutes=settings.EMAIL_CODE_EXPIRE_MINUTES
            )

            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = f"{self.sender_name} <{self.sender_email}>"
            msg['To'] = to_email

            html_part = MIMEText(html_content, 'html', 'utf-8')
            msg.attach(html_part)

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


# 邮件服务单例
email_service = EmailService()
