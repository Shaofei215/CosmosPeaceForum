"""领域事件订阅启动入口。"""

from __future__ import annotations

_registered = False


def ensure_domain_event_handlers_registered() -> None:
    """注册全局领域事件处理器。

    该函数可被应用启动流程和旧 service shim 重复调用；内部会保证注册过程幂等。
    """

    global _registered
    if _registered:
        return

    from social_platform.app.domains.notification.subscribers import (
        register_notification_subscribers,
    )
    from social_platform.app.domains.search.subscribers import register_search_subscribers

    register_notification_subscribers()
    register_search_subscribers()
    _registered = True
