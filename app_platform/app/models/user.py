# 用户数据库模型
# 定义用户表结构，存储用户基本信息
from sqlalchemy import Column, Integer, String, DateTime, Text, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime

from app_platform.app.db.session import Base


class User(Base):
    """
    用户模型
    存储平台用户的基本信息，对所有用户（人类和 AI）一视同仁
    """
    __tablename__ = "users"

    # 用户唯一标识符（全局唯一，使用自增）
    id = Column(Integer, primary_key=True, index=True)

    # 用户名，用于登录和识别
    # - 初始为 NULL（注册阶段）
    # - 资料完善时必须设置，且设置后唯一
    # - AI 用户在创建时直接设置
    username = Column(String(50), unique=True, index=True, nullable=True)

    # 个人简介，可选
    bio = Column(Text, nullable=True)

    # 头像 URL，可选
    avatar_url = Column(String(500), nullable=True)

    # 创建时间，自动设置为当前 UTC 时间
    created_at = Column(DateTime, default=datetime.utcnow)

    # 密码哈希（BCrypt）
    # - 真人用户：注册时设置
    # - AI 用户：系统生成随机密码或为空（由管理器保管）
    password_hash = Column(String(255), nullable=True)

    # AI 角色标记
    # True 表示 AI 账号，False 表示真人账号
    is_ai_agent = Column(Boolean, default=False, nullable=False, index=True)

    # 对应 ai_users_config.json 中的 ID（仅 AI 用户有值）
    ai_config_id = Column(Integer, nullable=True, index=True)

    # 邮箱地址（真人用户必填，AI 用户为 None）
    email = Column(String(255), unique=True, nullable=True, index=True)

    # 邮箱是否已验证
    email_verified = Column(Boolean, default=False, nullable=False)

    # 邮箱验证通过时间
    email_verified_at = Column(DateTime, nullable=True)

    # 关联关系：用户发布的帖子
    # cascade="all, delete-orphan" 表示删除用户时自动删除其所有帖子
    posts = relationship("Post", back_populates="author", cascade="all, delete-orphan")

    # 关联关系：用户的点赞记录
    # back_populates 建立双向关联
    # cascade 不设置，因为用户删除通过外键 ondelete 处理
    likes = relationship("Like", back_populates="user")

    # 关联关系：用户发布的评论
    # cascade="all, delete-orphan" 表示删除用户时自动删除其所有评论
    comments = relationship("Comment", back_populates="owner", cascade="all, delete-orphan")

    # 关联关系：用户的评论点赞记录
    # back_populates 建立双向关联
    comment_likes = relationship("CommentLike", back_populates="user")

    # 关联关系：邮箱验证码记录
    # cascade="all, delete-orphan" 表示删除用户时自动删除其所有验证码记录
    email_codes = relationship("EmailVerificationCode", back_populates="user")

    # ========== 关注系统相关字段和关系 ==========

    # 冗余计数字段：关注数量
    # 表示该用户关注了多少人
    # 在关注/取消关注时更新，保证高性能查询
    following_count = Column(Integer, default=0, nullable=False)

    # 冗余计数字段：粉丝数量
    # 表示该用户被多少人关注
    # 在关注/取消关注时更新，保证高性能查询
    followers_count = Column(Integer, default=0, nullable=False)

    # 关联关系：用户关注的人（作为关注者）
    # User.following 表示该用户关注了哪些人
    # foreign_keys=[Follow.follower_id] 指定外键指向 Follow 表的 follower_id
    following = relationship(
        "Follow",
        foreign_keys="Follow.follower_id",
        back_populates="follower",
        cascade="all, delete-orphan"
    )

    # 关联关系：用户的粉丝（作为被关注者）
    # User.followers 表示该用户的粉丝有哪些
    # foreign_keys=[Follow.following_id] 指定外键指向 Follow 表的 following_id
    followers = relationship(
        "Follow",
        foreign_keys="Follow.following_id",
        back_populates="following",
        cascade="all, delete-orphan"
    )
