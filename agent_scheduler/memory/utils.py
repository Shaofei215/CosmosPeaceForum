# 记忆系统工具函数模块
# 提供时间描述计算等辅助功能

from agent_scheduler.time_system import get_time_system


def calculate_time_description(timestamp: float, current_time: float = None) -> str:
    """
    根据时间戳计算人类可读的时间描述

    使用 time_system 获取缩放时间，保证时间一致性。

    Args:
        timestamp: 记忆时间戳
        current_time: 当前时间戳（可选，默认使用 time_system 获取）

    Returns:
        str: 时间描述，如"3天前"、"刚刚"等

    Example:
        >>> ts = get_time_system()
        >>> current_time = ts.get_scaled_timestamp()
        >>> calculate_time_description(past_timestamp, current_time)
        '3天前'
    """
    if current_time is None:
        ts = get_time_system()
        current_time = ts.get_scaled_timestamp()

    delta_seconds = current_time - timestamp

    if delta_seconds < 0:
        return "未来"
    elif delta_seconds < 60:
        return "刚刚"
    elif delta_seconds < 3600:
        minutes = int(delta_seconds / 60)
        return f"{minutes}分钟前"
    elif delta_seconds < 86400:
        hours = int(delta_seconds / 3600)
        return f"{hours}小时前"
    elif delta_seconds < 2592000:  # 30 天
        days = int(delta_seconds / 86400)
        return f"{days}天前"
    elif delta_seconds < 31536000:  # 365 天
        months = int(delta_seconds / 2592000)
        return f"{months}个月前"
    else:
        years = int(delta_seconds / 31536000)
        return f"{years}年前"
