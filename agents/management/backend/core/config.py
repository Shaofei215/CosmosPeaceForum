"""
Management Backend - 核心配置模块

agents 侧的基础设施与敏感配置统一从环境变量或 agents/.env 读取，
不写入 management SQLite 配置表。
"""

import os
from functools import lru_cache
from pathlib import Path


def find_env_file() -> Path | None:
    """查找 agents 自己的 .env 文件，不读取其他 .env。"""
    repo_root = Path(__file__).resolve().parents[4]
    candidates = [
        Path.cwd() / "agents" / ".env",
        repo_root / "agents" / ".env",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


@lru_cache(maxsize=1)
def _read_env_file() -> dict[str, str]:
    env_file = find_env_file()
    if env_file is None:
        return {}

    values: dict[str, str] = {}
    for raw_line in env_file.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        values[key] = value
    return values


def _get_env(name: str, default: str = "") -> str:
    if name in os.environ:
        return os.environ[name]
    return _read_env_file().get(name, default)


def _get_int_env(name: str, default: int) -> int:
    value = _get_env(name, str(default))
    try:
        return int(value)
    except ValueError:
        return default


def _sqlite_url_to_path(database_url: str) -> str:
    prefix = "sqlite:///"
    if database_url.startswith(prefix):
        return database_url[len(prefix):]
    return database_url


# JWT 认证配置
MANAGEMENT_JWT_SECRET_KEY = _get_env(
    "MANAGEMENT_JWT_SECRET_KEY",
    "change-this-local-management-jwt-secret",
)
MANAGEMENT_JWT_ALGORITHM = _get_env("MANAGEMENT_JWT_ALGORITHM", "HS256")
MANAGEMENT_ACCESS_TOKEN_EXPIRE_HOURS = _get_int_env(
    "MANAGEMENT_ACCESS_TOKEN_EXPIRE_HOURS",
    720,
)
# 新 management session 机制使用分钟级 access token；旧 HOURS 配置仅保留兼容。
MANAGEMENT_ACCESS_TOKEN_EXPIRE_MINUTES = _get_int_env(
    "MANAGEMENT_ACCESS_TOKEN_EXPIRE_MINUTES",
    10,
)
# 未勾选 remember me 时，管理端 refresh/session 只保留短窗口。
MANAGEMENT_REFRESH_TOKEN_EXPIRE_HOURS = _get_int_env(
    "MANAGEMENT_REFRESH_TOKEN_EXPIRE_HOURS",
    8,
)
# 勾选 remember me 时，管理端 refresh/session 延长到天级窗口。
MANAGEMENT_REMEMBER_ME_REFRESH_TOKEN_EXPIRE_DAYS = _get_int_env(
    "MANAGEMENT_REMEMBER_ME_REFRESH_TOKEN_EXPIRE_DAYS",
    7,
)

# 管理员初始账号（首次启动使用）。优先读取环境变量，其次读取 agents/.env。
MANAGEMENT_ADMIN_USERNAME = _get_env(
    "MANAGEMENT_ADMIN_INITIAL_USERNAME",
    _get_env("MANAGEMENT_ADMIN_USERNAME", "management_admin"),
)
MANAGEMENT_ADMIN_PASSWORD = _get_env(
    "MANAGEMENT_ADMIN_INITIAL_PASSWORD",
    _get_env("MANAGEMENT_ADMIN_PASSWORD", "ChangeMe123!"),
)

# 服务器配置
MANAGEMENT_SERVER_HOST = _get_env("MANAGEMENT_SERVER_HOST", "0.0.0.0")
MANAGEMENT_SERVER_PORT = _get_int_env("MANAGEMENT_SERVER_PORT", 8001)

# 数据库路径。当前 management 后端只支持 SQLite。
_DEFAULT_MANAGEMENT_DB_PATH = str(Path(__file__).parent.parent.parent / "data" / "management.db")
_MANAGEMENT_DB_PATH_ENV = _get_env("MANAGEMENT_DB_PATH", "")
_MANAGEMENT_DATABASE_URL_ENV = _get_env("MANAGEMENT_DATABASE_URL", "")
if _MANAGEMENT_DB_PATH_ENV:
    MANAGEMENT_DB_PATH = _MANAGEMENT_DB_PATH_ENV
    MANAGEMENT_DATABASE_URL = f"sqlite:///{MANAGEMENT_DB_PATH}"
elif _MANAGEMENT_DATABASE_URL_ENV:
    MANAGEMENT_DATABASE_URL = _MANAGEMENT_DATABASE_URL_ENV
    MANAGEMENT_DB_PATH = _sqlite_url_to_path(MANAGEMENT_DATABASE_URL)
else:
    MANAGEMENT_DB_PATH = _DEFAULT_MANAGEMENT_DB_PATH
    MANAGEMENT_DATABASE_URL = f"sqlite:///{MANAGEMENT_DB_PATH}"

# social_platform 连接与 AI 用户基础配置
SOCIAL_PLATFORM_API_BASE_URL = _get_env(
    "SOCIAL_PLATFORM_API_BASE_URL",
    "http://localhost:8000/api/v1",
).rstrip("/")
SOCIAL_PALTFORM_FRONTEND_URL = _get_env(
    "SOCIAL_PALTFORM_FRONTEND_URL",
    "http://localhost:8000",
).rstrip("/")
ADMIN_KEY = _get_env("ADMIN_KEY", "")
AI_USER_PASSWORD = _get_env("AI_USER_PASSWORD", "ChangeMe123!")
LOG_LEVEL = _get_env("LOG_LEVEL", "INFO")
PLATFORM_DISPLAY_NAME = _get_env("PLATFORM_DISPLAY_NAME", "宇宙和平论坛").strip() or "宇宙和平论坛"

# Scheduler 内部接口端口
SCHEDULER_INTERNAL_HOST = _get_env("SCHEDULER_INTERNAL_HOST", "127.0.0.1")
SCHEDULER_INTERNAL_PORT = _get_int_env("SCHEDULER_INTERNAL_PORT", 8002)
SCHEDULER_INTERNAL_BASE_URL = _get_env(
    "SCHEDULER_INTERNAL_BASE_URL",
    f"http://{SCHEDULER_INTERNAL_HOST}:{SCHEDULER_INTERNAL_PORT}",
).rstrip("/")


class Settings:
    """配置类，封装所有配置参数"""
    
    # JWT 认证配置
    jwt_secret_key: str = MANAGEMENT_JWT_SECRET_KEY
    jwt_algorithm: str = MANAGEMENT_JWT_ALGORITHM
    jwt_access_token_expire_hours: int = MANAGEMENT_ACCESS_TOKEN_EXPIRE_HOURS
    jwt_access_token_expire_minutes: int = MANAGEMENT_ACCESS_TOKEN_EXPIRE_MINUTES
    refresh_token_expire_hours: int = MANAGEMENT_REFRESH_TOKEN_EXPIRE_HOURS
    remember_me_refresh_token_expire_days: int = MANAGEMENT_REMEMBER_ME_REFRESH_TOKEN_EXPIRE_DAYS
    
    # 管理员初始账号
    admin_username: str = MANAGEMENT_ADMIN_USERNAME
    admin_password: str = MANAGEMENT_ADMIN_PASSWORD
    
    # 服务器配置
    server_host: str = MANAGEMENT_SERVER_HOST
    server_port: int = MANAGEMENT_SERVER_PORT
    
    # 数据库路径
    db_path: str = MANAGEMENT_DB_PATH
    database_url: str = MANAGEMENT_DATABASE_URL

    # social_platform 连接与 AI 用户基础配置
    social_platform_api_base_url: str = SOCIAL_PLATFORM_API_BASE_URL
    social_platform_frontend_url: str = SOCIAL_PALTFORM_FRONTEND_URL
    admin_key: str = ADMIN_KEY
    ai_user_password: str = AI_USER_PASSWORD
    log_level: str = LOG_LEVEL
    platform_display_name: str = PLATFORM_DISPLAY_NAME
    
    # Scheduler 内部接口端口
    scheduler_internal_host: str = SCHEDULER_INTERNAL_HOST
    scheduler_internal_port: int = SCHEDULER_INTERNAL_PORT
    scheduler_internal_base_url: str = SCHEDULER_INTERNAL_BASE_URL
    
    def get_db_path(self) -> str:
        """获取 SQLite 数据库路径"""
        return self.db_path

    def get_database_url(self) -> str:
        """获取 SQLAlchemy 数据库 URL"""
        return self.database_url


def get_config() -> Settings:
    """获取配置实例"""
    return Settings()


def get_db_path() -> str:
    """获取 SQLite 数据库路径"""
    return MANAGEMENT_DB_PATH
