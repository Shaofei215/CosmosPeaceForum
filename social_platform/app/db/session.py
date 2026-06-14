"""公开平台数据库会话管理。

本模块根据配置创建 SQLAlchemy Engine 与会话工厂。对于本地文件型 SQLite，
会在创建 Engine 前自动创建数据库文件的父目录，保证新 clone 仓库后可直接启动。
"""

from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker, declarative_base

from social_platform.app.core.config import get_settings

# 获取应用配置
settings = get_settings()


def _ensure_sqlite_database_dir(database_url: str) -> None:
    """确保文件型 SQLite 数据库的父目录存在。

    Args:
        database_url: SQLAlchemy 数据库连接 URL。

    Notes:
        只处理 ``sqlite:///path/to/file.db`` 或 ``sqlite+pysqlite:///...`` 这类
        本地文件数据库；``sqlite://`` 和 ``sqlite:///:memory:`` 不需要创建目录。
    """

    url = make_url(database_url)
    if url.get_backend_name() != "sqlite" or not url.database or url.database == ":memory:":
        return

    db_path = Path(url.database).expanduser()
    if db_path.parent == Path("."):
        return
    db_path.parent.mkdir(parents=True, exist_ok=True)


def _connect_args(database_url: str) -> dict:
    """返回特定数据库驱动需要的 SQLAlchemy 连接参数。

    Args:
        database_url: SQLAlchemy 数据库连接 URL。

    Returns:
        dict: 传递给 ``create_engine`` 的 ``connect_args``。
    """

    if database_url.startswith("sqlite"):
        return {"check_same_thread": False}
    return {}


_ensure_sqlite_database_dir(settings.DATABASE_URL)

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
