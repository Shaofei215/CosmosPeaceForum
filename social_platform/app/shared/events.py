"""轻量领域事件总线。

本模块提供进程内同步事件总线，用于把领域写操作与通知、搜索投影等副作用解耦。
事件处理分为两个阶段：

- ``before_commit``：使用当前数据库会话执行，适合同事务内写入通知等强一致副作用。
- ``after_commit``：事务提交后执行，适合搜索索引、长连接推送等可重建投影。
"""

from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass
from typing import Callable, ClassVar, Generic, Literal, TypeVar

from sqlalchemy import event as sqlalchemy_event
from sqlalchemy.orm import Session


logger = logging.getLogger(__name__)

EventPhase = Literal["before_commit", "after_commit"]
_PENDING_DOMAIN_EVENTS_KEY = "pending_domain_events"


@dataclass(frozen=True)
class DomainEvent:
    """领域事件基类。

    子类应只携带可序列化或轻量可复制的数据，例如资源 ID、操作者 ID 和必要快照，
    避免把带有懒加载关系的 ORM 对象传入提交后处理器。
    """


EventT = TypeVar("EventT", bound=DomainEvent)
DomainEventHandler = Callable[[Session, EventT], None]


@dataclass(frozen=True)
class _HandlerRegistration(Generic[EventT]):
    """事件处理器注册信息。"""

    phase: EventPhase
    handler: DomainEventHandler[EventT]


class EventBus:
    """进程内同步领域事件总线。

    Args:
        name: 总线名称，用于日志定位。

    Raises:
        ValueError: 当订阅阶段不是 ``before_commit`` 或 ``after_commit`` 时抛出。
    """

    _valid_phases: ClassVar[set[EventPhase]] = {"before_commit", "after_commit"}

    def __init__(self, name: str = "domain") -> None:
        self.name = name
        self._handlers: defaultdict[type[DomainEvent], list[_HandlerRegistration]] = defaultdict(list)

    def subscribe(
        self,
        event_type: type[EventT],
        handler: DomainEventHandler[EventT],
        *,
        phase: EventPhase = "before_commit",
    ) -> None:
        """订阅指定类型的领域事件。

        Args:
            event_type: 事件类型。
            handler: 处理器函数，接收当前会话和事件对象。
            phase: 处理阶段，默认为事务提交前。

        Raises:
            ValueError: 当 phase 非法时抛出。
        """

        if phase not in self._valid_phases:
            raise ValueError(f"不支持的事件处理阶段: {phase}")

        registrations = self._handlers[event_type]
        for registration in registrations:
            if registration.phase == phase and registration.handler is handler:
                return
        registrations.append(_HandlerRegistration(phase=phase, handler=handler))

    def publish(self, session: Session, domain_event: DomainEvent) -> None:
        """发布领域事件。

        ``before_commit`` 处理器会立即执行；如果存在 ``after_commit`` 处理器，事件会
        暂存到 ``session.info``，待 SQLAlchemy ``after_commit`` 钩子触发。

        Args:
            session: 当前数据库会话。
            domain_event: 待发布事件。
        """

        registrations = list(self._handlers.get(type(domain_event), []))
        for registration in registrations:
            if registration.phase == "before_commit":
                registration.handler(session, domain_event)

        if any(registration.phase == "after_commit" for registration in registrations):
            pending = session.info.setdefault(_PENDING_DOMAIN_EVENTS_KEY, [])
            pending.append(domain_event)

    def dispatch_after_commit(self, session: Session) -> None:
        """执行当前会话提交后的待处理事件。

        Args:
            session: 已完成提交的数据库会话。
        """

        pending_events = session.info.pop(_PENDING_DOMAIN_EVENTS_KEY, [])
        for domain_event in pending_events:
            registrations = list(self._handlers.get(type(domain_event), []))
            for registration in registrations:
                if registration.phase != "after_commit":
                    continue
                try:
                    registration.handler(session, domain_event)
                except Exception:
                    logger.exception(
                        "领域事件提交后处理失败: bus=%s event=%s handler=%s",
                        self.name,
                        type(domain_event).__name__,
                        getattr(registration.handler, "__name__", repr(registration.handler)),
                    )

    def clear_pending(self, session: Session) -> None:
        """清理当前会话尚未提交的事件。

        Args:
            session: 当前数据库会话。
        """

        session.info.pop(_PENDING_DOMAIN_EVENTS_KEY, None)

    def clear_handlers(self) -> None:
        """清空所有处理器注册。

        该方法主要供事件总线单元测试使用，业务代码不应调用。
        """

        self._handlers.clear()


domain_event_bus = EventBus()


def publish_domain_event(session: Session, domain_event: DomainEvent) -> None:
    """通过全局领域事件总线发布事件。

    Args:
        session: 当前数据库会话。
        domain_event: 待发布事件。
    """

    from social_platform.app.domains.bootstrap import ensure_domain_event_handlers_registered

    ensure_domain_event_handlers_registered()
    domain_event_bus.publish(session, domain_event)


def subscribe_domain_event(
    event_type: type[EventT],
    handler: DomainEventHandler[EventT],
    *,
    phase: EventPhase = "before_commit",
) -> None:
    """向全局领域事件总线注册处理器。

    Args:
        event_type: 事件类型。
        handler: 处理器函数。
        phase: 处理阶段。
    """

    domain_event_bus.subscribe(event_type, handler, phase=phase)


@sqlalchemy_event.listens_for(Session, "after_commit")
def _dispatch_after_commit_events(session: Session) -> None:
    """SQLAlchemy 提交后钩子，分发全局领域事件。"""

    domain_event_bus.dispatch_after_commit(session)


@sqlalchemy_event.listens_for(Session, "after_rollback")
def _clear_pending_events(session: Session) -> None:
    """SQLAlchemy 回滚后钩子，丢弃未提交事件。"""

    domain_event_bus.clear_pending(session)
