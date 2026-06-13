"""关注领域事件。"""

from __future__ import annotations

from dataclasses import dataclass

from social_platform.app.shared.events import DomainEvent


@dataclass(frozen=True)
class FollowChanged(DomainEvent):
    """关注关系状态变化事件。"""

    follower_id: int
    following_id: int
    previous_state: bool
    current_state: bool
