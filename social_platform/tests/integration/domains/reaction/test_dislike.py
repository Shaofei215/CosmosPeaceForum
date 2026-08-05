"""帖子点踩领域集成测试。"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from social_platform.app.db.session import Base
from social_platform.app.domains import registry as domain_models  # noqa: F401
from social_platform.app.domains.notification.models import Notification
from social_platform.app.domains.post.models import Post
from social_platform.app.domains.reaction import application as reaction_service
from social_platform.app.domains.reaction.models import Dislike, Like
from social_platform.app.domains.user.models import User


@pytest.fixture()
def db_session():
    """创建启用完整领域模型的内存数据库会话。"""

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


def _create_user(db_session, username: str) -> User:
    """创建测试用户并刷新主键。"""

    user = User(username=username)
    db_session.add(user)
    db_session.flush()
    return user


def test_dislike_is_mutually_exclusive_with_like_and_reduces_heat(db_session) -> None:
    """点踩应替换点赞、降低热度，之后点赞也应反向移除点踩。"""

    author = _create_user(db_session, "dislike_author")
    actor = _create_user(db_session, "dislike_actor")
    post = Post(author_id=author.id, content="互动互斥测试")
    db_session.add(post)
    db_session.commit()

    reaction_service.toggle_like(post.id, actor.id, db_session)
    db_session.refresh(post)
    liked_heat = post.heat_score

    result = reaction_service.toggle_dislike(
        post.id,
        actor.id,
        db_session,
        created_by_agent=True,
        archive_threshold=100,
    )
    db_session.refresh(post)

    assert result.is_disliked is True
    assert result.is_liked is False
    assert post.like_count == 0
    assert post.dislike_count == 1
    assert post.heat_score < liked_heat
    assert db_session.query(Like).count() == 0
    assert db_session.query(Dislike).one().created_by_agent is True

    is_liked, like_count = reaction_service.toggle_like(post.id, actor.id, db_session)
    db_session.refresh(post)
    assert (is_liked, like_count) == (True, 1)
    assert post.dislike_count == 0
    assert db_session.query(Dislike).count() == 0


def test_dislike_rejects_self_and_can_be_cancelled(db_session) -> None:
    """作者不能踩自己；其他用户再次操作可以取消点踩。"""

    author = _create_user(db_session, "self_dislike_author")
    actor = _create_user(db_session, "cancel_dislike_actor")
    post = Post(author_id=author.id, content="取消点踩测试")
    db_session.add(post)
    db_session.commit()

    with pytest.raises(reaction_service.SelfDislikeError):
        reaction_service.toggle_dislike(
            post.id,
            author.id,
            db_session,
            archive_threshold=100,
        )

    reaction_service.toggle_dislike(
        post.id,
        actor.id,
        db_session,
        archive_threshold=100,
    )
    result = reaction_service.toggle_dislike(
        post.id,
        actor.id,
        db_session,
        archive_threshold=100,
    )
    assert result.is_disliked is False
    assert result.dislike_count == 0
    assert db_session.query(Dislike).count() == 0


def test_dislike_rate_limit_blocks_mass_actions(db_session, monkeypatch) -> None:
    """同一账号短时间跨帖子点踩达到上限后应被拒绝。"""

    monkeypatch.setattr(reaction_service, "MAX_DISLIKES_PER_MINUTE", 1)
    author = _create_user(db_session, "rate_dislike_author")
    actor = _create_user(db_session, "rate_dislike_actor")
    first_post = Post(author_id=author.id, content="第一次点踩")
    blocked_post = Post(author_id=author.id, content="被限流的点踩")
    db_session.add_all([first_post, blocked_post])
    db_session.commit()

    reaction_service.toggle_dislike(
        first_post.id,
        actor.id,
        db_session,
        archive_threshold=100,
    )
    with pytest.raises(reaction_service.DislikeRateLimitError):
        reaction_service.toggle_dislike(
            blocked_post.id,
            actor.id,
            db_session,
            archive_threshold=100,
        )

    db_session.refresh(blocked_post)
    assert blocked_post.dislike_count == 0
    assert db_session.query(Dislike).count() == 1


def test_dislike_threshold_archives_post_and_notifies_author(db_session) -> None:
    """不同用户的点踩达到阈值后应归档帖子并发送站内管理通知。"""

    author = _create_user(db_session, "threshold_author")
    first_actor = _create_user(db_session, "threshold_actor_1")
    second_actor = _create_user(db_session, "threshold_actor_2")
    post = Post(author_id=author.id, content="达到阈值后删除")
    db_session.add(post)
    db_session.commit()

    first = reaction_service.toggle_dislike(
        post.id,
        first_actor.id,
        db_session,
        archive_threshold=2,
    )
    second = reaction_service.toggle_dislike(
        post.id,
        second_actor.id,
        db_session,
        archive_threshold=2,
    )

    db_session.refresh(post)
    notification = db_session.query(Notification).one()
    assert first.archived is False
    assert second.archived is True
    assert post.moderation_status == "archived"
    assert post.dislike_count == 2
    assert post.archive_reason == "点踩人数达到自动删除阈值（2）"
    assert notification.type == "moderation"
    assert notification.recipient_id == author.id
    assert "收到 2 次点踩" in (notification.source_content or "")
    assert db_session.query(Dislike).count() == 2

    with pytest.raises(reaction_service.PostNotFoundError):
        reaction_service.get_dislike_status(post.id, first_actor.id, db_session)
