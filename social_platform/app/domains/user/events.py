"""用户领域事件。"""

from __future__ import annotations

from dataclasses import dataclass

from social_platform.app.shared.events import DomainEvent


@dataclass(frozen=True)
class UserUpdated(DomainEvent):
    """用户资料更新事件。"""

    user_id: int


@dataclass(frozen=True)
class UserDeleted(DomainEvent):
    """用户删除事件。"""

    user_id: int
    post_ids: tuple[int, ...] = ()
