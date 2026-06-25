"""公开平台系统时区工具。

本模块集中提供运行进程所在系统时区的时间函数，供模型默认值、
业务过期判断和会话刷新逻辑复用。数据库当前使用无时区 datetime
字段，因此这里返回去掉 tzinfo 的本地时间，避免前端把 UTC 时间当作
本地时间显示成八小时前。
"""

from datetime import datetime


def local_now() -> datetime:
    """返回系统本地时区的无时区当前时间。

    Returns:
        datetime: 按运行环境系统时区计算，并去掉 tzinfo 的当前时间。
    """
    return datetime.now().astimezone().replace(tzinfo=None)
