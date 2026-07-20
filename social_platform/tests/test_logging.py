"""公开平台统一日志格式、留存与访问关联测试。"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

from social_platform.app.core.logging import (
    AccessLogMiddleware,
    HybridRotatingFileHandler,
    JsonLogFormatter,
    get_log_context,
)


def _record(message: str = "公开平台日志") -> logging.LogRecord:
    return logging.LogRecord("social_platform.app.test", logging.INFO, __file__, 1, message, (), None)


def test_json_formatter_contract_and_exception() -> None:
    try:
        raise ValueError("测试异常")
    except ValueError:
        record = logging.getLogger("social_platform.app.test").makeRecord(
            "social_platform.app.test",
            logging.ERROR,
            __file__,
            1,
            "请求失败",
            (),
            __import__("sys").exc_info(),
            extra={"request_id": "request-1", "event": "test.error"},
        )

    payload = json.loads(JsonLogFormatter().format(record))
    assert payload["service"] == "social-platform"
    assert payload["request_id"] == "request-1"
    assert payload["exception"]["type"] == "ValueError"
    assert "测试异常" in payload["exception"]["stack"]
    assert datetime.fromisoformat(payload["timestamp"]).tzinfo is not None


def test_daily_rollover_preserves_valid_jsonl(tmp_path: Path) -> None:
    current = [datetime(2026, 7, 20, 23, 59, tzinfo=timezone.utc)]
    handler = HybridRotatingFileHandler(
        tmp_path,
        retention_days=30,
        segment_max_bytes=4096,
        max_total_bytes=8192,
        now_factory=lambda: current[0],
    )
    handler.setFormatter(JsonLogFormatter())
    handler.emit(_record("第一天"))
    current[0] = datetime(2026, 7, 21, 0, 1, tzinfo=timezone.utc)
    handler.emit(_record("第二天"))
    handler.close()

    archives = list(tmp_path.glob("runtime.*.jsonl"))
    assert len(archives) == 1
    assert json.loads(archives[0].read_text(encoding="utf-8"))["message"] == "第一天"
    assert json.loads((tmp_path / "runtime.jsonl").read_text(encoding="utf-8"))["message"] == "第二天"


@pytest.mark.asyncio
async def test_access_log_uses_route_template_and_omits_query_and_authorization() -> None:
    records: list[logging.LogRecord] = []

    class ListHandler(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            records.append(record)

    logger = logging.getLogger("social_platform.access")
    handler = ListHandler()
    old_level = logger.level
    logger.setLevel(logging.INFO)
    logger.addHandler(handler)

    async def app(scope, receive, send):
        scope["route"] = SimpleNamespace(path="/api/v1/posts/{post_id}")
        await send({"type": "http.response.start", "status": 404, "headers": []})
        await send({"type": "http.response.body", "body": b"{}"})

    sent: list[dict] = []

    async def collect(message: dict) -> None:
        sent.append(message)

    middleware = AccessLogMiddleware(app, api_prefixes=("/api/v1",))
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/api/v1/posts/8",
        "query_string": b"token=never-log-this",
        "headers": [
            (b"authorization", b"Bearer secret"),
            (b"user-agent", b"pytest-browser"),
            (b"x-request-id", b"bad request id"),
        ],
        "client": ("198.51.100.4", 5000),
    }
    try:
        await middleware(scope, lambda: None, collect)
    finally:
        logger.removeHandler(handler)
        logger.setLevel(old_level)

    request_id = dict(sent[0]["headers"])[b"x-request-id"].decode("ascii")
    assert request_id != "bad request id"
    assert records[-1].levelno == logging.WARNING
    http = getattr(records[-1], "http")
    assert http["route"] == "/api/v1/posts/{post_id}"
    assert http["client_ip"] == "198.51.100.4"
    assert http["user_agent"] == "pytest-browser"
    assert "token" not in json.dumps(http)
    assert get_log_context() == {}


@pytest.mark.asyncio
async def test_access_log_excludes_static_and_debugs_health() -> None:
    """静态资源不应留存，健康检查则应以 DEBUG 记录。"""

    records: list[logging.LogRecord] = []

    class ListHandler(logging.Handler):
        """把测试期间的日志记录收集到列表。"""

        def emit(self, record: logging.LogRecord) -> None:
            """收集一条日志记录。"""

            records.append(record)

    logger = logging.getLogger("social_platform.access")
    handler = ListHandler()
    old_level = logger.level
    logger.setLevel(logging.DEBUG)
    logger.addHandler(handler)

    async def app(scope, receive, send):
        """返回固定成功响应供中间件测试。"""

        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"ok"})

    async def collect(message: dict) -> None:
        """消费测试响应消息。"""

    middleware = AccessLogMiddleware(app, api_prefixes=("/api/v1",), health_paths=("/health",))
    try:
        await middleware(
            {"type": "http", "method": "GET", "path": "/assets/app.js", "headers": []},
            lambda: None,
            collect,
        )
        await middleware(
            {"type": "http", "method": "GET", "path": "/health", "headers": []},
            lambda: None,
            collect,
        )
    finally:
        logger.removeHandler(handler)
        logger.setLevel(old_level)

    assert len(records) == 1
    assert records[0].levelno == logging.DEBUG


@pytest.mark.asyncio
async def test_access_log_waits_for_stream_completion_and_logs_exception_once() -> None:
    """流式响应完成后只记一次访问日志，未处理异常也只记一次堆栈。"""

    records: list[logging.LogRecord] = []

    class ListHandler(logging.Handler):
        """把测试期间的日志记录收集到列表。"""

        def emit(self, record: logging.LogRecord) -> None:
            """收集一条日志记录。"""

            records.append(record)

    logger = logging.getLogger("social_platform.access")
    handler = ListHandler()
    old_level = logger.level
    logger.setLevel(logging.INFO)
    logger.addHandler(handler)

    async def stream_app(scope, receive, send):
        """模拟包含两个正文分片的 SSE 响应。"""

        scope["route"] = SimpleNamespace(path="/api/v1/events")
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"one", "more_body": True})
        await send({"type": "http.response.body", "body": b"two", "more_body": False})

    async def failing_app(scope, receive, send):
        """模拟路由边界内的未处理异常。"""

        scope["route"] = SimpleNamespace(path="/api/v1/failure")
        raise ValueError("boom")

    async def collect(message: dict) -> None:
        """消费测试响应消息。"""

    scope = {"type": "http", "method": "GET", "path": "/api/v1/events", "headers": []}
    try:
        await AccessLogMiddleware(stream_app, api_prefixes=("/api/v1",))(
            scope,
            lambda: None,
            collect,
        )
        with pytest.raises(ValueError, match="boom"):
            await AccessLogMiddleware(failing_app, api_prefixes=("/api/v1",))(
                {"type": "http", "method": "GET", "path": "/api/v1/failure", "headers": []},
                lambda: None,
                collect,
            )
    finally:
        logger.removeHandler(handler)
        logger.setLevel(old_level)

    assert len(records) == 2
    assert getattr(records[0], "event") == "http.request"
    assert getattr(records[1], "event") == "http.exception"
    assert records[1].levelno == logging.ERROR
    assert records[1].exc_info is not None
