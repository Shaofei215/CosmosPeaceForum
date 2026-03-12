"""
数据库模型定义
定义所有数据表结构：User, Post, Comment, Reply, Like, Follow, Notification
"""
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Enum, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime
import enum

from app.database import Base


class LikeTargetType(str, enum.Enum):
    """点赞目标类型"""
    POST = "post"
    COMMENT = "comment"
    REPLY = "reply"


class NotificationType(str, enum.Enum):
    """通知类型"""
    LIKE_POST = "like_post"       # 点赞帖子
    LIKE_COMMENT = "like_comment"   # 点赞评论
    LIKE_REPLY = "like_reply"      # 点赞回复
    COMMENT = "comment"            # 评论帖子
    REPLY = "reply"               # 回复评论
    FOLLOW = "follow"              # 关注
    QUOTE = "quote"                # 被转发


class User(Base):
    """
    用户模型
    """
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    bio = Column(Text, nullable=True)
    avatar = Column(String(255), nullable=True)  # 头像图片路径
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    posts = relationship("Post", back_populates="author", cascade="all, delete-orphan")
    comments = relationship("Comment", back_populates="author", cascade="all, delete-orphan")
    replies = relationship("Reply", back_populates="author", cascade="all, delete-orphan")
    likes = relationship("Like", back_populates="user", cascade="all, delete-orphan")


class RepostType(str, enum.Enum):
    """转发类型"""
    DIRECT = "direct"              # 直接转发（无内容）
    COMMENT = "comment"            # 评论并转发
    REPLY = "reply"                # 回复并转发


class Post(Base):
    """
    帖子模型
    """
    __tablename__ = "posts"

    id = Column(Integer, primary_key=True, index=True)
    author_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # 热度相关字段
    hot_score = Column(Integer, default=0, nullable=False, index=True)  # 热度分数
    last_hot_update = Column(DateTime, default=datetime.utcnow, nullable=False)  # 上次热度更新时间

    # ========== 重构：转发相关字段 ==========
    # 帖子类型：original=原创，quote=引用转发
    post_type = Column(String(20), default="original", nullable=False, index=True)
    
    # 关联的直接转发帖子 ID（外键，用于计数和追溯）
    # quote 类型时，指向直接转发的帖子；original 类型时为 NULL
    quote_from_id = Column(Integer, ForeignKey("posts.id"), nullable=True, index=True)
    
    # 关联的原始帖子 ID（用于小卡片展示）
    # 永远指向最底层的原创帖子
    original_post_id = Column(Integer, ForeignKey("posts.id"), nullable=True, index=True)
    
    # 转发类型：direct=直接转发，comment=评论转发，reply=回复转发
    repost_type = Column(String(20), nullable=True)  # 仅当 post_type='quote' 时使用
    
    # 关联的评论 ID（如果是评论并转发）
    comment_id = Column(Integer, ForeignKey("comments.id"), nullable=True, index=True)
    
    # 关联的回复 ID（如果是回复并转发）
    reply_id = Column(Integer, ForeignKey("replies.id"), nullable=True, index=True)
    
    # 转发时的评论（quote 类型时的内容）
    quote_comment = Column(Text, nullable=True)

    author = relationship("User", back_populates="posts")
    comments = relationship("Comment", foreign_keys="Comment.post_id", back_populates="post", cascade="all, delete-orphan")
    likes = relationship("Like", foreign_keys="Like.post_id", back_populates="post", cascade="all, delete-orphan")
    
    # 自引用：被引用的原帖（直接转发）
    quote_from = relationship(
        "Post",
        remote_side=[id],
        back_populates="quotes",
        foreign_keys=[quote_from_id]
    )
    # 自引用：所有引用/转发此帖的记录
    quotes = relationship(
        "Post",
        back_populates="quote_from",
        cascade="all, delete-orphan",
        foreign_keys=[quote_from_id]
    )
    
    # 自引用：原始帖子（用于小卡片展示）
    original_post = relationship(
        "Post",
        remote_side=[id],
        foreign_keys=[original_post_id]
    )


