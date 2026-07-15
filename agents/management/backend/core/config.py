"""
Agents 核心配置模块

agents 侧的基础设施与敏感配置统一从环境变量或 agents/.env 读取。
"""

from functools import lru_cache
from pathlib import Path

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


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
    server_host: str = Field(default="0.0.0.0", validation_alias="MANAGEMENT_SERVER_HOST")
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


@lru_cache(maxsize=1)
def get_config() -> Settings:
    """获取进程内缓存的配置实例。

    Returns:
        Settings: 首次调用时从环境变量与 agents/.env 构建的配置实例。
    """
    return Settings()


def get_db_path() -> str:
    """获取 SQLite 数据库路径。

    Returns:
        str: 当前 Management 配置使用的 SQLite 数据库文件路径。
    """
    return get_config().get_db_path()
