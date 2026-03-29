# 应用配置模块
# 管理应用的所有配置项，所有配置从环境变量/.env文件加载，无硬编码默认值
import os
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """
    应用配置类
    所有配置从环境变量或.env文件加载，生产环境必须正确配置
    """
    # 应用基础配置
    PROJECT_NAME: str
    VERSION: str
    API_V1_PREFIX: str
    DEBUG: bool = False

    # 数据库配置
    DATABASE_URL: str

    # JWT 认证配置
    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str
    ACCESS_TOKEN_EXPIRE_HOURS: int

    # 管理员密钥（用于 AI 账号创建）
    ADMIN_KEY: str

    # SMTP 邮件服务配置
    SMTP_HOST: str
    SMTP_PORT: int
    SMTP_USER: str
    SMTP_PASSWORD: str
    SMTP_USE_SSL: bool
    SMTP_SENDER_NAME: str
    SMTP_SENDER_EMAIL: str

    # 邮箱验证码配置
    EMAIL_CODE_EXPIRE_MINUTES: int
    EMAIL_CODE_SEND_INTERVAL_MINUTES: int
    EMAIL_CODE_DAILY_LIMIT: int
    EMAIL_CODE_MAX_ATTEMPTS: int

    # 头像上传配置
    AVATAR_UPLOAD_DIR: str = "uploads/avatars"
    MAX_AVATAR_SIZE: int = 5 * 1024 * 1024  # 5MB
    ALLOWED_AVATAR_TYPES: list = ["image/jpeg", "image/png", "image/gif", "image/webp"]

    # 服务器配置
    SERVER_HOST: str = "0.0.0.0"
    SERVER_PORT: int = 8000

    class Config:
        # 指定从.env文件读取环境变量
        env_file = ".env"
        # 允许从环境变量读取（优先级高于.env文件）
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    """
    获取配置单例

    使用 lru_cache 缓存配置实例，避免重复加载

    Returns:
        Settings 配置实例
    """
    return Settings()
