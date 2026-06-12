"""帖子领域事件。

事件由帖子领域发布，消费方领域通过事件总线订阅。
"""

from __future__ import annotations

from dataclasses import dataclass

from social_platform.app.shared.events import DomainEvent


@dataclass(frozen=True)
class PostCreated(DomainEvent):
    """帖子创建事件。"""

    post_id: int
    author_id: int


@dataclass(frozen=True)
class PostUpdated(DomainEvent):
    """帖子更新事件。"""

    post_id: int
    author_id: int


@dataclass(frozen=True)
class PostDeleted(DomainEvent):
    """帖子删除事件。"""

    post_id: int
    author_id: int


@dataclass(frozen=True)
class RepostCreated(DomainEvent):
    """转发创建事件。"""

    root_post_id: int
    repost_id: int
    sender_id: int
    source_post_id: int | None = None
    source_comment_id: int | None = None
    source_content: str | None = None
