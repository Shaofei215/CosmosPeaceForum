"""帖子话题领域事件订阅器。

话题关联和热度是由帖子正文与互动状态派生出的投影。本模块订阅帖子、评论、
点赞和转发事件，在主事务内维护该投影。
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from social_platform.app.domains.comment.events import CommentCreated, CommentDeleted
from social_platform.app.domains.post.events import PostCreated, PostDeleted, PostUpdated, RepostCreated
from social_platform.app.domains.post.models import Post
from social_platform.app.domains.reaction.events import LikeChanged
from social_platform.app.domains.topic import application as topic_application
from social_platform.app.shared.events import subscribe_domain_event


def _sync_post_by_id(db: Session, post_id: int | None) -> None:
    """按帖子 ID 同步正文话题。"""

    if post_id is None:
        return
    post = db.query(Post).filter(Post.id == post_id).first()
    if post is None or post.moderation_status != "active":
        topic_application.remove_post_topics(db, post_id)
        return
    topic_application.sync_post_topics(db, post.id, post.content)


def handle_post_created(db: Session, event: PostCreated) -> None:
    """帖子创建后同步话题关联。"""

    _sync_post_by_id(db, event.post_id)


def handle_post_updated(db: Session, event: PostUpdated) -> None:
    """帖子更新后重新解析话题关联。"""

    _sync_post_by_id(db, event.post_id)


def handle_post_deleted(db: Session, event: PostDeleted) -> None:
    """帖子删除后移除话题关联。"""

    topic_application.remove_post_topics(db, event.post_id)


def handle_repost_created(db: Session, event: RepostCreated) -> None:
    """转发创建后同步新转发帖话题，并刷新源帖话题热度。"""

    _sync_post_by_id(db, event.repost_id)
    topic_application.refresh_topics_for_post(db, event.source_post_id)
    topic_application.refresh_topics_for_post(db, event.root_post_id)


def handle_like_changed(db: Session, event: LikeChanged) -> None:
    """点赞状态变化后刷新相关帖子的话题热度。"""

    topic_application.refresh_topics_for_post(db, event.post_id or event.target_id)


def handle_comment_created(db: Session, event: CommentCreated) -> None:
    """评论创建后刷新所属帖子的话题热度。"""

    topic_application.refresh_topics_for_post(db, event.post_id)


def handle_comment_deleted(db: Session, event: CommentDeleted) -> None:
    """评论删除后刷新所属帖子的话题热度。"""

    topic_application.refresh_topics_for_post(db, event.post_id)


def register_topic_subscribers() -> None:
    """注册帖子话题领域事件订阅器。"""

    subscribe_domain_event(PostCreated, handle_post_created)
    subscribe_domain_event(PostUpdated, handle_post_updated)
    subscribe_domain_event(PostDeleted, handle_post_deleted)
    subscribe_domain_event(RepostCreated, handle_repost_created)
    subscribe_domain_event(LikeChanged, handle_like_changed)
    subscribe_domain_event(CommentCreated, handle_comment_created)
    subscribe_domain_event(CommentDeleted, handle_comment_deleted)
