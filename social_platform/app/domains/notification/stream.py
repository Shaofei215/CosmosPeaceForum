import threading
from collections import defaultdict


_conditions: dict[int, threading.Condition] = defaultdict(threading.Condition)
_versions: dict[int, int] = defaultdict(int)


def publish_notification_update(user_id: int) -> None:
    """发布指定用户的通知版本变化，唤醒等待中的 SSE 连接。"""
    if not user_id:
        return

    condition = _conditions[user_id]
    with condition:
        _versions[user_id] += 1
        condition.notify_all()


def get_notification_version(user_id: int) -> int:
    """读取用户通知版本号，供客户端判断是否需要刷新。"""
    return _versions[user_id]


def wait_for_notification_update(
    user_id: int,
    last_version: int,
    timeout: float = 25.0,
) -> int:
    """等待用户通知版本变化或超时，支撑轻量 SSE 轮询。"""
    condition = _conditions[user_id]
    with condition:
        condition.wait_for(lambda: _versions[user_id] > last_version, timeout=timeout)
        return _versions[user_id]
