"""硬币领域事件。"""

from __future__ import annotations

from dataclasses import dataclass

from social_platform.app.shared.events import DomainEvent


@dataclass(frozen=True)
class PostCoinGiven(DomainEvent):
    """用户成功向帖子投出一枚硬币。"""

    post_id: int
    sender_id: int
    recipient_id: int
    created_by_agent: bool = False
