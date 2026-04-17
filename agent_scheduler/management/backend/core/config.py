"""
Management Backend - 核心配置模块
仅包含基础设施参数，业务配置均通过数据库存储

配置加载优先级：
1. 数据库（主存储）
2. 环境变量（仅基础设施）
3. 代码默认值
"""

import os
from pathlib import Path


def _load_env_file(env_path: str = None) -> None:
    """从 .env 文件加载环境配置到 os.environ"""
    if env_path is None:
        scheduler_dir = Path(__file__).parent.parent.parent.parent
        env_path = str(scheduler_dir / ".env")

    if not os.path.exists(env_path):
        return

    try:
        with open(env_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#') or '=' not in line:
                    continue
                key, value = line.split('=', 1)
                key = key.strip()
                if key not in os.environ:
                    os.environ[key] = value.strip()
    except Exception:
        pass


def _ensure_encryption_key() -> str:
    """确保 ENCRYPTION_KEY 存在，不存在则生成"""
    key = os.environ.get("ENCRYPTION_KEY", "")
    if not key:
        from cryptography.fernet import Fernet
        key = Fernet.generate_key().decode()
        print(f"[配置][警告] 未设置 ENCRYPTION_KEY，已自动生成: {key[:16]}...")
    return key


_load_env_file()

# ==================== 基础设施参数（仅环境变量） ====================

# 加密配置
ENCRYPTION_KEY = _ensure_encryption_key()

# JWT 认证配置
MANAGEMENT_JWT_SECRET_KEY = os.environ.get("MANAGEMENT_JWT_SECRET_KEY", "dev-secret-key-change-in-production")
MANAGEMENT_JWT_ALGORITHM = os.environ.get("MANAGEMENT_JWT_ALGORITHM", "HS256")
MANAGEMENT_ACCESS_TOKEN_EXPIRE_HOURS = int(os.environ.get("MANAGEMENT_ACCESS_TOKEN_EXPIRE_HOURS", "720"))

# 管理员初始账号（首次启动使用）
MANAGEMENT_ADMIN_USERNAME = os.environ.get("MANAGEMENT_ADMIN_USERNAME", "admin")
MANAGEMENT_ADMIN_PASSWORD = os.environ.get("MANAGEMENT_ADMIN_PASSWORD", "Level999")

# 服务器配置
MANAGEMENT_SERVER_HOST = os.environ.get("MANAGEMENT_SERVER_HOST", "0.0.0.0")
MANAGEMENT_SERVER_PORT = int(os.environ.get("MANAGEMENT_SERVER_PORT", "8001"))

# 数据库路径（可选，默认使用 management/data/management.db）
MANAGEMENT_DB_PATH = os.environ.get("MANAGEMENT_DB_PATH", "")

# Scheduler 内部接口端口（可选）
SCHEDULER_INTERNAL_PORT = int(os.environ.get("SCHEDULER_INTERNAL_PORT", "8002"))


class Settings:
    """配置类，封装所有配置参数"""
    
    # 加密配置
    encryption_key: str = ENCRYPTION_KEY
    
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
        if self.db_path:
            return self.db_path
        management_dir = Path(__file__).parent.parent.parent / "data"
        management_dir.mkdir(parents=True, exist_ok=True)
        return str(management_dir / "management.db")


def get_config() -> Settings:
    """获取配置实例"""
    return Settings()


def get_db_path() -> str:
    """获取 SQLite 数据库路径"""
    if MANAGEMENT_DB_PATH:
        return MANAGEMENT_DB_PATH
    management_dir = Path(__file__).parent.parent.parent / "data"
    management_dir.mkdir(parents=True, exist_ok=True)
    return str(management_dir / "management.db")
