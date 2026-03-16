# 帖子数据库模型
# 定义帖子表结构，存储用户发布的内容
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from datetime import datetime

from app.db.session import Base


class Post(Base):
    """
    帖子模型
    存储用户发布的内容信息
    """
    __tablename__ = "posts"  # 数据库表名

    # 帖子唯一标识符（全局唯一，使用自增）
    id = Column(Integer, primary_key=True, index=True)
    
    # 作者 ID，外键关联到 users 表
    author_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # 帖子标题，可选
    title = Column(String(200), nullable=True)
    
    # 帖子内容，必填
    content = Column(Text, nullable=False)
    
    # 创建时间，自动设置为当前 UTC 时间
    created_at = Column(DateTime, default=datetime.utcnow)

    # 关联关系：帖子的作者
    # back_populates 建立双向关联
    author = relationship("User", back_populates="posts")
