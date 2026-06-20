# 帖子数据库模型
# 定义帖子表结构，存储用户发布的内容
from sqlalchemy import Column, Float, Integer, String, DateTime, ForeignKey, Index, Text, UniqueConstraint
from sqlalchemy.orm import relationship
from datetime import datetime

from social_platform.app.db.session import Base


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

    # 推荐流热度分数，由定时任务和互动操作刷新
    heat_score = Column(Float, default=0.0, nullable=False, server_default="0")
    heat_score_updated_at = Column(DateTime, nullable=True)

    # 管理端内容安全处理状态。archived 内容在公开端不可见，但仍保留用于恢复和审计。
    moderation_status = Column(String(20), nullable=False, default="active", server_default="active")
    archived_at = Column(DateTime, nullable=True)
    archived_by_admin_id = Column(Integer, nullable=True)
    archive_reason = Column(Text, nullable=True)

    __table_args__ = (
        Index("idx_posts_latest", "created_at", "id"),
        Index("idx_posts_heat_latest", "heat_score", "created_at", "id"),
        Index("idx_posts_author_latest", "author_id", "created_at", "id"),
        Index("idx_posts_moderation_status", "moderation_status", "created_at", "id"),
    )

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

    # 关联关系：帖子的投票选项和投票记录
    poll_options = relationship(
        "PollOption",
        back_populates="post",
        cascade="all, delete-orphan",
        order_by="PollOption.position",
    )
    poll_votes = relationship("PollVote", back_populates="post", cascade="all, delete-orphan")


class PollOption(Base):
    """帖子投票选项模型。

    Args:
        post_id: 所属帖子 ID。
        text: 选项展示文本，最多 20 个字符。
        position: 选项在投票中的展示顺序。
        vote_count: 冗余票数，用于列表页快速展示统计结果。
        created_at: 选项创建时间。
    """

    __tablename__ = "poll_options"

    id = Column(Integer, primary_key=True, index=True)
    post_id = Column(
        Integer,
        ForeignKey("posts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    text = Column(String(20), nullable=False)
    position = Column(Integer, nullable=False)
    vote_count = Column(Integer, default=0, nullable=False, server_default="0")
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    post = relationship("Post", back_populates="poll_options")
    votes = relationship("PollVote", back_populates="option", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("post_id", "position", name="uq_poll_options_post_position"),
        Index("idx_poll_options_post_position", "post_id", "position"),
    )


class PollVote(Base):
    """帖子投票记录模型。

    Args:
        post_id: 所属帖子 ID，用于限制每个用户在单个帖子只能投一次票。
        option_id: 被选择的投票选项 ID。
        user_id: 投票用户 ID。
        created_at: 投票时间。
    """

    __tablename__ = "poll_votes"

    id = Column(Integer, primary_key=True, index=True)
    post_id = Column(
        Integer,
        ForeignKey("posts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    option_id = Column(
        Integer,
        ForeignKey("poll_options.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    post = relationship("Post", back_populates="poll_votes")
    option = relationship("PollOption", back_populates="votes")

    __table_args__ = (
        UniqueConstraint("post_id", "user_id", name="uq_poll_votes_post_user"),
        Index("idx_poll_votes_post_option", "post_id", "option_id"),
    )

# 导入关系依赖模型，确保单独导入 Post 时 SQLAlchemy 字符串关系可解析。
from social_platform.app.domains.comment import models as _comment_models  # noqa: E402,F401
from social_platform.app.domains.reaction import models as _reaction_models  # noqa: E402,F401
from social_platform.app.domains.user import models as _user_models  # noqa: E402,F401
