"""
Management Backend - 数据库连接管理
使用 SQLModel (SQLAlchemy) 管理数据库连接，schema 变更由 Alembic 迁移负责。
"""

import logging
from pathlib import Path
from alembic import command
from alembic.config import Config
from sqlmodel import Session, create_engine
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
        database_url = config.get_database_url()
        
        if database_url.startswith("sqlite"):
            db_dir = Path(db_path).parent
            db_dir.mkdir(parents=True, exist_ok=True)
            connect_args = {"check_same_thread": False}
        else:
            connect_args = {}
        _engine = create_engine(
            database_url,
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
    """初始化数据库 schema。"""
    engine = get_engine()
    alembic_cfg = Config(str(Path(__file__).resolve().parents[2] / "alembic.ini"))
    alembic_cfg.set_main_option("sqlalchemy.url", get_config().get_database_url())
    alembic_cfg.attributes["configure_logger"] = False
    logger.info(
        "Management 数据库迁移开始",
        extra={"event": "migration.start", "component": "migration"},
    )
    try:
        command.upgrade(alembic_cfg, "head")
    except Exception:
        logger.exception(
            "Management 数据库迁移失败",
            extra={"event": "migration.error", "component": "migration"},
        )
        raise
    logger.info(
        "表结构迁移完成: %s",
        get_config().get_db_path(),
        extra={"event": "migration.complete", "component": "migration"},
    )


def get_db():
    """获取数据库会话（用于 FastAPI 依赖注入）"""
    session = get_session_local()()
    try:
        yield session
    finally:
        session.close()
