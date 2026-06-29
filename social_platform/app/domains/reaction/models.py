# 点赞数据库模型
# 定义点赞表结构，记录用户对帖子的点赞行为
from sqlalchemy import Boolean, Column, Integer, DateTime, ForeignKey, PrimaryKeyConstraint, Index
from sqlalchemy.orm import relationship
from datetime import datetime
from social_platform.app.core.timezone import local_now

from social_platform.app.db.session import Base


class Like(Base):
    """
    点赞模型
    记录用户对帖子的点赞行为
    
    Attributes:
        user_id: 点赞用户的 ID，外键关联 users 表
        post_id: 被点赞帖子的 ID，外键关联 posts 表
        created_at: 点赞创建时间，自动设置为当前系统本地时间
    
    Note:
        - 使用 (user_id, post_id) 作为复合主键
        - 确保一个用户对同一帖子只能点赞一次
        - 删除用户或帖子时自动删除对应的点赞记录
    """
    __tablename__ = "likes"  # 数据库表名

    # 点赞用户 ID，外键关联到 users 表
    # 不能为空，因为点赞必须有用户
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    
    # 被点赞帖子 ID，外键关联到 posts 表
    # 不能为空，因为点赞必须针对帖子
    post_id = Column(Integer, ForeignKey("posts.id", ondelete="CASCADE"), nullable=False)
    
    # 点赞创建时间，自动设置为当前系统本地时间
    created_at = Column(DateTime, default=local_now)
    created_by_agent = Column(Boolean, default=False, nullable=False, server_default="0")

    # 复合主键：(user_id, post_id)
    # 确保同一用户对同一帖子只能有一条点赞记录
    __table_args__ = (
        PrimaryKeyConstraint('user_id', 'post_id', name='likes_pkey'),
        # 为 post_id 添加索引，加速查询某帖子的所有点赞
        Index('idx_likes_post_id', 'post_id'),
        # 为 user_id 添加索引，加速查询某用户的所有点赞
        Index('idx_likes_user_id', 'user_id'),
    )

    # 关联关系：点赞的用户
    # back_populates 建立双向关联
    # cascade 不设置，因为用户删除通过外键 ondelete 处理
    user = relationship("User", back_populates="likes")

    # 关联关系：被点赞的帖子
    # back_populates 建立双向关联
    post = relationship("Post", back_populates="likes")
