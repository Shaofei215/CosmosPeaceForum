# 应用配置模块
# 管理应用的所有配置项，所有配置从环境变量/social_platform/.env文件加载
import secrets
from functools import lru_cache
from pathlib import Path
from typing import Literal, Optional

from pydantic import Field, PrivateAttr, field_validator, model_validator
from pydantic_settings import BaseSettings

from social_platform.app.core.runtime_secrets import resolve_persistent_secrets


_DEFAULT_RUNTIME_SECRETS_PATH = (
    Path(__file__).resolve().parents[1] / "data" / "generated_secrets.json"
)
_DEFAULT_LOG_DIR = Path(__file__).resolve().parents[1] / "data" / "logs"
_JWT_SECRET_PLACEHOLDERS = {"change-this-to-a-long-random-secret"}
_PASSWORD_PLACEHOLDERS = {"ChangeMe123!"}


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
    # 仅用于兼容尚未删除旧变量的现有 .env；标题改用 PLATFORM_DISPLAY_NAME，版本固定在 main.py。
    legacy_project_name: str | None = Field(
        default=None,
        validation_alias="PROJECT_NAME",
        exclude=True,
    )
    legacy_version: str | None = Field(
        default=None,
        validation_alias="VERSION",
        exclude=True,
    )
    # 平台对外展示名，用于网页标题、邮件模板和系统提示词等可品牌化位置。
    PLATFORM_DISPLAY_NAME: str = "宇宙和平论坛"
    # 平台外文名，用于生成只允许 ASCII 字符的 Skill 机器标识与下载文件名。
    PLATFORM_ENGLISH_NAME: str = "Cosmos Peace Forum"
    API_V1_PREFIX: str
    # 浏览器可访问的公开平台前端 origin。当前主要供 agents/.env 同名配置对齐，
    # 同时用于生成公共 Skill 中的公开平台 API 地址。
    SOCIAL_PLATFORM_FRONTEND_URL: str = "http://localhost:8000"
    # 外部 Agent 从其宿主环境访问的公开工具网关根地址。个人模式与生产模式
    # 网络拓扑不同，因此必须作为独立配置，不能从公开平台 origin 推断。
    EXTERNAL_AGENT_API_BASE_URL: str = "http://localhost:8001/external/v1"

    DATABASE_URL: str

    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str
    ACCESS_TOKEN_EXPIRE_HOURS: int
    # 新会话机制使用分钟级 access token；HOURS 保留给旧调用的兼容 fallback。
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_HOURS: int = 12
    REMEMBER_ME_REFRESH_TOKEN_EXPIRE_DAYS: int = 30
    # 平台内管理员会话更短，refresh 生命周期由 remember_me 决定。
    ADMIN_ACCESS_TOKEN_EXPIRE_MINUTES: int = 10
    ADMIN_REFRESH_TOKEN_EXPIRE_HOURS: int = 8
    ADMIN_REMEMBER_ME_REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    # AI Agent 不参与真人 mobile/desktop 互斥，保留较长单次任务窗口。
    AI_ACCESS_TOKEN_EXPIRE_HOURS: int = 24
    AI_REFRESH_TOKEN_EXPIRE_HOURS: int = 24

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
    # 开启后，真人注册必须提交与邮箱绑定的邀请码。
    INVITATION_REGISTRATION_ENABLED: bool = False

    # 达到该点踩人数后，帖子自动归档并向作者发送站内管理通知。
    POST_DISLIKE_ARCHIVE_THRESHOLD: int = Field(default=10, ge=1)

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

    # 运行日志配置。目录位于现有持久化 data volume 内。
    LOG_LEVEL: str = "INFO"
    LOG_DIR: str = str(_DEFAULT_LOG_DIR)
    LOG_RETENTION_DAYS: int = Field(default=30, ge=1)
    LOG_SEGMENT_MAX_MB: int = Field(default=50, ge=1)
    LOG_MAX_TOTAL_MB: int = Field(default=512, ge=1)

    # 公开平台管理器初始管理员。首次启动会创建该账号，并强制登录后修改。
    PLATFORM_ADMIN_INITIAL_USERNAME: str = Field(
        default="platform_admin",
        min_length=1,
        max_length=30,
    )
    PLATFORM_ADMIN_INITIAL_PASSWORD: str = "ChangeMe123!"

    _platform_admin_password_was_generated: bool = PrivateAttr(default=False)

    @field_validator("PLATFORM_ADMIN_INITIAL_USERNAME", mode="before")
    @classmethod
    def normalize_platform_admin_username(cls, value: str) -> str:
        """初始管理员用户名沿用平台管理员 1–30 字和 trim 约束。"""

        normalized = value.strip()
        if not normalized:
            raise ValueError("PLATFORM_ADMIN_INITIAL_USERNAME 不能为空")
        return normalized

    @field_validator("LOG_LEVEL", mode="before")
    @classmethod
    def normalize_log_level(cls, value: str) -> str:
        """校验并规范化标准日志级别。"""

        normalized = str(value).strip().upper()
        if normalized not in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}:
            raise ValueError("LOG_LEVEL 必须是 DEBUG/INFO/WARNING/ERROR/CRITICAL")
        return normalized

    @field_validator("LOG_DIR", mode="before")
    @classmethod
    def normalize_log_dir(cls, value: str | None) -> str:
        """空目录配置回退到公开平台持久化数据目录。"""

        normalized = str(value or "").strip()
        return normalized or str(_DEFAULT_LOG_DIR)

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

    @property
    def platform_admin_password_was_generated(self) -> bool:
        """返回平台初始管理员密码是否由本进程自动生成。

        Returns:
            bool: 使用空值或示例默认值触发自动生成时为 ``True``。
        """

        return self._platform_admin_password_was_generated

    class Config:
        env_file = find_env_file()
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    settings = Settings()  # pyright: ignore[reportCallIssue] -- 字段由 BaseSettings 从环境读取。
    return finalize_runtime_secrets(settings)


def finalize_runtime_secrets(
    settings: Settings,
    secret_file: Path = _DEFAULT_RUNTIME_SECRETS_PATH,
) -> Settings:
    """将不安全的示例值替换为运行期 JWT secret 和一次性管理员密码。

    JWT secret 需要跨重启稳定，因此写入公开平台数据目录；初始管理员密码只用于
    创建首个账号，不写入运行期密钥文件，并由启动流程在确实创建账号时输出。

    Args:
        settings: 已完成环境变量解析和类型校验的公开平台配置。
        secret_file: 自动生成 JWT secret 的持久化文件，测试可传入临时路径。

    Returns:
        Settings: 已就地替换不安全示例值的同一配置实例。

    Raises:
        RuntimeError: 已有运行期密钥文件损坏时抛出。
        OSError: 运行期密钥无法安全持久化时抛出。
    """

    resolved_values, _ = resolve_persistent_secrets(
        {"JWT_SECRET_KEY": settings.JWT_SECRET_KEY},
        {"JWT_SECRET_KEY": _JWT_SECRET_PLACEHOLDERS},
        secret_file,
    )
    settings.JWT_SECRET_KEY = resolved_values["JWT_SECRET_KEY"]

    normalized_admin_password = settings.PLATFORM_ADMIN_INITIAL_PASSWORD.strip()
    if not normalized_admin_password or normalized_admin_password in _PASSWORD_PLACEHOLDERS:
        # 24 个随机字节编码后恰为 32 个 URL-safe 字符，满足管理端密码长度上限。
        settings.PLATFORM_ADMIN_INITIAL_PASSWORD = secrets.token_urlsafe(24)
        settings._platform_admin_password_was_generated = True
    return settings
