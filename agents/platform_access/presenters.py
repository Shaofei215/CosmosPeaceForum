"""共享平台访问层的纯数据 presenter。

当前公开 API 同时返回裸对象和分页包装，因此本阶段保留原始结构，只递归复制 JSON
容器以隔离 HTTP 库对象。后续外部网关可在该边界增加独立、版本化的 presenter。
"""

from __future__ import annotations

from typing import Any


def normalize_platform_response(value: Any) -> Any:
    """把 JSON 数据递归转换为普通 Python 容器且不改变响应契约。

    Args:
        value: ``requests`` 解析后的 JSON 值。

    Returns:
        Any: 与输入等价的字典、列表或标量。
    """

    if isinstance(value, dict):
        return {key: normalize_platform_response(item) for key, item in value.items()}
    if isinstance(value, list):
        return [normalize_platform_response(item) for item in value]
    return value
