from social_platform.app.admin.models.admin_user import PlatformAdminUser  # noqa: F401
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from social_platform.app.db.session import Base
from social_platform.app.domains.post.models import Post
from social_platform.app.domains.search.application import _rank_content_search_posts, search_topic
from social_platform.app.domains.topic.models import PostTopic, Topic
from social_platform.app.domains.user.models import User


def _post(post_id: int, title: str, content: str, heat_score: float) -> Post:
    return Post(
        id=post_id,
        author_id=1,
        title=title,
        content=content,
        heat_score=heat_score,
    )


def test_content_search_heat_only_breaks_close_relevance_ties():
    cool_post = _post(1, "记忆系统设计", "关于记忆系统的实现记录", 0)
    hot_post = _post(2, "记忆系统复盘", "关于记忆系统的线上反馈", 100)

    ranked_posts = _rank_content_search_posts(
        posts=[cool_post, hot_post],
        hit_score_map={1: 10.0, 2: 9.8},
        query="记忆系统",
    )

    assert [post.id for post in ranked_posts] == [2, 1]


def test_content_search_heat_does_not_override_clear_relevance_gap():
    relevant_post = _post(1, "记忆系统设计", "关于记忆系统的实现记录", 0)
    hot_weak_post = _post(2, "平台周报", "一些产品反馈和运营数据", 1000)

    ranked_posts = _rank_content_search_posts(
        posts=[hot_weak_post, relevant_post],
        hit_score_map={1: 10.0, 2: 3.0},
        query="记忆系统",
    )

    assert [post.id for post in ranked_posts] == [1, 2]


def test_content_search_exact_title_match_gets_extra_boost():
    exact_post = _post(1, "记忆系统", "正文", 0)
    contains_post = _post(2, "记忆系统设计", "正文", 0)

    ranked_posts = _rank_content_search_posts(
        posts=[contains_post, exact_post],
        hit_score_map={1: 9.0, 2: 10.0},
        query="记忆系统",
    )

    assert [post.id for post in ranked_posts] == [1, 2]


def test_topic_search_returns_posts_for_topic():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    testing_session_local = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = testing_session_local()
    try:
        user = User(username="alice")
        db.add(user)
        db.commit()
        topic = Topic(name="和平论坛", post_count=1, heat_score=10)
        db.add(topic)
        db.commit()
        post = Post(author_id=user.id, content="#和平论坛# 讨论", heat_score=5)
        db.add(post)
        db.commit()
        db.add(PostTopic(post_id=post.id, topic_id=topic.id))
        db.commit()

        result = search_topic(db, "#和平论坛#", page=1, page_size=20)

        assert result.pagination.total == 1
        assert result.data[0].id == post.id
        assert result.data[0].topic_mentions[0].name == "和平论坛"
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)
