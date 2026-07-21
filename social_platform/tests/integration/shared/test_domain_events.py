from __future__ import annotations

from dataclasses import dataclass

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from social_platform.app.domains import registry as domain_models  # noqa: F401
from social_platform.app.admin.models import admin_user  # noqa: F401
from social_platform.app.db.session import Base
from social_platform.app.domains.post.events import PostCreated, RepostCreated
from social_platform.app.domains.search import subscribers as search_subscribers
from social_platform.app.domains.comment.models import Comment
from social_platform.app.domains.follow.models import Follow
from social_platform.app.domains.notification.models import Notification
from social_platform.app.domains.post.models import PollVote, Post
from social_platform.app.domains.reaction.models import Like
from social_platform.app.domains.post.schemas import PostCreate
from social_platform.app.domains.content_safety import application as report_service
from social_platform.app.domains.content_safety.models import ContentReport
from social_platform.app.domains.user.models import User
from social_platform.app.domains.user import application as user_application
from social_platform.app.domains.comment import application as comment_service
from social_platform.app.domains.follow import application as follow_service
from social_platform.app.domains.post import application as post_application
from social_platform.app.domains.post import poll_application
from social_platform.app.domains.reaction import application as like_service
from social_platform.app.domains.reaction.events import LikeChanged
from social_platform.app.domains.follow.events import FollowChanged
from social_platform.app.shared.events import subscribe_domain_event
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


def test_agent_post_like_and_notification_keep_operation_source(db_session):
    """Agent 通道创建的点赞关系和派生通知应保存同一来源。"""

    author, actor, post = _seed_users_and_post(db_session)

    like_service.toggle_like(
        post.id,
        actor.id,
        db_session,
        created_by_agent=True,
    )

    like = db_session.query(Like).one()
    notification = db_session.query(Notification).one()
    assert like.created_by_agent is True
    assert notification.created_by_agent is True


def test_agent_source_is_saved_for_post_follow_vote_and_report(db_session):
    """其余持久社交关系也应保存显式传入的 Agent 来源。"""

    author = User(username="source_author")
    actor = User(username="source_actor")
    db_session.add_all([author, actor])
    db_session.commit()

    post = post_application.create_post(
        db_session,
        author,
        PostCreate(content="poll", poll_options=["A", "B"]),
        created_by_agent=True,
    )
    follow_service.toggle_follow(
        db_session,
        actor.id,
        author.id,
        created_by_agent=True,
    )
    poll_application.vote_poll(
        db_session,
        actor,
        post.id,
        post.poll_options[0].id,
        created_by_agent=True,
    )
    report_service.create_content_report(
        db_session,
        reporter=actor,
        target_type="post",
        target_id=post.id,
        reason="test",
        created_by_agent=True,
    )

    assert post.created_by_agent is True
    assert db_session.query(Follow).one().created_by_agent is True
    assert db_session.query(PollVote).one().created_by_agent is True
    assert db_session.query(ContentReport).one().created_by_agent is True


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


def test_agent_comment_and_notification_keep_operation_source(db_session):
    """Agent 通道创建的评论及其通知应保存同一来源。"""

    _, actor, post = _seed_users_and_post(db_session)

    comment = comment_service.create_comment(
        post.id,
        actor.id,
        "agent comment",
        None,
        db_session,
        created_by_agent=True,
    )

    notification = db_session.query(Notification).one()
    assert comment.created_by_agent is True
    assert notification.created_by_agent is True


def test_post_mention_creates_notification_for_each_existing_user_once(db_session):
    """新帖子应按用户名去重发送提及通知，并保留帖子原文和操作目标。"""

    author = User(username="mention_author")
    mentioned = User(username="mentioned_user")
    db_session.add_all([author, mentioned])
    db_session.commit()

    post = post_application.create_post(
        db_session,
        author,
        PostCreate(
            content="你好 @mentioned_user，再次 @mentioned_user，忽略 @missing_user",
        ),
    )

    notification = db_session.query(Notification).one()
    assert notification.recipient_id == mentioned.id
    assert notification.sender_id == author.id
    assert notification.type == "mention"
    assert notification.resource_type == "post"
    assert notification.resource_id == post.id
    assert notification.post_id == post.id
    assert notification.comment_id is None
    assert notification.source_content == post.content


