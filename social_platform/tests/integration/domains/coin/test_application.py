"""硬币领域应用服务集成测试。"""

from collections.abc import Generator
from datetime import date, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from social_platform.app.db.session import Base
from social_platform.app.domains.coin import application as coin_service
from social_platform.app.domains.coin.models import DailyCoinReward, PostCoin
from social_platform.app.domains.notification.models import Notification
from social_platform.app.domains.post.models import Post
from social_platform.app.domains.user.models import User


@pytest.fixture()
def db_session() -> Generator[Session, None, None]:
    """创建仅供硬币领域测试使用的内存数据库会话。"""

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    testing_session_local = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = testing_session_local()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


def _create_user(db_session: Session, username: str, *, coin_balance: int = 0) -> User:
    """创建测试用户并刷新主键。"""

    user = User(username=username, coin_balance=coin_balance)
    db_session.add(user)
    db_session.flush()
    return user


def test_daily_login_reward_is_idempotent_and_fifth_day_grants_two(db_session) -> None:
    """同一天只发一次，连续第 5 天发两枚硬币。"""

    user = _create_user(db_session, "daily_reward_user")
    first_day = date(2026, 8, 1)

    amounts = []
    for offset in range(5):
        result = coin_service.grant_daily_login_reward(
            db_session,
            user,
            first_day + timedelta(days=offset),
        )
        amounts.append(result.amount)
        db_session.commit()

    duplicate = coin_service.grant_daily_login_reward(
        db_session,
        user,
        first_day + timedelta(days=4),
    )

    assert amounts == [1, 1, 1, 1, 2]
    assert duplicate.amount == 0
    assert user.coin_balance == 6
    assert user.login_streak == 5
    assert db_session.query(DailyCoinReward).count() == 5


def test_daily_login_reward_resets_streak_after_gap(db_session) -> None:
    """漏登一天后连续天数从 1 重新开始。"""

    user = _create_user(db_session, "streak_reset_user")
    coin_service.grant_daily_login_reward(db_session, user, date(2026, 8, 1))
    db_session.commit()

    result = coin_service.grant_daily_login_reward(db_session, user, date(2026, 8, 3))
    db_session.commit()

    assert result.amount == 1
    assert result.streak == 1
    assert user.login_streak == 1


def test_daily_login_reward_does_not_exceed_65535(db_session) -> None:
    """每日奖励到达余额上限后不应继续增加硬币。"""

    user = _create_user(db_session, "capped_reward_user", coin_balance=65_534)
    first = coin_service.grant_daily_login_reward(db_session, user, date(2026, 8, 1))
    db_session.commit()
    second = coin_service.grant_daily_login_reward(db_session, user, date(2026, 8, 2))
    db_session.commit()

    assert first.amount == 1
    assert second.amount == 0
    assert user.coin_balance == 65_535


def test_give_post_coin_consumes_balance_updates_heat_and_notifies(db_session) -> None:
    """投币应原子转移硬币、增加计数，并保留 Agent 来源到通知。"""

    author = _create_user(db_session, "coin_author")
    actor = _create_user(db_session, "coin_actor", coin_balance=2)
    post = Post(author_id=author.id, content="值得支持的帖子")
    db_session.add(post)
    db_session.commit()

    coin_count, coin_balance = coin_service.give_post_coin(
        db_session,
        actor.id,
        post.id,
        created_by_agent=True,
    )

    relation = db_session.query(PostCoin).one()
    notification = db_session.query(Notification).one()
    db_session.refresh(post)
    db_session.refresh(author)
    assert (coin_count, coin_balance) == (1, 1)
    assert author.coin_balance == 1
    assert relation.created_by_agent is True
    assert notification.type == "post_coin"
    assert notification.recipient_id == author.id
    assert notification.created_by_agent is True
    assert post.coin_count == 1
    assert post.heat_score > 0


def test_give_post_coin_rejects_duplicate_self_and_insufficient_balance(db_session) -> None:
    """投币必须执行一次性、自投禁止和余额约束。"""

    author = _create_user(db_session, "constraints_author", coin_balance=1)
    actor = _create_user(db_session, "constraints_actor", coin_balance=1)
    empty_actor = _create_user(db_session, "empty_actor")
    post = Post(author_id=author.id, content="约束测试")
    db_session.add(post)
    db_session.commit()

    coin_service.give_post_coin(db_session, actor.id, post.id)

    with pytest.raises(coin_service.DuplicateCoinError):
        coin_service.give_post_coin(db_session, actor.id, post.id)
    with pytest.raises(coin_service.SelfCoinError):
        coin_service.give_post_coin(db_session, author.id, post.id)
    with pytest.raises(coin_service.InsufficientCoinBalanceError):
        coin_service.give_post_coin(db_session, empty_actor.id, post.id)

    db_session.refresh(post)
    db_session.refresh(author)
    assert post.coin_count == 1
    assert author.coin_balance == 2
    assert db_session.query(PostCoin).count() == 1


def test_give_post_coin_rate_limit_preserves_balances(db_session, monkeypatch) -> None:
    """同一账号超过投币频率时不应继续扣款、收款或增加热度计数。"""

    monkeypatch.setattr(coin_service, "MAX_COIN_TRANSFERS_PER_MINUTE", 1)
    author = _create_user(db_session, "rate_limit_author")
    actor = _create_user(db_session, "rate_limit_actor", coin_balance=2)
    first_post = Post(author_id=author.id, content="第一次投币")
    blocked_post = Post(author_id=author.id, content="被限流的投币")
    db_session.add_all([first_post, blocked_post])
    db_session.commit()

    coin_service.give_post_coin(db_session, actor.id, first_post.id)
    with pytest.raises(coin_service.CoinRateLimitError):
        coin_service.give_post_coin(db_session, actor.id, blocked_post.id)

    db_session.refresh(author)
    db_session.refresh(actor)
    db_session.refresh(blocked_post)
    assert author.coin_balance == 1
    assert actor.coin_balance == 1
    assert blocked_post.coin_count == 0
    assert db_session.query(PostCoin).count() == 1


def test_give_post_coin_rejects_recipient_at_65535_limit(db_session) -> None:
    """作者余额达到 65535 时，投币事务应完整回滚。"""

    author = _create_user(
        db_session,
        "max_balance_author",
        coin_balance=65_535,
    )
    actor = _create_user(db_session, "max_balance_actor", coin_balance=1)
    post = Post(
        author_id=author.id,
        content="余额上限测试",
        coin_count=2_147_483_647,
    )
    db_session.add(post)
    db_session.commit()

    with pytest.raises(coin_service.RecipientCoinBalanceLimitError):
        coin_service.give_post_coin(db_session, actor.id, post.id)

    db_session.refresh(author)
    db_session.refresh(actor)
    db_session.refresh(post)
    assert author.coin_balance == 65_535
    assert actor.coin_balance == 1
    assert post.coin_count == 2_147_483_647
    assert db_session.query(PostCoin).count() == 0


def test_admin_can_set_user_coin_balance_without_changing_streak(db_session) -> None:
    """管理端余额纠错不应伪造登录奖励或改变连续登录状态。"""

    user = _create_user(db_session, "admin_coin_user", coin_balance=2)
    user.login_streak = 4
    db_session.commit()

    updated = coin_service.set_user_coin_balance(db_session, user.id, 65_535)
    db_session.commit()

    assert updated.coin_balance == 65_535
    assert updated.login_streak == 4
    assert db_session.query(DailyCoinReward).count() == 0
    with pytest.raises(ValueError, match="0 到 65535"):
        coin_service.set_user_coin_balance(db_session, user.id, 65_536)
