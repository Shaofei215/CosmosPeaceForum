"""项目级 pytest 收集规则。

测试通过 ``tests/unit`` 与 ``tests/integration`` 的目录位置自动获得同名 marker，
让目录结构成为唯一分类来源，避免文件移动后忘记同步装饰器。
"""

from __future__ import annotations

from pathlib import Path

import pytest


_TEST_LEVEL_MARKERS = frozenset({"unit", "integration"})


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """根据测试文件目录自动添加测试层级 marker。

    Args:
        config: 当前 pytest 配置，提供仓库根目录。
        items: 本次已经收集的测试项。
    """

    root_path = Path(config.rootpath)
    for item in items:
        try:
            relative_parts = Path(item.path).relative_to(root_path).parts
        except ValueError:
            continue

        for marker_name in _TEST_LEVEL_MARKERS:
            if marker_name in relative_parts:
                item.add_marker(getattr(pytest.mark, marker_name))
                break

