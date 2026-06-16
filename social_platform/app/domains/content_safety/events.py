"""内容安全领域事件定义。"""

from dataclasses import dataclass

from social_platform.app.shared.events import DomainEvent


@dataclass(frozen=True)
class ContentModerationActionApplied(DomainEvent):
    """内容作者的内容已被管理端或自动审核处理。"""

    recipient_id: int
    resource_type: str
    resource_id: int
    reason: str | None = None


@dataclass(frozen=True)
class ReportedContentViolationConfirmed(DomainEvent):
    """用户举报的内容已被确认违规并处理。"""

    reporter_ids: tuple[int, ...]
    resource_type: str
    resource_id: int
