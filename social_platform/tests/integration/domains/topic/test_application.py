import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from social_platform.app.db.session import Base
from social_platform.app.domains.post.models import Post
from social_platform.app.domains.topic import application as topic_service
from social_platform.app.domains.topic.models import PostTopic, Topic
from social_platform.app.domains.user.models import User


@pytest.fixture()
def db_session():
    """创建内存数据库会话，供话题服务测试使用。"""

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    testing_session_local = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = testing_session_local()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


def test_extract_topic_names_keeps_order_and_deduplicates():
    names = topic_service.extract_topic_names("#和平论坛# 今天讨论 #AI-Agent# 和 #和平论坛#")

    assert names == ["和平论坛", "AI-Agent"]


def test_sync_post_topics_creates_topics_and_refreshes_stats(db_session):
    user = User(username="alice")
    db_session.add(user)
    db_session.commit()
    post = Post(author_id=user.id, content="聊聊 #和平论坛# 和 #AI#。", heat_score=9)
    db_session.add(post)
    db_session.commit()

    topic_service.sync_post_topics(db_session, post.id, post.content)
    db_session.commit()

    topics = db_session.query(Topic).order_by(Topic.name.asc()).all()
    assert [topic.name for topic in topics] == ["AI", "和平论坛"]
    assert all(topic.post_count == 1 for topic in topics)
    assert all(topic.heat_score > 0 for topic in topics)


def test_sync_post_topics_removes_stale_associations(db_session):
    user = User(username="alice")
    db_session.add(user)
    db_session.commit()
    post = Post(author_id=user.id, content="#旧话题#", heat_score=1)
    db_session.add(post)
    db_session.commit()

    topic_service.sync_post_topics(db_session, post.id, "#旧话题#")
    topic_service.sync_post_topics(db_session, post.id, "#新话题#")
    db_session.commit()

    assert db_session.query(PostTopic).count() == 1
    old_topic = db_session.query(Topic).filter(Topic.name == "旧话题").one()
    new_topic = db_session.query(Topic).filter(Topic.name == "新话题").one()
    assert old_topic.post_count == 0
    assert new_topic.post_count == 1


def test_list_trending_topics_only_returns_used_topics(db_session):
    used = Topic(name="已使用", post_count=2, heat_score=10)
    unused = Topic(name="未使用", post_count=0, heat_score=100)
    db_session.add_all([used, unused])
    db_session.commit()

    topics = topic_service.list_trending_topics(db_session)

    assert [topic.name for topic in topics] == ["已使用"]