class Comment(Base):
    """
    评论模型
    """
    __tablename__ = "comments"

    id = Column(Integer, primary_key=True, index=True)
    post_id = Column(Integer, ForeignKey("posts.id"), nullable=False)
    author_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # 热度相关字段
    hot_score = Column(Integer, default=0, nullable=False, index=True)  # 热度分数
    last_hot_update = Column(DateTime, default=datetime.utcnow, nullable=False)  # 上次热度更新时间

    post = relationship("Post", foreign_keys="Comment.post_id", back_populates="comments")
    author = relationship("User", back_populates="comments")
    replies = relationship("Reply", foreign_keys="Reply.comment_id", back_populates="comment", cascade="all, delete-orphan")
    likes = relationship("Like", foreign_keys="Like.comment_id", back_populates="comment", cascade="all, delete-orphan")


class Reply(Base):
    """
    回复模型（评论的回复）
    支持楼中楼，可以回复评论，也可以回复其他回复
    """
    __tablename__ = "replies"

    id = Column(Integer, primary_key=True, index=True)
    # 母评论ID（必属）
    comment_id = Column(Integer, ForeignKey("comments.id"), nullable=False)
    # 父回复ID（可选，如果是回复回复则有值）
    parent_reply_id = Column(Integer, ForeignKey("replies.id"), nullable=True)
    author_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # 热度相关字段
    hot_score = Column(Integer, default=0, nullable=False, index=True)  # 热度分数
    last_hot_update = Column(DateTime, default=datetime.utcnow, nullable=False)  # 上次热度更新时间

    comment = relationship("Comment", back_populates="replies")
    author = relationship("User", back_populates="replies")
    # 自引用关系，用于获取子回复
    parent_reply = relationship("Reply", remote_side=[id], back_populates="child_replies")
    child_replies = relationship("Reply", back_populates="parent_reply", cascade="all, delete-orphan")
    likes = relationship("Like", foreign_keys="Like.reply_id", back_populates="reply", cascade="all, delete-orphan")


class Like(Base):
    """
    点赞模型（通用）
    支持帖子、评论、回复的点赞
    """
    __tablename__ = "likes"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # 点赞目标（三选一）
    post_id = Column(Integer, ForeignKey("posts.id"), nullable=True)
    comment_id = Column(Integer, ForeignKey("comments.id"), nullable=True)
    reply_id = Column(Integer, ForeignKey("replies.id"), nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    user = relationship("User", back_populates="likes")
    post = relationship("Post", foreign_keys=[post_id], back_populates="likes")
    comment = relationship("Comment", foreign_keys=[comment_id], back_populates="likes")
    reply = relationship("Reply", foreign_keys=[reply_id], back_populates="likes")


class Follow(Base):
    """
    关注关系模型
    """
    __tablename__ = "follows"

    id = Column(Integer, primary_key=True, index=True)
    follower_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    following_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class UserReadPost(Base):
    """
    用户已读帖子记录模型
    用于记录用户阅读过哪些帖子，实现个性化推荐去重
    """
    __tablename__ = "user_read_posts"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    post_id = Column(Integer, ForeignKey("posts.id"), nullable=False, index=True)
    read_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    # 联合唯一约束，防止重复记录
    __table_args__ = (
        {'sqlite_autoincrement': True},
    )


class Notification(Base):
    """
    通知消息模型
    用于记录用户收到的互动消息（点赞、评论、回复、关注等）
    """
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)  # 接收者
    actor_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)  # 发起者
    
    # 通知类型
    type = Column(Enum(NotificationType), nullable=False, index=True)
    
    # 关联对象（根据类型三选一）
    post_id = Column(Integer, ForeignKey("posts.id"), nullable=True, index=True)
    comment_id = Column(Integer, ForeignKey("comments.id"), nullable=True, index=True)
    reply_id = Column(Integer, ForeignKey("replies.id"), nullable=True, index=True)
    
    is_read = Column(Boolean, default=False, nullable=False, index=True)  # 是否已读
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    
    # 关系
    user = relationship("User", foreign_keys=[user_id], backref="notifications")
    actor = relationship("User", foreign_keys=[actor_id])
    post = relationship("Post", foreign_keys=[post_id])
    comment = relationship("Comment", foreign_keys=[comment_id])
    reply = relationship("Reply", foreign_keys=[reply_id])
