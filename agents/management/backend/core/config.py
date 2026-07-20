"""
Agents 核心配置模块

agents 侧的基础设施与敏感配置统一从环境变量或 agents/.env 读取。
"""

import secrets
from functools import lru_cache
from pathlib import Path

from pydantic import Field, PrivateAttr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from agents.management.backend.core.runtime_secrets import resolve_persistent_secrets


def find_env_file() -> Path | None:
    """查找 .env 文件。"""
    repo_root = Path(__file__).resolve().parents[4]
    candidates = [
        Path.cwd() / "agents" / ".env",
        repo_root / "agents" / ".env",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def _sqlite_url_to_path(database_url: str) -> str:
    """从 SQLite 数据库 URL 中提取文件路径。

    Args:
        database_url: SQLite URL 或已经是文件路径的字符串。

    Returns:
        str: 移除 ``sqlite:///`` 前缀后的路径；没有该前缀时原样返回。
    """
    prefix = "sqlite:///"
    if database_url.startswith(prefix):
        # 使用切片而非 replace，确保只移除开头且仅移除一次协议前缀。
        return database_url[len(prefix):]
    return database_url


_DEFAULT_MANAGEMENT_DB_PATH = str(Path(__file__).parent.parent.parent / "data" / "management.db")
_DEFAULT_RUNTIME_SECRETS_PATH = (
    Path(__file__).resolve().parents[2] / "data" / "generated_secrets.json"
)
_DEFAULT_LOG_DIR = Path(__file__).resolve().parents[2] / "data" / "logs"
_JWT_SECRET_PLACEHOLDERS = {
    "change-this-to-a-long-random-secret",
    "change-this-local-management-jwt-secret",
}
_PASSWORD_PLACEHOLDERS = {"ChangeMe123!"}


class Settings(BaseSettings):
    """Management 与 Scheduler 共用的基础设施配置。

    配置值按“初始化参数、系统环境变量、agents/.env、字段默认值”的顺序读取，
    并由 Pydantic 完成类型转换与校验。由于 agents/.env 由多个子系统共享，未在
    本模型声明的配置项会被忽略。
    """

    model_config = SettingsConfigDict(
        env_file=find_env_file(),
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
        populate_by_name=True,
    )

    _admin_password_was_generated: bool = PrivateAttr(default=False)

    # JWT 认证配置
    jwt_secret_key: str = Field(
        default="change-this-local-management-jwt-secret",
        validation_alias="MANAGEMENT_JWT_SECRET_KEY",
    )
    jwt_algorithm: str = Field(default="HS256", validation_alias="MANAGEMENT_JWT_ALGORITHM")
    jwt_access_token_expire_minutes: int = Field(
        default=10,
        validation_alias="MANAGEMENT_ACCESS_TOKEN_EXPIRE_MINUTES",
    )
    # 未勾选 remember me 时，管理端 refresh/session 只保留短窗口。
    refresh_token_expire_hours: int = Field(
        default=8,
        validation_alias="MANAGEMENT_REFRESH_TOKEN_EXPIRE_HOURS",
    )
    # 勾选 remember me 时，管理端 refresh/session 延长到天级窗口。
    remember_me_refresh_token_expire_days: int = Field(
        default=7,
        validation_alias="MANAGEMENT_REMEMBER_ME_REFRESH_TOKEN_EXPIRE_DAYS",
    )

    # 管理员初始账号
    admin_username: str = Field(
        default="management_admin",
        validation_alias="MANAGEMENT_ADMIN_INITIAL_USERNAME",
    )
    admin_password: str = Field(
        default="ChangeMe123!",
        validation_alias="MANAGEMENT_ADMIN_INITIAL_PASSWORD",
    )

    # 服务器配置
    server_host: str = Field(default="127.0.0.1", validation_alias="MANAGEMENT_SERVER_HOST")
    server_port: int = Field(default=8001, validation_alias="MANAGEMENT_SERVER_PORT")

    # 数据库配置。MANAGEMENT_DB_PATH 的优先级高于 MANAGEMENT_DATABASE_URL。
    db_path: str = Field(default="", validation_alias="MANAGEMENT_DB_PATH")
    database_url: str = Field(default="", validation_alias="MANAGEMENT_DATABASE_URL")

    # social_platform 连接与 AI 用户基础配置
    social_platform_api_base_url: str = Field(
        default="http://localhost:8000/api/v1",
        validation_alias="SOCIAL_PLATFORM_API_BASE_URL",
    )
    social_platform_frontend_url: str = Field(
        default="http://localhost:8000",
        validation_alias="SOCIAL_PLATFORM_FRONTEND_URL",
    )
    admin_key: str = Field(default="", validation_alias="ADMIN_KEY")
    ai_user_password: str = Field(default="ChangeMe123!", validation_alias="AI_USER_PASSWORD")
    log_level: str = Field(default="INFO", validation_alias="LOG_LEVEL")
    log_dir: str = Field(default=str(_DEFAULT_LOG_DIR), validation_alias="LOG_DIR")
    log_retention_days: int = Field(default=30, ge=1, validation_alias="LOG_RETENTION_DAYS")
    log_segment_max_mb: int = Field(default=50, ge=1, validation_alias="LOG_SEGMENT_MAX_MB")
    log_max_total_mb: int = Field(default=512, ge=1, validation_alias="LOG_MAX_TOTAL_MB")
    platform_display_name: str = Field(
        default="宇宙和平论坛",
        validation_alias="PLATFORM_DISPLAY_NAME",
    )

    # Scheduler 内部接口端口
    scheduler_internal_host: str = Field(
        default="127.0.0.1",
        validation_alias="SCHEDULER_INTERNAL_HOST",
    )
    scheduler_internal_port: int = Field(
        default=8002,
        validation_alias="SCHEDULER_INTERNAL_PORT",
    )
    scheduler_internal_base_url: str = Field(
        default="",
        validation_alias="SCHEDULER_INTERNAL_BASE_URL",
    )

    @field_validator("log_level", mode="before")
    @classmethod
    def normalize_log_level(cls, value: str) -> str:
        """校验并规范化标准日志级别。"""

        normalized = str(value).strip().upper()
        if normalized not in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}:
            raise ValueError("LOG_LEVEL 必须是 DEBUG/INFO/WARNING/ERROR/CRITICAL")
        return normalized

    @field_validator("log_dir", mode="before")
    @classmethod
    def normalize_log_dir(cls, value: str | None) -> str:
        """空目录配置回退到 Management 持久化数据目录。"""

        normalized = str(value or "").strip()
        return normalized or str(_DEFAULT_LOG_DIR)

    @model_validator(mode="after")
    def normalize_dependent_settings(self) -> "Settings":
        """规范化 URL，并补全数据库及 Scheduler 的关联配置。

        Returns:
            Settings: 完成关联字段补全与字符串规范化后的当前配置实例。
        """
        if self.db_path:
            self.database_url = f"sqlite:///{self.db_path}"
        elif self.database_url:
            self.db_path = _sqlite_url_to_path(self.database_url)
        else:
            self.db_path = _DEFAULT_MANAGEMENT_DB_PATH
            self.database_url = f"sqlite:///{self.db_path}"

        self.social_platform_api_base_url = self.social_platform_api_base_url.rstrip("/")
        self.social_platform_frontend_url = self.social_platform_frontend_url.rstrip("/")
        self.platform_display_name = self.platform_display_name.strip() or "宇宙和平论坛"

        if not self.scheduler_internal_base_url:
            self.scheduler_internal_base_url = (
                f"http://{self.scheduler_internal_host}:{self.scheduler_internal_port}"
            )
        self.scheduler_internal_base_url = self.scheduler_internal_base_url.rstrip("/")
        return self

    def get_db_path(self) -> str:
        """获取 SQLite 数据库路径。

        Returns:
            str: SQLite 数据库文件路径。
        """
        return self.db_path

    def get_database_url(self) -> str:
        """获取 SQLAlchemy 数据库 URL。

        Returns:
            str: SQLAlchemy 使用的 SQLite 数据库连接 URL。
        """
        return self.database_url

    @property
    def admin_password_was_generated(self) -> bool:
        """返回初始管理员密码是否由本进程自动生成。

        Returns:
            bool: 使用空值或示例默认值触发自动生成时为 ``True``。
        """

        return self._admin_password_was_generated


