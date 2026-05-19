"""
Management Backend - 核心配置模块
"""

import logging
import os
import secrets
from functools import lru_cache
from pathlib import Path

logger = logging.getLogger(__name__)


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


def _get_or_generate_jwt_secret() -> str:
    """
    获取或自动生成 JWT 密钥
    
    优先级：
    1. 环境变量 MANAGEMENT_JWT_SECRET_KEY（可选，允许生产环境覆盖）
    2. 数据目录下的 .jwt_secret 文件
    3. 自动生成并保存到 .jwt_secret 文件
    """
    # 1. 优先使用环境变量（生产环境可配置）
    env_key = _get_env("MANAGEMENT_JWT_SECRET_KEY", "")
    if env_key:
        return env_key
    
    # 2. 读取或生成密钥文件
    management_dir = Path(__file__).parent.parent.parent / "data"
    management_dir.mkdir(parents=True, exist_ok=True)
    secret_file = management_dir / ".jwt_secret"
    
    if secret_file.exists():
        return secret_file.read_text().strip()
    
    # 3. 生成新密钥并保存
    new_secret = secrets.token_hex(32)
    secret_file.write_text(new_secret)
    try:
        secret_file.chmod(0o600)  # 仅所有者可读写
    except NotImplementedError:
        # Windows 不支持 chmod
        pass
    logger.info("已自动生成 JWT 密钥并保存到: %s", secret_file)
    return new_secret


# JWT 认证配置
MANAGEMENT_JWT_SECRET_KEY = _get_or_generate_jwt_secret()
MANAGEMENT_JWT_ALGORITHM = "HS256"
MANAGEMENT_ACCESS_TOKEN_EXPIRE_HOURS = 720

# 管理员初始账号（首次启动使用）。优先读取环境变量，其次读取 agents/.env。
MANAGEMENT_ADMIN_USERNAME = _get_env(
    "MANAGEMENT_ADMIN_INITIAL_USERNAME",
    _get_env("MANAGEMENT_ADMIN_USERNAME", "sliverwolf"),
)
MANAGEMENT_ADMIN_PASSWORD = _get_env(
    "MANAGEMENT_ADMIN_INITIAL_PASSWORD",
    _get_env("MANAGEMENT_ADMIN_PASSWORD", "Level999"),
)

# 服务器配置
MANAGEMENT_SERVER_HOST = _get_env("MANAGEMENT_SERVER_HOST", "0.0.0.0")
MANAGEMENT_SERVER_PORT = int(_get_env("MANAGEMENT_SERVER_PORT", "8001"))

# 数据库路径
MANAGEMENT_DB_PATH = _get_env(
    "MANAGEMENT_DB_PATH",
    str(Path(__file__).parent.parent.parent / "data" / "management.db"),
)

# Scheduler 内部接口端口
SCHEDULER_INTERNAL_PORT = int(_get_env("SCHEDULER_INTERNAL_PORT", "8002"))


class Settings:
    """配置类，封装所有配置参数"""
    
    # JWT 认证配置
    jwt_secret_key: str = MANAGEMENT_JWT_SECRET_KEY
    jwt_algorithm: str = MANAGEMENT_JWT_ALGORITHM
    jwt_access_token_expire_hours: int = MANAGEMENT_ACCESS_TOKEN_EXPIRE_HOURS
    
    # 管理员初始账号
    admin_username: str = MANAGEMENT_ADMIN_USERNAME
    admin_password: str = MANAGEMENT_ADMIN_PASSWORD
    
    # 服务器配置
    server_host: str = MANAGEMENT_SERVER_HOST
    server_port: int = MANAGEMENT_SERVER_PORT
    
    # 数据库路径
    db_path: str = MANAGEMENT_DB_PATH
    
    # Scheduler 内部接口端口
    scheduler_internal_port: int = SCHEDULER_INTERNAL_PORT
    
    def get_db_path(self) -> str:
        """获取 SQLite 数据库路径"""
        return self.db_path


def get_config() -> Settings:
    """获取配置实例"""
    return Settings()


def get_db_path() -> str:
    """获取 SQLite 数据库路径"""
    return MANAGEMENT_DB_PATH
