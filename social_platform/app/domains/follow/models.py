# 关注数据库模型
# 定义关注表结构，记录用户之间的单向关注关系
from sqlalchemy import Boolean, Integer, DateTime, ForeignKey, UniqueConstraint, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime
from social_platform.app.core.timezone import local_now

from social_platform.app.db.session import Base


class Follow(Base):
    """
    关注模型
    记录用户之间的关注关系（单向）

    使用说明：
    - A 关注 B：创建一条 follower_id=A, following_id=B 的记录
    - A 取消关注 B：删除该记录

    关系说明：
    - follower：关注者（主动发起关注的一方）
    - following：被关注者（被动接收关注的一方）

    Attributes:
        follower_id: 关注者用户 ID（主动发起关注的一方）
        following_id: 被关注者用户 ID（被动接收关注的一方）
        created_at: 关注创建时间

    数据库约束：
    - (follower_id, following_id) 复合唯一约束，防止重复关注
    - follower_id 和 following_id 分别建立索引，加速查询
    - 外键设置 ondelete="CASCADE"，删除用户时自动清除关注关系
    """
    __tablename__ = "follows"

    # 主键 ID，使用自增策略
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    # 关注者用户 ID，外键关联到 users 表
    # 不能为空，因为关注必须有发起者
    follower_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False
    )

    # 被关注者用户 ID，外键关联到 users 表
    # 不能为空，因为关注必须指向被关注者
    following_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False
    )

    # 关注创建时间，自动设置为当前系统本地时间
    created_at: Mapped[datetime] = mapped_column(DateTime, default=local_now, nullable=True)
    created_by_agent: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, server_default="0")

    # 表级约束和索引配置
    __table_args__ = (
        # 复合唯一约束：(follower_id, following_id)
        # 确保同一用户对同一用户只能关注一次
        UniqueConstraint('follower_id', 'following_id', name='uq_follow_pair'),
        # 为 follower_id 添加索引，加速"查询某用户关注的人"操作
        Index('idx_follow_follower_id', 'follower_id'),
        # 为 following_id 添加索引，加速"查询某用户的被关注"操作
        Index('idx_follow_following_id', 'following_id'),
    )

    # 关联关系：关注者
    # back_populates 建立双向关联，指向 User.following
    follower = relationship(
        "User",
        foreign_keys=[follower_id],
        back_populates="following"
    )

    # 关联关系：被关注者
    # back_populates 建立双向关联，指向 User.followers
    following = relationship(
        "User",
        foreign_keys=[following_id],
        back_populates="followers"
    )
