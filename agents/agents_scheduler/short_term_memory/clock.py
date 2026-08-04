"""短期记忆使用的 Scheduler 时间描述。

本模块独立实现短期记忆的时间投影和相对时间文案，避免把当前快照耦合进长期
记忆工具模块。
"""

import time
from collections.abc import Mapping
from typing import Any


def project_scheduler_timestamp(
    state: Mapping[str, Any] | None,
    *,
    real_timestamp: float | None = None,
    fallback_timestamp: float = 0.0,
) -> float:
    """根据持久化 Scheduler 锚点投影当前缩放时间戳。

    Args:
        state: ``scheduler_time_state`` 的锚点字段。
        real_timestamp: 当前现实 Unix 时间戳，测试时可显式传入。
        fallback_timestamp: 没有可用锚点时沿用的缩放时间基线。

    Returns:
        float: 当前 Scheduler 缩放时间戳。
    """

    if not state:
        return max(0.0, float(fallback_timestamp))

    try:
        scaled_timestamp = float(state["scaled_timestamp"])
        saved_real_timestamp = float(state["real_timestamp"])
        scale = float(state["scale"])
        paused = bool(state.get("paused", False))
    except (KeyError, TypeError, ValueError):
        return max(0.0, float(fallback_timestamp))

    if paused:
        return scaled_timestamp

    now = time.time() if real_timestamp is None else real_timestamp
    return scaled_timestamp + max(0.0, now - saved_real_timestamp) * scale


def describe_short_term_memory_age(
    timestamp: float,
    *,
    current_timestamp: float | None = None,
) -> str:
    """把短期记忆更新时间描述为基于缩放时间的自然语言。

    Args:
        timestamp: 保存短期记忆时的 Scheduler 缩放时间戳。
        current_timestamp: 当前缩放时间戳；省略时读取全局 Scheduler 时间。

    Returns:
        str: 例如“刚刚”“3天前”或“2个月前”。
    """

    if current_timestamp is None:
        from agents.agents_scheduler.scheduler.time_system import get_time_system

        current_timestamp = get_time_system().get_scaled_timestamp()

    delta_seconds = current_timestamp - timestamp
    if delta_seconds < 0:
        return "未来"
    if delta_seconds < 60:
        return "刚刚"
    if delta_seconds < 3600:
        return f"{int(delta_seconds / 60)}分钟前"
    if delta_seconds < 86400:
        return f"{int(delta_seconds / 3600)}小时前"
    if delta_seconds < 2592000:
        return f"{int(delta_seconds / 86400)}天前"
    if delta_seconds < 31536000:
        return f"{int(delta_seconds / 2592000)}个月前"
    return f"{int(delta_seconds / 31536000)}年前"
