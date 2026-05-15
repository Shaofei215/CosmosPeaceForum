import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app_platform.app.db.session import Base
from app_platform.app.models import Comment, Notification, Post, User
from app_platform.app.services import notification_service


@pytest.fixture()
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    testing_session_local = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = testing_session_local()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


def _seed_comment_thread(db):
    post_author = User(username="post_author")
    comment_owner = User(username="comment_owner")
    replier = User(username="replier")
    db.add_all([post_author, comment_owner, replier])
    db.flush()

    post = Post(author_id=post_author.id, content="post")
    db.add(post)
    db.flush()

    parent_comment = Comment(
        post_id=post.id,
        owner_id=comment_owner.id,
        content="parent comment",
    )
    db.add(parent_comment)
    db.flush()

    reply = Comment(
        post_id=post.id,
        owner_id=replier.id,
        parent_id=parent_comment.id,
        content="reply",
    )
    db.add(reply)
    db.flush()

    return post_author, comment_owner, replier, post, parent_comment, reply


def test_comment_reply_notifies_parent_comment_owner_only(db_session):
    db = db_session
    post_author, comment_owner, replier, post, parent_comment, reply = _seed_comment_thread(db)

    notification_service.create_comment_notifications(
        db=db,
        post=post,
        comment=reply,
        sender_id=replier.id,
        parent_comment=parent_comment,
    )
    db.flush()

    notifications = db.query(Notification).all()
    assert len(notifications) == 1
    assert notifications[0].recipient_id == comment_owner.id
    assert notifications[0].recipient_id != post_author.id
    assert notifications[0].type == "comment_reply"
    assert notifications[0].comment_id == reply.id


def test_top_level_comment_notifies_post_author(db_session):
    db = db_session
    post_author = User(username="post_author")
    commenter = User(username="commenter")
    db.add_all([post_author, commenter])
    db.flush()

    post = Post(author_id=post_author.id, content="post")
    db.add(post)
    db.flush()

    comment = Comment(post_id=post.id, owner_id=commenter.id, content="comment")
    db.add(comment)
    db.flush()

    notification_service.create_comment_notifications(
        db=db,
        post=post,
        comment=comment,
        sender_id=commenter.id,
    )
    db.flush()

    notifications = db.query(Notification).all()
    assert len(notifications) == 1
    assert notifications[0].recipient_id == post_author.id
    assert notifications[0].type == "comment"
    assert notifications[0].comment_id == comment.id
