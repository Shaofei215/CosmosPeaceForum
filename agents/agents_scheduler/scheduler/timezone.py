"""Agent Scheduler 系统时区工具。

Scheduler 的运行期注入和日志时间需要与部署机器系统时区一致。本模块
返回无时区本地时间，便于与现有 SQLite/JSON 数据结构保持兼容。
"""

from datetime import datetime


def local_now() -> datetime:
    """返回系统本地时区的无时区当前时间。

    Returns:
        datetime: 按运行环境系统时区计算，并去掉 tzinfo 的当前时间。
    """
    return datetime.now().astimezone().replace(tzinfo=None)
