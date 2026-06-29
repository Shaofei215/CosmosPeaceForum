"""互动反应领域事件。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from social_platform.app.shared.events import DomainEvent


ReactionTargetType = Literal["post", "comment"]


@dataclass(frozen=True)
class LikeChanged(DomainEvent):
    """点赞状态变化事件。"""

    target_type: ReactionTargetType
    target_id: int
    actor_id: int
    owner_id: int
    previous_state: bool
    current_state: bool
    post_id: int | None = None
    created_by_agent: bool = False
