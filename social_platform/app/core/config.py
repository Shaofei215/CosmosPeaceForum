# 应用配置模块
# 管理应用的所有配置项，所有配置从环境变量/social_platform/.env文件加载
from pathlib import Path
from functools import lru_cache
from typing import Literal, Optional

from pydantic import model_validator
from pydantic_settings import BaseSettings


def find_env_file() -> str:
    """
    查找 .env 文件的位置
    social_platform 独立读取 social_platform/.env，不再回退到项目根目录 .env。
    """
    current_dir = Path.cwd()
    social_platform_dir = Path(__file__).resolve().parents[2]

    candidates = [
        current_dir / "social_platform" / ".env",
        current_dir / ".env" if current_dir.name == "social_platform" else None,
        social_platform_dir / ".env",
    ]

    for candidate in candidates:
        if candidate and candidate.exists():
            return str(candidate)

    return str(social_platform_dir / ".env")


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
    AVATAR_STORAGE_STRATEGY: Literal["local", "object_storage"] = "local"
    MAX_AVATAR_SIZE: int = 5 * 1024 * 1024
    ALLOWED_AVATAR_TYPES: list = ["image/jpeg", "image/png", "image/gif", "image/webp"]

    OBJECT_STORAGE_ENDPOINT_URL: Optional[str] = None
    OBJECT_STORAGE_ACCESS_KEY_ID: Optional[str] = None
    OBJECT_STORAGE_SECRET_ACCESS_KEY: Optional[str] = None
    OBJECT_STORAGE_BUCKET: Optional[str] = None
    OBJECT_STORAGE_REGION: str = "us-east-1"
    OBJECT_STORAGE_PUBLIC_BASE_URL: Optional[str] = None
    OBJECT_STORAGE_AVATAR_PREFIX: str = "avatars"
    OBJECT_STORAGE_FORCE_PATH_STYLE: bool = True
    OBJECT_STORAGE_PUBLIC_READ: bool = False

    SERVER_HOST: str = "0.0.0.0"
    SERVER_PORT: int = 8000

    # 公开平台管理器初始管理员。首次启动会创建该账号，并强制登录后修改。
    PLATFORM_ADMIN_INITIAL_USERNAME: str = "platform_admin"
    PLATFORM_ADMIN_INITIAL_PASSWORD: str = "ChangeMe123!"

    @model_validator(mode="after")
    def validate_avatar_storage_settings(self):
        if self.AVATAR_STORAGE_STRATEGY != "object_storage":
            return self

        required_fields = {
            "OBJECT_STORAGE_ENDPOINT_URL": self.OBJECT_STORAGE_ENDPOINT_URL,
            "OBJECT_STORAGE_ACCESS_KEY_ID": self.OBJECT_STORAGE_ACCESS_KEY_ID,
            "OBJECT_STORAGE_SECRET_ACCESS_KEY": self.OBJECT_STORAGE_SECRET_ACCESS_KEY,
            "OBJECT_STORAGE_BUCKET": self.OBJECT_STORAGE_BUCKET,
        }
        missing_fields = [field for field, value in required_fields.items() if not value]
        if missing_fields:
            raise ValueError(
                "AVATAR_STORAGE_STRATEGY=object_storage 时必须配置："
                + ", ".join(missing_fields)
            )

        self.OBJECT_STORAGE_AVATAR_PREFIX = self.OBJECT_STORAGE_AVATAR_PREFIX.strip("/")
        if self.OBJECT_STORAGE_PUBLIC_BASE_URL:
            self.OBJECT_STORAGE_PUBLIC_BASE_URL = self.OBJECT_STORAGE_PUBLIC_BASE_URL.rstrip("/")
        if self.OBJECT_STORAGE_ENDPOINT_URL:
            self.OBJECT_STORAGE_ENDPOINT_URL = self.OBJECT_STORAGE_ENDPOINT_URL.rstrip("/")
        return self

    class Config:
        env_file = find_env_file()
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
