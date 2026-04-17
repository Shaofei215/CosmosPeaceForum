"""
Management Backend - 数据库连接管理
使用 SQLModel (SQLAlchemy) 管理 SQLite 数据库连接
"""

from sqlmodel import SQLModel, Session, create_engine
from sqlalchemy.orm import sessionmaker

from agent_scheduler.management.backend.core.config import get_config

_engine = None
_SessionLocal = None


def get_engine():
    """获取 SQLAlchemy 引擎（单例）"""
    global _engine
    if _engine is None:
        config = get_config()
        db_path = config.get_db_path()
        connect_args = {"check_same_thread": False}
        _engine = create_engine(
            f"sqlite:///{db_path}",
            connect_args=connect_args,
            echo=False,
        )
    return _engine


def get_session_local():
    """获取会话工厂（单例）"""
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(
            class_=Session,
            autocommit=False,
            autoflush=False,
            bind=get_engine(),
        )
    return _SessionLocal


def init_db():
    """初始化数据库（创建所有表）"""
    engine = get_engine()
    SQLModel.metadata.create_all(engine)
    print(f"[数据库] 表结构初始化完成: {get_config().get_db_path()}")


def get_db():
    """获取数据库会话（用于 FastAPI 依赖注入）"""
    session = get_session_local()()
    try:
        yield session
    finally:
        session.close()