def test_comment_mention_uses_mention_instead_of_duplicate_comment_notification(db_session):
    """同一评论的常规接收者被提及时应只收到更具体的提及通知。"""

    author, actor, post = _seed_users_and_post(db_session)

    comment = comment_service.create_comment(
        post.id,
        actor.id,
        "正文中提及 @author",
        None,
        db_session,
    )

    notification = db_session.query(Notification).one()
    assert notification.recipient_id == author.id
    assert notification.type == "mention"
    assert notification.resource_type == "comment"
    assert notification.resource_id == comment.id
    assert notification.post_id == post.id
    assert notification.comment_id == comment.id
    assert notification.source_content == comment.content


def test_self_mention_does_not_create_notification(db_session):
    """用户在自己的帖子中提及自己时不应产生通知。"""

    author = User(username="self_mention")
    db_session.add(author)
    db_session.commit()

    post_application.create_post(
        db_session,
        author,
        PostCreate(content="@self_mention 自我记录"),
    )

    assert db_session.query(Notification).count() == 0


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

    repost = post_application.create_repost(
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


def test_deleting_repost_decrements_direct_and_chained_counters(db_session):
    """删除链式转发会同时回减直接源帖和根帖，且直接转发只计数一次。"""

    author, actor, root = _seed_users_and_post(db_session)
    third = User(username="third-reposter")
    db_session.add(third)
    db_session.commit()
    first = post_application.create_repost(
        db=db_session,
        user_id=actor.id,
        source_type="post",
        source_id=root.id,
    )
    second = post_application.create_repost(
        db=db_session,
        user_id=third.id,
        source_type="post",
        source_id=first.id,
    )
    db_session.refresh(root)
    db_session.refresh(first)
    assert root.repost_count == 2
    assert first.repost_count == 1

    post_application.delete_post(db_session, third, second.id)

    db_session.refresh(root)
    db_session.refresh(first)
    assert root.repost_count == 1
    assert first.repost_count == 0
    post_application.delete_post(db_session, actor, first.id)
    db_session.refresh(root)
    assert root.repost_count == 0


def test_deleting_comment_repost_decrements_source_post_counter(db_session):
    """评论转发删除时会找到评论所属帖子并回减计数。"""

    author, actor, root = _seed_users_and_post(db_session)
    comment = Comment(post_id=root.id, owner_id=author.id, content="source comment")
    db_session.add(comment)
    db_session.commit()
    repost = post_application.create_repost(
        db=db_session,
        user_id=actor.id,
        source_type="comment",
        source_id=comment.id,
    )
    db_session.refresh(root)
    assert root.repost_count == 1

    post_application.delete_post(db_session, actor, repost.id)
    db_session.refresh(root)
    assert root.repost_count == 0


def test_user_deletion_repairs_follow_and_repost_counters(db_session):
    """用户注销前显式回减其他用户的关注与转发冗余计数。"""

    owner, deleting_user, root = _seed_users_and_post(db_session)
    follow_service.toggle_follow(db_session, deleting_user.id, owner.id)
    follow_service.toggle_follow(db_session, owner.id, deleting_user.id)
    post_application.create_repost(
        db=db_session,
        user_id=deleting_user.id,
        source_type="post",
        source_id=root.id,
    )

    user_application.delete_user(db_session, deleting_user, deleting_user.id)

    db_session.refresh(owner)
    db_session.refresh(root)
    assert owner.followers_count == 0
    assert owner.following_count == 0
    assert root.repost_count == 0


def test_search_projection_subscriber_indexes_post_after_commit(monkeypatch, db_session):
    indexed_post_ids: list[int] = []

    monkeypatch.setattr(search_subscribers, "_index_post_by_id", indexed_post_ids.append)

    search_subscribers.handle_post_created(db_session, PostCreated(post_id=42, author_id=1))

    assert indexed_post_ids == [42]


def test_search_projection_subscriber_indexes_repost_after_commit(monkeypatch, db_session):
    indexed_post_ids: list[int] = []

    monkeypatch.setattr(search_subscribers, "_index_post_by_id", indexed_post_ids.append)

    search_subscribers.handle_repost_created(
        db_session,
        RepostCreated(root_post_id=1, repost_id=43, sender_id=2, source_post_id=1),
    )

    assert indexed_post_ids == [43]
