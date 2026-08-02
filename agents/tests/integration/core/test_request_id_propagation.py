"""Management 到 Scheduler 的请求关联传播测试。"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from agents.logging_config import logging_context
from agents.management.backend.services import registrar


def test_management_propagates_request_id_to_scheduler() -> None:
    """Management 热更新请求应把当前请求 ID 传递给 Scheduler。"""

    response = MagicMock(status_code=200)
    with (
        logging_context(request_id="management-request-1"),
        patch.object(
            registrar,
            "get_config",
            return_value=SimpleNamespace(scheduler_internal_base_url="http://scheduler:8002"),
        ),
        patch.object(registrar.requests, "post", return_value=response) as post,
    ):
        assert registrar.notify_scheduler_reload("agent", 7) is True

    assert post.call_args.kwargs["headers"]["X-Request-ID"] == "management-request-1"


def test_management_routes_relation_reload_to_dedicated_endpoint() -> None:
    """关系热更新应调用专用内部端点并继续传播请求 ID。"""
    response = MagicMock(status_code=200)
    with (
        logging_context(request_id="relation-request-1"),
        patch.object(
            registrar,
            "get_config",
            return_value=SimpleNamespace(scheduler_internal_base_url="http://scheduler:8002"),
        ),
        patch.object(registrar.requests, "post", return_value=response) as post,
    ):
        assert registrar.notify_scheduler_reload("relations") is True

    assert post.call_args.args[0] == "http://scheduler:8002/internal/reload/relations"
    assert post.call_args.kwargs["data"] is None
    assert post.call_args.kwargs["headers"]["X-Request-ID"] == "relation-request-1"
