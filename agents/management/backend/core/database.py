"""
Management Backend - 数据库连接管理
使用 SQLModel (SQLAlchemy) 管理 SQLite 数据库连接
"""

import logging
from pathlib import Path
from sqlalchemy import inspect, text
from sqlmodel import SQLModel, Session, create_engine
from sqlalchemy.orm import sessionmaker

from agents.management.backend.core.config import get_config

logger = logging.getLogger(__name__)

_engine = None
_SessionLocal = None


def get_engine():
    """获取 SQLAlchemy 引擎（单例）"""
    global _engine
    if _engine is None:
        config = get_config()
        db_path = config.get_db_path()
        
        # 确保数据库目录存在
        db_dir = Path(db_path).parent
        db_dir.mkdir(parents=True, exist_ok=True)
        
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
    _ensure_lightweight_migrations(engine)
    logger.info("表结构初始化完成: %s", get_config().get_db_path())


def _ensure_lightweight_migrations(engine):
    """补齐 SQLModel create_all 不会更新的旧 SQLite 表字段。"""
    inspector = inspect(engine)
    if "agent_configs" not in inspector.get_table_names():
        return

    columns = {column["name"] for column in inspector.get_columns("agent_configs")}
    if "last_login_at" not in columns:
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE agent_configs ADD COLUMN last_login_at DATETIME"))
        logger.info("已为 agent_configs 添加 last_login_at 字段")


def get_db():
    """获取数据库会话（用于 FastAPI 依赖注入）"""
    session = get_session_local()()
    try:
        yield session
    finally:
        session.close()
