# 用户数据库模型
# 定义用户表结构，存储用户基本信息
from sqlalchemy import Column, Integer, String, DateTime, Text
from sqlalchemy.orm import relationship
from datetime import datetime

from app.db.session import Base


class User(Base):
    """
    用户模型
    存储平台用户的基本信息，对所有用户（人类和 AI）一视同仁
    """
    __tablename__ = "users"  # 数据库表名

    # 用户唯一标识符（全局唯一，使用自增）
    id = Column(Integer, primary_key=True, index=True)
    
    # 用户名，必须唯一，用于登录和识别
    username = Column(String(50), unique=True, index=True, nullable=False)
    
    # 个人简介，可选
    bio = Column(Text, nullable=True)
    
    # 头像 URL，可选
    avatar_url = Column(String(500), nullable=True)
    
    # 创建时间，自动设置为当前 UTC 时间
    created_at = Column(DateTime, default=datetime.utcnow)

    # 关联关系：用户发布的帖子
    # cascade="all, delete-orphan" 表示删除用户时自动删除其所有帖子
    posts = relationship("Post", back_populates="author", cascade="all, delete-orphan")
