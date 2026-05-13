# 评论数据库模型
# 定义评论表结构，支持无限层级回复和评论点赞功能
from sqlalchemy import Column, Float, Integer, String, DateTime, ForeignKey, PrimaryKeyConstraint, Index, Text
from sqlalchemy.orm import relationship, remote, foreign
from datetime import datetime

from app_platform.app.db.session import Base


class Comment(Base):
    """
    评论模型
    存储用户对帖子的评论和回复，支持无限层级嵌套
    
    Attributes:
        id: 评论唯一标识符
        post_id: 关联帖子ID
        owner_id: 评论发布者ID
        parent_id: 父评论ID，为空表示一级评论，有值表示回复
        content: 评论内容
        like_count: 冗余点赞数，默认0
        reply_count: 全量回复数（所有子孙后代总数），默认0
        created_at: 创建时间
    
    Note:
        - 通过 parent_id 自关联实现无限层级回复
        - reply_count 统计当前评论下的所有回复（含嵌套回复）
        - 删除帖子或用户时自动删除关联评论
    """
    __tablename__ = "comments"  # 数据库表名

    # 评论唯一标识符（全局唯一，使用自增）
    id = Column(Integer, primary_key=True, index=True)
    
    # 关联帖子ID，外键关联到 posts 表
    post_id = Column(Integer, ForeignKey("posts.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # 评论发布者ID，外键关联到 users 表
    owner_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # 父评论ID，外键关联到 comments 表自身
    # 为空表示一级评论，有值表示回复
    parent_id = Column(Integer, ForeignKey("comments.id", ondelete="CASCADE"), nullable=True, index=True)
    
    # 评论内容，必填
    content = Column(Text, nullable=False)
    
    # 点赞计数，冗余存储以提高查询性能
    like_count = Column(Integer, default=0, nullable=False)
    
    # 回复计数，统计所有子孙后代回复总数（全量统计）
    reply_count = Column(Integer, default=0, nullable=False)
    
    # 创建时间，自动设置为当前 UTC 时间
    created_at = Column(DateTime, default=datetime.utcnow)

    # 评论推荐流热度分数，由定时任务和互动操作刷新
    heat_score = Column(Float, default=0.0, nullable=False, server_default="0")
    heat_score_updated_at = Column(DateTime, nullable=True)

    # 关联关系：评论所属的帖子
    post = relationship("Post", back_populates="comments")
    
    # 关联关系：评论的发布者
    owner = relationship("User", back_populates="comments")
    
    # 关联关系：父评论
    # remote_side=[id] 表示 id 是远程端（被引用的表）
    parent = relationship("Comment", remote_side=[id], back_populates="children")
    
    # 关联关系：子评论（回复列表）
    children = relationship("Comment", back_populates="parent", cascade="all, delete-orphan")
    
    # 关联关系：评论的点赞记录
    likes = relationship("CommentLike", back_populates="comment", cascade="all, delete-orphan")


class CommentLike(Base):
    """
    评论点赞模型
    记录用户对评论的点赞行为
    
    Attributes:
        user_id: 点赞用户的 ID，外键关联 users 表
        comment_id: 被点赞评论的 ID，外键关联 comments 表
        created_at: 点赞创建时间，自动设置为当前 UTC 时间
    
    Note:
        - 使用 (user_id, comment_id) 作为复合主键
        - 确保一个用户对同一评论只能点赞一次
        - 删除用户或评论时自动删除对应的点赞记录
    """
    __tablename__ = "comment_likes"  # 数据库表名

    # 点赞用户 ID，外键关联到 users 表
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    
    # 被点赞评论 ID，外键关联到 comments 表
    comment_id = Column(Integer, ForeignKey("comments.id", ondelete="CASCADE"), nullable=False)
    
    # 点赞创建时间，自动设置为当前 UTC 时间
    created_at = Column(DateTime, default=datetime.utcnow)

    # 复合主键：(user_id, comment_id)
    # 确保同一用户对同一评论只能有一条点赞记录
    __table_args__ = (
        PrimaryKeyConstraint('user_id', 'comment_id', name='comment_likes_pkey'),
        # 为 comment_id 添加索引，加速查询某评论的所有点赞
        Index('idx_comment_likes_comment_id', 'comment_id'),
        # 为 user_id 添加索引，加速查询某用户的所有点赞
        Index('idx_comment_likes_user_id', 'user_id'),
    )

    # 关联关系：点赞的用户
    user = relationship("User", back_populates="comment_likes")
    
    # 关联关系：被点赞的评论
    comment = relationship("Comment", back_populates="likes")
