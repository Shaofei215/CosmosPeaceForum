import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from social_platform.app.db.session import Base
from social_platform.app.domains import registry as domain_models  # noqa: F401
from social_platform.app.domains.comment.models import Comment
from social_platform.app.domains.post.models import Post
from social_platform.app.domains.user.models import User
from social_platform.app.domains.comment import application as comment_service


@pytest.fixture
def db_session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()
    try:
        db.add_all(
            [
                User(id=1, username="post_author"),
                User(id=2, username="root_author"),
                User(id=3, username="reply_author"),
                User(id=4, username="nested_reply_author"),
            ]
        )
        db.add(Post(id=1, author_id=1, content="hello"))
        db.commit()
        yield db
    finally:
        db.close()


def test_replies_to_replies_are_flattened_under_thread_root(db_session):
    db = db_session

    root = comment_service.create_comment(1, 2, "root", None, db)
    reply_to_root = comment_service.create_comment(1, 3, "reply to root", root.id, db)
    reply_to_reply = comment_service.create_comment(1, 4, "reply to reply", reply_to_root.id, db)

    db.refresh(root)
    db.refresh(reply_to_root)
    db.refresh(reply_to_reply)

    assert reply_to_root.parent_id == root.id
    assert reply_to_root.root_comment_id == root.id
    assert reply_to_reply.parent_id == reply_to_root.id
    assert reply_to_reply.root_comment_id == root.id
    assert root.reply_count == 2
    assert reply_to_root.reply_count == 0

    top_level_comments, top_level_total = comment_service.get_comment_tree(
        post_id=1,
        user_id=None,
        skip=0,
        limit=20,
        db=db,
        sort="latest",
    )

    assert top_level_total == 1
    assert [comment.id for comment in top_level_comments] == [root.id]
    assert top_level_comments[0].children == []

    replies, reply_total = comment_service.get_comment_replies(
        post_id=1,
        comment_id=root.id,
        user_id=None,
        skip=0,
        limit=20,
        db=db,
        sort="latest",
    )

    assert reply_total == 2
    assert [comment.id for comment in replies] == [reply_to_reply.id, reply_to_root.id]
    assert all(comment.children == [] for comment in replies)
    assert replies[0].parent.id == reply_to_root.id
    assert replies[0].parent.owner.username == "reply_author"


def test_deleting_reply_keeps_other_flat_replies_in_thread(db_session):
    db = db_session

    root = comment_service.create_comment(1, 2, "root", None, db)
    reply_to_root = comment_service.create_comment(1, 3, "reply to root", root.id, db)
    reply_to_reply = comment_service.create_comment(1, 4, "reply to reply", reply_to_root.id, db)

    assert comment_service.delete_comment(reply_to_root.id, 3, db) is True

    root = db.get(Comment, root.id)
    remaining_reply = db.get(Comment, reply_to_reply.id)
    post = db.get(Post, 1)
    replies, reply_total = comment_service.get_comment_replies(
        post_id=1,
        comment_id=root.id,
        user_id=None,
        skip=0,
        limit=20,
        db=db,
        sort="latest",
    )

    assert root.reply_count == 1
    assert post.comment_count == 2
    assert remaining_reply.parent_id == root.id
    assert remaining_reply.root_comment_id == root.id
    assert reply_total == 1
    assert [comment.id for comment in replies] == [remaining_reply.id]


def test_comment_tree_uses_stored_reply_count_without_legacy_recount(db_session):
    db = db_session

    root = comment_service.create_comment(1, 2, "root", None, db)
    reply_to_root = comment_service.create_comment(1, 3, "reply to root", root.id, db)
    reply_to_reply = comment_service.create_comment(1, 4, "reply to reply", reply_to_root.id, db)

    root.reply_count = 0
    reply_to_root.root_comment_id = None
    reply_to_reply.root_comment_id = None
    db.commit()
    db.expire_all()

    top_level_comments, top_level_total = comment_service.get_comment_tree(
        post_id=1,
        user_id=None,
        skip=0,
        limit=20,
        db=db,
        sort="latest",
    )

    assert top_level_total == 1
    assert top_level_comments[0].id == root.id
    assert top_level_comments[0].reply_count == 0

    replies, reply_total = comment_service.get_comment_replies(
        post_id=1,
        comment_id=root.id,
        user_id=None,
        skip=0,
        limit=20,
        db=db,
        sort="latest",
    )

    assert reply_total == 2
    assert [comment.id for comment in replies] == [reply_to_reply.id, reply_to_root.id]

    focused_reply = comment_service.get_comment_by_id(reply_to_reply.id, user_id=None, db=db)
    assert focused_reply.root_comment_id == root.id
