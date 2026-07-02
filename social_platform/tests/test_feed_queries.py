from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from social_platform.app.admin.models.admin_user import PlatformAdminUser  # noqa: F401
from social_platform.app.db.session import Base
from social_platform.app.domains import registry as domain_models  # noqa: F401
from social_platform.app.domains.feed import queries as feed_queries
from social_platform.app.domains.follow.models import Follow
from social_platform.app.domains.post.models import Post
from social_platform.app.domains.reaction.models import Like
from social_platform.app.domains.user.models import User


@pytest.fixture()
def db_session() -> Session:
    """创建 feed 领域测试使用的内存数据库会话。

    Yields:
        Session: 已创建全部领域表的 SQLAlchemy 会话。
    """

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    session_local = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = session_local()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


def _seed_feed_data(db: Session) -> dict[str, User | Post]:
    """写入 feed 查询测试所需的用户、帖子、点赞与关注数据。

    Args:
        db: 当前测试数据库会话。

    Returns:
        dict[str, User | Post]: 关键测试对象映射。
    """

    now = datetime(2026, 1, 1, 12, 0, 0)
    viewer = User(id=1, username="viewer")
    author = User(id=2, username="author", bio="作者简介", avatar_url="/avatars/author.png")
    mutual_author = User(id=3, username="mutual")
    origin_author = User(id=4, username="origin")
    db.add_all([viewer, author, mutual_author, origin_author])
    db.flush()

    origin_post = Post(
        id=10,
        author_id=origin_author.id,
        title="源文章",
        type="article",
        content="origin content",
        created_at=now - timedelta(days=1),
        heat_score=12,
    )
    older_hot_post = Post(
        id=11,
        author_id=author.id,
        content="hello @viewer",
        created_at=now - timedelta(minutes=10),
        heat_score=80,
        like_count=1,
        comment_count=2,
        repost_count=3,
    )
    newer_post = Post(
        id=12,
        author_id=mutual_author.id,
        content="newer post",
        created_at=now,
        heat_score=20,
        created_by_agent=True,
    )
    repost = Post(
        id=13,
        author_id=author.id,
        content="转发 @origin",
        created_at=now - timedelta(minutes=5),
        heat_score=40,
        repost_source_type="post",
        repost_source_id=origin_post.id,
        repost_root_post_id=origin_post.id,
        repost_chain="转发 @origin",
    )
    db.add_all([origin_post, older_hot_post, newer_post, repost])
    db.add_all(
        [
            Like(user_id=viewer.id, post_id=older_hot_post.id),
            Follow(follower_id=viewer.id, following_id=author.id),
            Follow(follower_id=viewer.id, following_id=mutual_author.id),
            Follow(follower_id=mutual_author.id, following_id=viewer.id),
        ]
    )
    db.commit()
    return {
        "viewer": viewer,
        "author": author,
        "mutual_author": mutual_author,
        "origin_post": origin_post,
        "older_hot_post": older_hot_post,
        "newer_post": newer_post,
        "repost": repost,
    }


def test_feed_type_aliases_and_invalid_type() -> None:
    """验证推荐流历史别名与非法类型校验保持兼容。"""

    assert feed_queries.normalize_feed_type("recommended") == "recommended"
    assert feed_queries.normalize_feed_type("recommend") == "recommended"
    assert feed_queries.normalize_feed_type("hot") == "recommended"

    with pytest.raises(ValueError, match="feed_type"):
        feed_queries.normalize_feed_type("unknown")


def test_anonymous_following_feed_returns_empty_page(db_session: Session) -> None:
    """匿名访问关注流时返回空列表和稳定分页信息。"""

    _seed_feed_data(db_session)

    response = feed_queries.get_feed(
        db=db_session,
        page=1,
        page_size=20,
        current_user_id=None,
        feed_type="following",
    )

    assert response.data == []
    assert response.pagination is not None
    assert response.pagination.total == 0
    assert response.pagination.total_pages == 0


def test_latest_feed_orders_by_created_at_and_id(db_session: Session) -> None:
    """最新流按创建时间倒序和 ID 倒序返回。"""

    _seed_feed_data(db_session)

    response = feed_queries.get_feed(
        db=db_session,
        page=1,
        page_size=4,
        current_user_id=1,
        feed_type="latest",
    )

    assert [item.id for item in response.data] == [12, 13, 11, 10]


def test_recommended_feed_is_stable_for_same_seed(db_session: Session) -> None:
    """推荐流在同一 seed 下保持分页结果稳定。"""

    _seed_feed_data(db_session)

    first = feed_queries.get_feed(
        db=db_session,
        page=1,
        page_size=4,
        current_user_id=1,
        feed_type="recommended",
        seed="stable-seed",
    )
    second = feed_queries.get_feed(
        db=db_session,
        page=1,
        page_size=4,
        current_user_id=1,
        feed_type="hot",
        seed="stable-seed",
    )

    assert [item.id for item in first.data] == [item.id for item in second.data]
    assert sorted(item.id for item in first.data) == [10, 11, 12, 13]


def test_feed_items_include_user_state_repost_and_mentions(db_session: Session) -> None:
    """信息流响应项保留点赞、关注、转发源和提及用户字段。"""

    _seed_feed_data(db_session)

    response = feed_queries.get_feed(
        db=db_session,
        page=1,
        page_size=4,
        current_user_id=1,
        feed_type="latest",
    )
    items = {item.id: item for item in response.data}

    liked_item = items[11]
    assert liked_item.is_liked is True
    assert liked_item.author_name == "author"
    assert liked_item.author_avatar == "/avatars/author.png"
    assert liked_item.author_bio == "作者简介"
    assert liked_item.author_is_following is True
    assert liked_item.author_is_followed_by is False
    assert liked_item.author_is_mutual is False
    assert liked_item.like_count == 1
    assert liked_item.comment_count == 2
    assert liked_item.repost_count == 3
    assert [user.username for user in liked_item.mention_users] == ["viewer"]

    mutual_item = items[12]
    assert mutual_item.created_by_agent is True
    assert mutual_item.author_is_following is True
    assert mutual_item.author_is_followed_by is True
    assert mutual_item.author_is_mutual is True

    repost_item = items[13]
    assert repost_item.repost_source_type == "post"
    assert repost_item.repost_source_id == 10
    assert repost_item.repost_root_post_id == 10
    assert repost_item.repost_origin is not None
    assert repost_item.repost_origin.id == 10
    assert repost_item.repost_origin_missing is False
    assert [user.username for user in repost_item.repost_chain_authors] == ["origin"]


def test_user_feed_raises_when_user_missing(db_session: Session) -> None:
    """指定用户帖子流在用户不存在时抛出 ValueError。"""

    with pytest.raises(ValueError, match="用户不存在"):
        feed_queries.get_user_feed(
            db=db_session,
            user_id=404,
            page=1,
            page_size=20,
            current_user_id=None,
        )
