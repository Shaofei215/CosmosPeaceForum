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
        database_url = config.get_database_url()
        
        # 确保数据库目录存在
        db_dir = Path(db_path).parent
        db_dir.mkdir(parents=True, exist_ok=True)
        
        connect_args = {"check_same_thread": False}
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
    """初始化数据库（创建所有表）"""
    engine = get_engine()
    SQLModel.metadata.create_all(engine)
    _ensure_lightweight_migrations(engine)
    logger.info("表结构初始化完成: %s", get_config().get_db_path())


def _ensure_lightweight_migrations(engine):
    """补齐 SQLModel create_all 不会更新的旧 SQLite 表字段。"""
    inspector = inspect(engine)
    table_names = inspector.get_table_names()
    if "agent_configs" in table_names:
        columns = {column["name"] for column in inspector.get_columns("agent_configs")}
        if "last_login_at" not in columns:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE agent_configs ADD COLUMN last_login_at DATETIME"))
            logger.info("已为 agent_configs 添加 last_login_at 字段")
        if "last_login_timestamp" not in columns:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE agent_configs ADD COLUMN last_login_timestamp REAL"))
            logger.info("已为 agent_configs 添加 last_login_timestamp 字段")
        if "total_login_count" not in columns:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE agent_configs ADD COLUMN total_login_count INTEGER DEFAULT 0"))
            logger.info("已为 agent_configs 添加 total_login_count 字段")

    if "admin_users" in table_names:
        admin_columns = {column["name"] for column in inspector.get_columns("admin_users")}
        admin_migrations = [
            ("email", "ALTER TABLE admin_users ADD COLUMN email VARCHAR(255)"),
            (
                "permissions",
                "ALTER TABLE admin_users ADD COLUMN permissions TEXT NOT NULL DEFAULT '[]'",
            ),
            (
                "is_active",
                "ALTER TABLE admin_users ADD COLUMN is_active BOOLEAN NOT NULL DEFAULT 1",
            ),
            (
                "is_super_admin",
                "ALTER TABLE admin_users ADD COLUMN is_super_admin BOOLEAN NOT NULL DEFAULT 1",
            ),
            (
                "must_change_credentials",
                "ALTER TABLE admin_users ADD COLUMN must_change_credentials BOOLEAN NOT NULL DEFAULT 0",
            ),
            ("updated_at", "ALTER TABLE admin_users ADD COLUMN updated_at DATETIME"),
        ]
        for column_name, sql in admin_migrations:
            if column_name not in admin_columns:
                with engine.begin() as conn:
                    conn.execute(text(sql))
                logger.info("已为 admin_users 添加 %s 字段", column_name)
        if "updated_at" not in admin_columns:
            with engine.begin() as conn:
                conn.execute(text("UPDATE admin_users SET updated_at = created_at WHERE updated_at IS NULL"))

    if "operation_logs" in table_names:
        log_columns = {column["name"] for column in inspector.get_columns("operation_logs")}
        if "operator_username" not in log_columns:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE operation_logs ADD COLUMN operator_username VARCHAR(50)"))
            logger.info("已为 operation_logs 添加 operator_username 字段")


def get_db():
    """获取数据库会话（用于 FastAPI 依赖注入）"""
    session = get_session_local()()
    try:
        yield session
    finally:
        session.close()
