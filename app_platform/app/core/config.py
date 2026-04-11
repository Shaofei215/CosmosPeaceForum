# 应用配置模块
# 管理应用的所有配置项，所有配置从环境变量/.env文件加载，无硬编码默认值
import os
from pathlib import Path
from pydantic_settings import BaseSettings
from functools import lru_cache


def find_env_file() -> str:
    """
    查找 .env 文件的位置
    优先查找项目根目录的 .env，如果不存在则查找 app_platform/.env
    """
    current_dir = Path.cwd()

    # 首先检查当前目录下的 .env
    env_in_current = current_dir / ".env"
    if env_in_current.exists():
        return str(env_in_current)

    # 检查当前目录下的 app_platform/.env
    env_in_app = current_dir / "app_platform" / ".env"
    if env_in_app.exists():
        return str(env_in_app)

    # 检查模块所在目录的 app_platform/.env
    module_env = Path(__file__).parent.parent / ".env"
    if module_env.exists():
        return str(module_env)

    # 最后检查模块所在目录的 app_platform/.env
    module_app_env = Path(__file__).parent.parent / "app_platform" / ".env"
    if module_app_env.exists():
        return str(module_app_env)

    # 返回默认路径（pydantic 会报错如果没有找到）
    return ".env"


class Settings(BaseSettings):
    """
    应用配置类
    所有配置从环境变量或.env文件加载，生产环境必须正确配置
    """
    PROJECT_NAME: str
    VERSION: str
    API_V1_PREFIX: str
    DEBUG: bool = False

    DATABASE_URL: str

    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str
    ACCESS_TOKEN_EXPIRE_HOURS: int

    ADMIN_KEY: str

    SMTP_HOST: str
    SMTP_PORT: int
    SMTP_USER: str
    SMTP_PASSWORD: str
    SMTP_USE_SSL: bool
    SMTP_SENDER_NAME: str
    SMTP_SENDER_EMAIL: str

    EMAIL_CODE_EXPIRE_MINUTES: int
    EMAIL_CODE_SEND_INTERVAL_MINUTES: int
    EMAIL_CODE_DAILY_LIMIT: int
    EMAIL_CODE_MAX_ATTEMPTS: int

    AVATAR_UPLOAD_DIR: str = "uploads/avatars"
    MAX_AVATAR_SIZE: int = 5 * 1024 * 1024
    ALLOWED_AVATAR_TYPES: list = ["image/jpeg", "image/png", "image/gif", "image/webp"]

    SERVER_HOST: str = "0.0.0.0"
    SERVER_PORT: int = 8000

    class Config:
        env_file = find_env_file()
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    return Settings()