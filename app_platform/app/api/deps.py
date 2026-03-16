# 依赖注入模块
# 提供 API 路由所需的公共依赖
from sqlalchemy.orm import Session
from typing import Generator

from app.db.session import SessionLocal


def get_db() -> Generator[Session, None, None]:
    """
    数据库会话依赖注入
    
    创建数据库会话，使用完毕后自动关闭
    
    Yields:
        Session: 数据库会话对象
    
    Note:
        使用 try-finally 确保会话总是被关闭
    """
    # 创建数据库会话
    db = SessionLocal()
    try:
        # 返回会话供路由使用
        yield db
    finally:
        # 确保会话被关闭，释放数据库连接
        db.close()
