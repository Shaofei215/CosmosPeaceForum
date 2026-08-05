"""热度领域事件订阅器。

热度是可由领域状态重算的排序维护能力，不由点赞、评论或转发应用服务直接刷新。
本模块在 ``before_commit`` 阶段使用当前事务会话更新热度字段，保证写操作返回后
数据库中的排序分数与冗余计数保持一致。
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from social_platform.app.domains.comment.events import CommentCreated, CommentDeleted
from social_platform.app.domains.comment.models import Comment
from social_platform.app.domains.coin.events import PostCoinGiven
from social_platform.app.domains.heat import application as heat_application
from social_platform.app.domains.post.events import PostCreated, RepostCountChanged, RepostCreated
from social_platform.app.domains.post.models import Post
from social_platform.app.domains.reaction.events import DislikeChanged, LikeChanged
from social_platform.app.shared.events import subscribe_domain_event


def _refresh_post_by_id(db: Session, post_id: int | None) -> None:
    """按帖子 ID 刷新热度。"""

    if post_id is None:
        return
    post = db.query(Post).filter(Post.id == post_id).first()
    if post is not None:
        heat_application.refresh_post_heat_score(db, post)


def _refresh_comment_by_id(db: Session, comment_id: int | None) -> None:
    """按评论 ID 刷新热度。"""

    if comment_id is None:
        return
    comment = db.query(Comment).filter(Comment.id == comment_id).first()
    if comment is not None:
        heat_application.refresh_comment_heat_score(db, comment)


def handle_like_changed(db: Session, event: LikeChanged) -> None:
    """根据点赞状态变化刷新对应资源热度。"""

    if event.target_type == "post":
        _refresh_post_by_id(db, event.target_id)
        return
    _refresh_comment_by_id(db, event.target_id)


def handle_dislike_changed(db: Session, event: DislikeChanged) -> None:
    """根据点踩状态变化刷新帖子热度。"""

    _refresh_post_by_id(db, event.post_id)


def handle_post_coin_given(db: Session, event: PostCoinGiven) -> None:
    """投币成功后立即刷新目标帖子热度。"""

    _refresh_post_by_id(db, event.post_id)


def handle_comment_created(db: Session, event: CommentCreated) -> None:
    """评论创建后刷新帖子、新评论和所属一级评论热度。"""

    _refresh_post_by_id(db, event.post_id)
    comment = db.query(Comment).filter(Comment.id == event.comment_id).first()
    if comment is None:
        return
    heat_application.refresh_comment_heat_score(db, comment)
    _refresh_comment_by_id(db, comment.root_comment_id)


def handle_comment_deleted(db: Session, event: CommentDeleted) -> None:
    """评论删除后刷新帖子和仍存在的所属一级评论热度。"""

    _refresh_post_by_id(db, event.post_id)
    _refresh_comment_by_id(db, event.root_comment_id)


def handle_post_created(db: Session, event: PostCreated) -> None:
    """帖子创建后初始化热度。"""

    _refresh_post_by_id(db, event.post_id)


def handle_repost_created(db: Session, event: RepostCreated) -> None:
    """转发创建后刷新转发帖、源帖和根帖热度。"""

    _refresh_post_by_id(db, event.repost_id)
    _refresh_post_by_id(db, event.source_post_id)
    _refresh_post_by_id(db, event.root_post_id)


def handle_repost_count_changed(db: Session, event: RepostCountChanged) -> None:
    """转发计数增减后刷新所有受影响帖子的热度。"""

    for post_id in event.post_ids:
        _refresh_post_by_id(db, post_id)


def register_heat_subscribers() -> None:
    """注册热度领域事件订阅器。"""

    subscribe_domain_event(LikeChanged, handle_like_changed)
    subscribe_domain_event(DislikeChanged, handle_dislike_changed)
    subscribe_domain_event(PostCoinGiven, handle_post_coin_given)
    subscribe_domain_event(CommentCreated, handle_comment_created)
    subscribe_domain_event(CommentDeleted, handle_comment_deleted)
    subscribe_domain_event(PostCreated, handle_post_created)
    subscribe_domain_event(RepostCreated, handle_repost_created)
    subscribe_domain_event(RepostCountChanged, handle_repost_count_changed)
