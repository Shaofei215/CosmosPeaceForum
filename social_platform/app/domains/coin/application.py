"""硬币领域应用服务。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from social_platform.app.core.timezone import local_now
from social_platform.app.domains.coin.events import PostCoinGiven
from social_platform.app.domains.coin.models import DailyCoinReward, PostCoin
from social_platform.app.domains.post.models import Post
from social_platform.app.domains.user.models import User
from social_platform.app.shared.events import publish_domain_event
from social_platform.app.shared.unit_of_work import commit_session, rollback_session


MAX_COIN_BALANCE = 65_535
MAX_COIN_TRANSFERS_PER_MINUTE = 30


class PostNotFoundError(Exception):
    """目标帖子不存在或不可公开互动。"""


class SelfCoinError(Exception):
    """用户不能给自己的帖子投币。"""


class DuplicateCoinError(Exception):
    """用户已经给目标帖子投过币。"""


class InsufficientCoinBalanceError(Exception):
    """用户没有可用硬币。"""


class RecipientCoinBalanceLimitError(Exception):
    """帖子作者的硬币余额已经达到系统上限。"""


class CoinRateLimitError(Exception):
    """用户在短时间内投币过于频繁。"""


class UserNotFoundError(Exception):
    """目标用户不存在。"""


@dataclass(frozen=True)
class DailyCoinRewardResult:
    """一次登录奖励检查结果。"""

    amount: int
    coin_balance: int
    streak: int
    reward_date: date


def grant_daily_login_reward(
    db: Session,
    user: User,
    reward_date: date | None = None,
) -> DailyCoinRewardResult:
    """在指定自然日首次登录时发放硬币。

    连续登录每逢第 5 天发放 2 枚，其余天发放 1 枚；中断后从第 1 天重新计算。
    本函数不提交事务，调用方应与登录 Session 创建一起提交。

    Args:
        db: 当前数据库会话。
        user: 已完成身份校验的用户。
        reward_date: 可选业务日期，默认使用服务器本地自然日。

    Returns:
        DailyCoinRewardResult: 本次发放数量、发放后余额和连续登录天数。
    """

    today = reward_date or local_now().date()
    existing = db.query(DailyCoinReward).filter(
        DailyCoinReward.user_id == user.id,
        DailyCoinReward.reward_date == today,
    ).first()
    if existing is not None:
        return DailyCoinRewardResult(
            amount=0,
            coin_balance=int(getattr(user, "coin_balance", 0) or 0),
            streak=int(getattr(user, "login_streak", 0) or 0),
            reward_date=today,
        )

    last_reward_date = getattr(user, "last_coin_reward_date", None)
    previous_streak = int(getattr(user, "login_streak", 0) or 0)
    streak = previous_streak + 1 if last_reward_date == today - timedelta(days=1) else 1
    requested_amount = 2 if streak % 5 == 0 else 1
    current_balance = int(getattr(user, "coin_balance", 0) or 0)
    amount = min(requested_amount, max(MAX_COIN_BALANCE - current_balance, 0))

    try:
        # 先写入唯一领取记录；并发登录只有一个事务能通过该 flush。
        with db.begin_nested():
            db.add(
                DailyCoinReward(
                    user_id=user.id,
                    reward_date=today,
                    amount=amount,
                    streak=streak,
                )
            )
            db.flush()
    except IntegrityError:
        db.expire(user)
        return DailyCoinRewardResult(
            amount=0,
            coin_balance=int(getattr(user, "coin_balance", 0) or 0),
            streak=int(getattr(user, "login_streak", 0) or 0),
            reward_date=today,
        )

    user.coin_balance = current_balance + amount
    user.login_streak = streak
    user.last_coin_reward_date = today
    return DailyCoinRewardResult(
        amount=amount,
        coin_balance=user.coin_balance,
        streak=streak,
        reward_date=today,
    )


def give_post_coin(
    db: Session,
    user_id: int,
    post_id: int,
    *,
    created_by_agent: bool = False,
) -> tuple[int, int]:
    """把一枚硬币从投币用户转给帖子作者，并增加帖子热度。

    Args:
        db: 当前数据库会话。
        user_id: 投币用户 ID。
        post_id: 目标帖子 ID。
        created_by_agent: 操作是否来自可信 Agent 通道。

    Returns:
        tuple[int, int]: 帖子累计硬币数与投币用户剩余余额。

    Raises:
        PostNotFoundError: 帖子不存在或已归档。
        SelfCoinError: 用户尝试给自己的帖子投币。
        DuplicateCoinError: 用户已经给该帖子投过币。
        InsufficientCoinBalanceError: 用户余额不足。
        RecipientCoinBalanceLimitError: 帖子作者的硬币余额已经达到上限。
        CoinRateLimitError: 用户一分钟内的投币次数达到安全上限。
    """

    post = db.query(Post).filter(
        Post.id == post_id,
        Post.moderation_status == "active",
    ).first()
    if post is None:
        raise PostNotFoundError("帖子不存在")
    if post.author_id == user_id:
        raise SelfCoinError("不能给自己的帖子投币")

    # 锁定投币者行，使同一账号的并发投币依次执行；服务端从认证上下文取得 user_id，
    # 客户端无法指定投币者、收币者或转账数量。
    actor_exists = db.query(User.id).filter(User.id == user_id).with_for_update().first()
    if actor_exists is None:
        raise InsufficientCoinBalanceError("硬币余额不足")
    recent_transfer_count = db.query(PostCoin).filter(
        PostCoin.user_id == user_id,
        PostCoin.created_at >= local_now() - timedelta(minutes=1),
    ).count()
    if recent_transfer_count >= MAX_COIN_TRANSFERS_PER_MINUTE:
        raise CoinRateLimitError("投币过于频繁，请稍后再试")

    if db.query(PostCoin).filter(
        PostCoin.user_id == user_id,
        PostCoin.post_id == post_id,
    ).first() is not None:
        raise DuplicateCoinError("每个用户只能给同一帖子投一枚硬币")

    try:
        relation = PostCoin(
            user_id=user_id,
            post_id=post_id,
            created_by_agent=created_by_agent,
        )
        db.add(relation)
        # 先触发复合主键约束；并发重复请求失败后整个事务都会回滚。
        db.flush()
        updated_users = db.query(User).filter(
            User.id == user_id,
            User.coin_balance > 0,
        ).update(
            {User.coin_balance: User.coin_balance - 1},
            synchronize_session=False,
        )
        if updated_users != 1:
            rollback_session(db)
            raise InsufficientCoinBalanceError("硬币余额不足")

        updated_recipients = db.query(User).filter(
            User.id == post.author_id,
            User.coin_balance < MAX_COIN_BALANCE,
        ).update(
            {User.coin_balance: User.coin_balance + 1},
            synchronize_session=False,
        )
        if updated_recipients != 1:
            rollback_session(db)
            raise RecipientCoinBalanceLimitError("帖子作者的硬币余额已达 65535 上限")

        db.query(Post).filter(Post.id == post_id).update(
            {Post.coin_count: Post.coin_count + 1},
            synchronize_session=False,
        )
        db.expire(post, ["coin_count"])
        publish_domain_event(
            db,
            PostCoinGiven(
                post_id=post_id,
                sender_id=user_id,
                recipient_id=post.author_id,
                created_by_agent=created_by_agent,
            ),
        )
        commit_session(db)
    except IntegrityError as exc:
        rollback_session(db)
        raise DuplicateCoinError("每个用户只能给同一帖子投一枚硬币") from exc

    coin_count = db.query(Post.coin_count).filter(Post.id == post_id).scalar() or 0
    coin_balance = db.query(User.coin_balance).filter(User.id == user_id).scalar() or 0
    return int(coin_count), int(coin_balance)


def get_post_coin_status(db: Session, user_id: int, post_id: int) -> tuple[bool, int, int]:
    """读取当前用户的帖子投币状态、帖子硬币数和余额。"""

    post = db.query(Post).filter(
        Post.id == post_id,
        Post.moderation_status == "active",
    ).first()
    if post is None:
        raise PostNotFoundError("帖子不存在")
    is_coined = db.query(PostCoin).filter(
        PostCoin.user_id == user_id,
        PostCoin.post_id == post_id,
    ).first() is not None
    balance = db.query(User.coin_balance).filter(User.id == user_id).scalar() or 0
    return is_coined, int(post.coin_count or 0), int(balance)


def get_user_coin_statuses(
    db: Session,
    post_ids: list[int],
    user_id: int | None,
) -> dict[int, bool]:
    """批量读取当前用户对帖子列表的投币状态。"""

    if user_id is None or not post_ids:
        return {post_id: False for post_id in post_ids}
    coined_ids = {
        row[0]
        for row in db.query(PostCoin.post_id).filter(
            PostCoin.user_id == user_id,
            PostCoin.post_id.in_(post_ids),
        ).all()
    }
    return {post_id: post_id in coined_ids for post_id in post_ids}


def set_user_coin_balance(db: Session, user_id: int, coin_balance: int) -> User:
    """由管理端把用户硬币余额设置为指定值，但不主动提交事务。"""

    if coin_balance < 0 or coin_balance > MAX_COIN_BALANCE:
        raise ValueError(f"硬币数量必须在 0 到 {MAX_COIN_BALANCE} 之间")
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise UserNotFoundError("用户不存在")
    user.coin_balance = coin_balance
    db.flush()
    return user
