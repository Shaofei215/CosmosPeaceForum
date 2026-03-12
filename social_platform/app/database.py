"""
数据库配置模块
提供 SQLAlchemy 引擎和会话管理
"""
import os
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# 使用绝对路径，确保数据库文件在 social_platform 目录下
BASE_DIR = Path(__file__).parent
SQLALCHEMY_DATABASE_URL = f"sqlite:///{BASE_DIR}/social_platform.db"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False}
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    """
    获取数据库会话的依赖函数
    用于 FastAPI 的 Depends 注入
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
