"""评论领域事件。"""

from __future__ import annotations

from dataclasses import dataclass

from social_platform.app.shared.events import DomainEvent


@dataclass(frozen=True)
class CommentCreated(DomainEvent):
    """评论或回复创建事件。"""

    post_id: int
    comment_id: int
    sender_id: int
    parent_comment_id: int | None = None


@dataclass(frozen=True)
class CommentDeleted(DomainEvent):
    """评论删除事件。"""

    comment_id: int
    post_id: int
    owner_id: int
    root_comment_id: int | None = None
