# 应用配置模块
# 管理应用的所有配置项
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """
    应用配置类
    从环境变量或.env 文件加载配置
    """
    # 项目名称
    PROJECT_NAME: str = "Herta-Tree Social Platform"

    # API 版本号
    VERSION: str = "0.1.0"

    # API v1 版本前缀
    API_V1_PREFIX: str = "/api/v1"

    # 数据库连接 URL，默认使用 SQLite
    DATABASE_URL: str = "sqlite:///./herta_tree.db"

    # 调试模式开关
    DEBUG: bool = True

    # JWT 配置
    JWT_SECRET_KEY: str = "your-secret-key-change-in-production"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_HOURS: int = 24

    # 管理员密钥（用于 AI 账号创建）
    ADMIN_KEY: str = "your-admin-key-change-in-production"

    # SMTP 邮件服务配置
    # SMTP 服务器地址
    SMTP_HOST: str = "smtp.qq.com"
    # SMTP 服务器端口（SSL: 465, TLS: 587）
    SMTP_PORT: int = 465
    # SMTP 用户名（通常是邮箱地址）
    SMTP_USER: str = ""
    # SMTP 密码/授权码
    SMTP_PASSWORD: str = ""
    # 是否使用 SSL（true/false）
    SMTP_USE_SSL: bool = True
    # 发件人显示名称
    SMTP_SENDER_NAME: str = "Herta-Tree"
    # 发件人邮箱地址
    SMTP_SENDER_EMAIL: str = "noreply@herta-tree.com"

    # 邮箱验证码配置
    # 验证码有效期（分钟）
    EMAIL_CODE_EXPIRE_MINUTES: int = 10
    # 同一邮箱发送间隔（分钟）
    EMAIL_CODE_SEND_INTERVAL_MINUTES: int = 1
    # 同一邮箱每日最大发送次数
    EMAIL_CODE_DAILY_LIMIT: int = 10
    # 验证码最大尝试次数
    EMAIL_CODE_MAX_ATTEMPTS: int = 5

    class Config:
        # 指定从.env 文件读取环境变量
        env_file = ".env"


@lru_cache()
def get_settings() -> Settings:
    """
    获取配置单例

    使用 lru_cache 缓存配置实例，避免重复加载

    Returns:
        Settings 配置实例
    """
    return Settings()
