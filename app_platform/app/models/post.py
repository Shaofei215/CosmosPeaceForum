# 帖子数据库模型
# 定义帖子表结构，存储用户发布的内容
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from datetime import datetime

from app_platform.app.db.session import Base


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

    type = Column(String(20), nullable=False, default="post", server_default="post")
    
    # 帖子内容，必填
    content = Column(Text, nullable=False)
    
    # 创建时间，自动设置为当前 UTC 时间
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # 点赞计数，冗余存储以提高查询性能
    # 默认值为 0，每次点赞/取消点赞时更新
    like_count = Column(Integer, default=0, nullable=False)
    
    # 评论计数，冗余存储以提高查询性能
    # 统计帖子下所有评论和回复的总数
    comment_count = Column(Integer, default=0, nullable=False)

    # 转发计数与转发链元数据
    repost_count = Column(Integer, default=0, nullable=False)
    repost_source_type = Column(String(20), nullable=True)
    repost_source_id = Column(Integer, nullable=True)
    repost_root_post_id = Column(Integer, ForeignKey("posts.id"), nullable=True, index=True)
    repost_chain = Column(Text, nullable=True)

    # 关联关系：帖子的作者
    # back_populates 建立双向关联
    author = relationship("User", back_populates="posts")
    repost_root_post = relationship("Post", remote_side=[id], foreign_keys=[repost_root_post_id])
    
    # 关联关系：帖子的点赞记录
    # back_populates 建立双向关联
    # cascade 不设置，因为帖子删除通过外键 ondelete 处理
    likes = relationship("Like", back_populates="post")
    
    # 关联关系：帖子的评论列表
    # cascade="all, delete-orphan" 表示删除帖子时自动删除其所有评论
    comments = relationship("Comment", back_populates="post", cascade="all, delete-orphan")
