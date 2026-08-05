"""硬币领域数据库模型。"""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Index, Integer, PrimaryKeyConstraint, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from social_platform.app.core.timezone import local_now
from social_platform.app.db.session import Base


class PostCoin(Base):
    """用户向帖子投出的硬币。

    复合主键从数据库层保证同一用户只能向同一帖子投一枚硬币。
    """

    __tablename__ = "post_coins"

    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    post_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("posts.id", ondelete="CASCADE"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=local_now, nullable=False)
    created_by_agent: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        server_default="0",
    )

    user = relationship("User", back_populates="post_coins")
    post = relationship("Post", back_populates="coins")

    __table_args__ = (
        PrimaryKeyConstraint("user_id", "post_id", name="post_coins_pkey"),
        Index("idx_post_coins_post_id", "post_id"),
        Index("idx_post_coins_user_id", "user_id"),
    )


class DailyCoinReward(Base):
    """每日登录硬币领取记录，用唯一约束防止重复发放。"""

    __tablename__ = "daily_coin_rewards"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    reward_date: Mapped[date] = mapped_column(Date, nullable=False)
    amount: Mapped[int] = mapped_column(Integer, nullable=False)
    streak: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=local_now, nullable=False)

    user = relationship("User", back_populates="daily_coin_rewards")

    __table_args__ = (
        UniqueConstraint("user_id", "reward_date", name="uq_daily_coin_rewards_user_date"),
        Index("idx_daily_coin_rewards_date", "reward_date"),
    )
