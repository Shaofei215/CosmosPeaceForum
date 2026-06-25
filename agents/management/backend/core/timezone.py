"""Agent 管理后端系统时区工具。

管理端 SQLite 模型当前使用无时区 datetime 字段。所有写入和过期判断
统一通过本模块读取系统本地时间，保证东八区部署时前端显示不会落后
八小时。
"""

from datetime import datetime


def local_now() -> datetime:
    """返回系统本地时区的无时区当前时间。

    Returns:
        datetime: 按运行环境系统时区计算，并去掉 tzinfo 的当前时间。
    """
    return datetime.now().astimezone().replace(tzinfo=None)