def finalize_runtime_secrets(
    settings: Settings,
    secret_file: Path = _DEFAULT_RUNTIME_SECRETS_PATH,
) -> Settings:
    """将不安全的示例值替换为运行期高熵密钥和一次性管理员密码。

    JWT secret 与 AI 用户共用密码需要跨重启稳定，因此写入 Management 数据目录；
    初始管理员密码仅用于创建首个账号，不写入运行期密钥文件，并由初始化流程按需输出。

    Args:
        settings: 已完成环境变量解析和类型校验的 Management 配置。
        secret_file: 自动生成且需要持久化的运行期密钥文件，测试可传入临时路径。

    Returns:
        Settings: 已就地替换不安全示例值的同一配置实例。

    Raises:
        RuntimeError: 已有运行期密钥文件损坏时抛出。
        OSError: 运行期密钥无法安全持久化时抛出。
    """

    resolved_values, _ = resolve_persistent_secrets(
        {
            "MANAGEMENT_JWT_SECRET_KEY": settings.jwt_secret_key,
            "AI_USER_PASSWORD": settings.ai_user_password,
        },
        {
            "MANAGEMENT_JWT_SECRET_KEY": _JWT_SECRET_PLACEHOLDERS,
            "AI_USER_PASSWORD": _PASSWORD_PLACEHOLDERS,
        },
        secret_file,
        token_bytes={
            "MANAGEMENT_JWT_SECRET_KEY": 48,
            # 24 字节编码为 32 字符，满足公开平台用户密码的最大长度约束。
            "AI_USER_PASSWORD": 24,
        },
    )
    settings.jwt_secret_key = resolved_values["MANAGEMENT_JWT_SECRET_KEY"]
    settings.ai_user_password = resolved_values["AI_USER_PASSWORD"]

    normalized_admin_password = settings.admin_password.strip()
    if not normalized_admin_password or normalized_admin_password in _PASSWORD_PLACEHOLDERS:
        # 24 个随机字节编码后恰为 32 个 URL-safe 字符，满足管理端密码长度上限。
        settings.admin_password = secrets.token_urlsafe(24)
        settings._admin_password_was_generated = True
    return settings


@lru_cache(maxsize=1)
def get_config() -> Settings:
    """获取进程内缓存的配置实例。

    Returns:
        Settings: 首次调用时从环境变量与 agents/.env 构建的配置实例。
    """
    return finalize_runtime_secrets(Settings())


def get_db_path() -> str:
    """获取 SQLite 数据库路径。

    Returns:
        str: 当前 Management 配置使用的 SQLite 数据库文件路径。
    """
    return get_config().get_db_path()
