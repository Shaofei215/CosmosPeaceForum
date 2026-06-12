from __future__ import annotations

from dataclasses import dataclass

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from social_platform.app.domains import registry as domain_models  # noqa: F401
from social_platform.app.admin.models import admin_user  # noqa: F401
from social_platform.app.db.session import Base
from social_platform.app.domains.post.events import PostCreated
from social_platform.app.domains.search import subscribers as search_subscribers
from social_platform.app.domains.comment.models import Comment
from social_platform.app.domains.follow.models import Follow
from social_platform.app.domains.notification.models import Notification
from social_platform.app.domains.post.models import Post
from social_platform.app.domains.user.models import User
from social_platform.app.domains.comment import application as comment_service
from social_platform.app.domains.follow import application as follow_service
from social_platform.app.domains.reaction import application as like_service
from social_platform.app.domains.reaction.events import LikeChanged
from social_platform.app.domains.follow.events import FollowChanged
from social_platform.app.shared.events import subscribe_domain_event
from social_platform.app.services import repost_service
from social_platform.app.shared.events import DomainEvent, EventBus, domain_event_bus


@dataclass(frozen=True)
class SampleEvent(DomainEvent):
    """事件总线测试用事件。"""

    value: int


@pytest.fixture()
def db_session():
    """创建内存数据库会话，供领域事件集成测试使用。"""

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


def _seed_users_and_post(db):
    """写入测试用户与帖子。

    Args:
        db: 当前测试数据库会话。

    Returns:
        tuple[User, User, Post]: 作者、互动用户和帖子。
    """

    author = User(username="author")
    actor = User(username="actor")
    db.add_all([author, actor])
    db.flush()
    post = Post(author_id=author.id, content="hello")
    db.add(post)
    db.commit()
    return author, actor, post


def test_event_bus_runs_handlers_in_subscription_order(db_session):
    bus = EventBus("test")
    calls: list[str] = []

    def first(_, event: SampleEvent) -> None:
        calls.append(f"first:{event.value}")

    def second(_, event: SampleEvent) -> None:
        calls.append(f"second:{event.value}")

    bus.subscribe(SampleEvent, first)
    bus.subscribe(SampleEvent, second)

    bus.publish(db_session, SampleEvent(7))

    assert calls == ["first:7", "second:7"]


def test_event_bus_deduplicates_same_handler(db_session):
    bus = EventBus("test")
    calls: list[int] = []

    def handler(_, event: SampleEvent) -> None:
        calls.append(event.value)

    bus.subscribe(SampleEvent, handler)
    bus.subscribe(SampleEvent, handler)

    bus.publish(db_session, SampleEvent(3))

    assert calls == [3]


def test_event_bus_rollback_clears_after_commit_events(db_session):
    bus = EventBus("test")
    calls: list[int] = []

    def handler(_, event: SampleEvent) -> None:
        calls.append(event.value)

    bus.subscribe(SampleEvent, handler, phase="after_commit")
    bus.publish(db_session, SampleEvent(9))
    bus.clear_pending(db_session)
    bus.dispatch_after_commit(db_session)

    assert calls == []


def test_post_like_creates_notification_and_unlike_does_not_create_more(db_session):
    author, actor, post = _seed_users_and_post(db_session)

    is_liked, like_count = like_service.toggle_like(post.id, actor.id, db_session)
    assert (is_liked, like_count) == (True, 1)

    notifications = db_session.query(Notification).all()
    assert len(notifications) == 1
    assert notifications[0].recipient_id == author.id
    assert notifications[0].sender_id == actor.id
    assert notifications[0].type == "post_like"

    is_liked, like_count = like_service.toggle_like(post.id, actor.id, db_session)
    assert (is_liked, like_count) == (False, 0)
    assert db_session.query(Notification).count() == 1


def test_self_post_like_does_not_create_notification(db_session):
    author, _, post = _seed_users_and_post(db_session)

    like_service.toggle_like(post.id, author.id, db_session)

    assert db_session.query(Notification).count() == 0


def test_comment_create_and_like_notifications_are_event_driven(db_session):
    author, actor, post = _seed_users_and_post(db_session)

    comment = comment_service.create_comment(post.id, actor.id, "first", None, db_session)
    notifications = db_session.query(Notification).all()
    assert len(notifications) == 1
    assert notifications[0].recipient_id == author.id
    assert notifications[0].type == "comment"

    db_session.add(User(username="third"))
    db_session.flush()
    third_user = db_session.query(User).filter(User.username == "third").one()
    comment_service.toggle_like(comment.id, third_user.id, db_session)

    notifications = db_session.query(Notification).order_by(Notification.id).all()
    assert len(notifications) == 2
    assert notifications[1].recipient_id == actor.id
    assert notifications[1].type == "comment_like"


def test_follow_notification_only_created_on_follow(db_session):
    follower = User(username="follower")
    following = User(username="following")
    db_session.add_all([follower, following])
    db_session.commit()

    is_following, _, _ = follow_service.toggle_follow(db_session, follower.id, following.id)
    assert is_following is True
    assert db_session.query(Notification).count() == 1
    assert db_session.query(Notification).one().type == "follow"

    is_following, _, _ = follow_service.toggle_follow(db_session, follower.id, following.id)
    assert is_following is False
    assert db_session.query(Notification).count() == 1
    assert db_session.query(Follow).count() == 0



def test_like_changed_event_carries_previous_and_current_state(db_session):
    captured: list[LikeChanged] = []
    domain_event_bus.subscribe(LikeChanged, lambda _, event: captured.append(event))
    _, actor, post = _seed_users_and_post(db_session)

    like_service.toggle_like(post.id, actor.id, db_session)
    like_service.toggle_like(post.id, actor.id, db_session)

    assert [(event.previous_state, event.current_state) for event in captured[-2:]] == [
        (False, True),
        (True, False),
    ]
    assert captured[-1].target_type == "post"


def test_follow_changed_event_carries_previous_and_current_state(db_session):
    captured: list[FollowChanged] = []
    domain_event_bus.subscribe(FollowChanged, lambda _, event: captured.append(event))
    follower = User(username="event_follower")
    following = User(username="event_following")
    db_session.add_all([follower, following])
    db_session.commit()

    follow_service.toggle_follow(db_session, follower.id, following.id)
    follow_service.toggle_follow(db_session, follower.id, following.id)

    assert [(event.previous_state, event.current_state) for event in captured[-2:]] == [
        (False, True),
        (True, False),
    ]

def test_repost_notification_is_event_driven(db_session):
    author, actor, post = _seed_users_and_post(db_session)

    repost = repost_service.create_repost(
        db=db_session,
        user_id=actor.id,
        source_type="post",
        source_id=post.id,
        content="转一下",
    )

    notifications = db_session.query(Notification).all()
    assert repost.id != post.id
    assert len(notifications) == 1
    assert notifications[0].recipient_id == author.id
    assert notifications[0].type == "repost"


def test_search_projection_subscriber_indexes_post_after_commit(monkeypatch, db_session):
    indexed_post_ids: list[int] = []

    monkeypatch.setattr(search_subscribers, "_index_post_by_id", indexed_post_ids.append)

    search_subscribers.handle_post_created(db_session, PostCreated(post_id=42, author_id=1))

    assert indexed_post_ids == [42]
