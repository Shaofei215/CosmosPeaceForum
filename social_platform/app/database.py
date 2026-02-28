"""
数据库配置模块
提供SQLAlchemy引擎和会话管理
"""
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

SQLALCHEMY_DATABASE_URL = "sqlite:///./social_platform.db"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False}
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    """
    获取数据库会话的依赖函数
    用于FastAPI的Depends注入
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
