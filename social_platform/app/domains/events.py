"""公开平台领域事件定义。"""

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


@dataclass(frozen=True)
class PostLiked(DomainEvent):
    """帖子点赞事件。"""

    post_id: int
    sender_id: int


@dataclass(frozen=True)
class PostUnliked(DomainEvent):
    """帖子取消点赞事件。"""

    post_id: int
    sender_id: int


@dataclass(frozen=True)
class CommentLiked(DomainEvent):
    """评论点赞事件。"""

    comment_id: int
    sender_id: int


@dataclass(frozen=True)
class CommentUnliked(DomainEvent):
    """评论取消点赞事件。"""

    comment_id: int
    sender_id: int


@dataclass(frozen=True)
class UserFollowed(DomainEvent):
    """用户关注事件。"""

    follower_id: int
    following_id: int


@dataclass(frozen=True)
class UserUnfollowed(DomainEvent):
    """用户取消关注事件。"""

    follower_id: int
    following_id: int


@dataclass(frozen=True)
class UserUpdated(DomainEvent):
    """用户资料更新事件。"""

    user_id: int


@dataclass(frozen=True)
class UserDeleted(DomainEvent):
    """用户删除事件。"""

    user_id: int
    post_ids: tuple[int, ...] = ()
