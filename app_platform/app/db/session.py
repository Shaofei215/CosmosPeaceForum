# 数据库会话管理
# 创建数据库连接和会话工厂
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

from app_platform.app.core.config import get_settings

# 获取应用配置
settings = get_settings()

def _connect_args(database_url: str) -> dict:
    """Return driver-specific SQLAlchemy connect args."""
    if database_url.startswith("sqlite"):
        return {"check_same_thread": False}
    return {}


# 创建数据库引擎
engine = create_engine(
    settings.DATABASE_URL,
    connect_args=_connect_args(settings.DATABASE_URL),
)

# 创建数据库会话工厂
# autocommit=False: 不自动提交事务
# autoflush=False: 不自动刷新
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 创建 ORM 基类
# 所有模型类都继承自这个基类
Base = declarative_base()
