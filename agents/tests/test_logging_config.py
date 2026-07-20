"""Agent 统一日志格式、轮转和请求关联测试。"""

from __future__ import annotations

import json
import logging
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

from agents.logging_config import (
    AccessLogMiddleware,
    ContextFilter,
    HybridRotatingFileHandler,
    JsonLogFormatter,
    configure_logging,
    get_log_context,
    logging_context,
    normalize_request_id,
)


def _record(message: str = "你好，宇宙") -> logging.LogRecord:
    return logging.LogRecord("agents.test", logging.INFO, __file__, 1, message, (), None)


def test_json_formatter_keeps_unicode_timezone_and_context() -> None:
    record = _record()
    record.request_id = "request-1"
    record.session_id = "session-1"
    record.agent_id = 7
    record.event = "agent.session.test"

    payload = json.loads(JsonLogFormatter().format(record))

    assert payload["message"] == "你好，宇宙"
    assert payload["service"] == "agents"
    assert payload["request_id"] == "request-1"
    assert payload["session_id"] == "session-1"
    assert payload["agent_id"] == 7
    assert datetime.fromisoformat(payload["timestamp"]).tzinfo is not None


def test_logging_context_is_nested_and_restored() -> None:
    assert get_log_context() == {}
    with logging_context(request_id="outer", agent_id=1):
        assert get_log_context() == {"request_id": "outer", "agent_id": 1}
        with logging_context(request_id="inner", session_id="s1"):
            assert get_log_context()["request_id"] == "inner"
            assert get_log_context()["agent_id"] == 1
        assert get_log_context() == {"request_id": "outer", "agent_id": 1}
    assert get_log_context() == {}


def test_hybrid_handler_rotates_by_size(tmp_path: Path) -> None:
    now = datetime(2026, 7, 20, 12, tzinfo=timezone.utc)
    handler = HybridRotatingFileHandler(
        tmp_path,
        retention_days=30,
        segment_max_bytes=260,
        max_total_bytes=4096,
        now_factory=lambda: now,
    )
    handler.setFormatter(JsonLogFormatter())
    try:
        handler.emit(_record("a" * 120))
        handler.emit(_record("b" * 120))
    finally:
        handler.close()

    assert (tmp_path / "runtime.jsonl").exists()
    assert len(list(tmp_path.glob("runtime.*.jsonl"))) >= 1
    for path in tmp_path.glob("*.jsonl"):
        for line in path.read_text(encoding="utf-8").splitlines():
            json.loads(line)


def test_hybrid_handler_cleans_expired_and_over_capacity_archives(tmp_path: Path) -> None:
    now = datetime.now(timezone.utc)
    expired = tmp_path / "runtime.20260101-000000.jsonl"
    oldest = tmp_path / "runtime.20260718-000000.jsonl"
    newest = tmp_path / "runtime.20260719-000000.jsonl"
    for path in (expired, oldest, newest):
        path.write_bytes(b"x" * 100)
    expired_time = (now - timedelta(days=31)).timestamp()
    oldest_time = (now - timedelta(days=2)).timestamp()
    newest_time = (now - timedelta(days=1)).timestamp()
    os.utime(expired, (expired_time, expired_time))
    os.utime(oldest, (oldest_time, oldest_time))
    os.utime(newest, (newest_time, newest_time))

    handler = HybridRotatingFileHandler(
        tmp_path,
        retention_days=30,
        segment_max_bytes=1024,
        max_total_bytes=100,
        now_factory=lambda: now,
    )
    handler.close()

    assert not expired.exists()
    assert not oldest.exists()
    assert newest.exists()


def test_hybrid_handler_storage_failure_is_rate_limited(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """不可写目标只应限频报告 stderr，且不能让业务日志调用失败。"""

    invalid_log_dir = tmp_path / "not-a-directory"
    invalid_log_dir.write_text("occupied", encoding="utf-8")
    handler = HybridRotatingFileHandler(
        invalid_log_dir,
        retention_days=30,
        segment_max_bytes=1024,
        max_total_bytes=2048,
    )
    try:
        handler.emit(_record("第一次写入"))
        handler.emit(_record("第二次写入"))
    finally:
        handler.close()

    assert capsys.readouterr().err.count("日志持久化失败") == 1


def test_hybrid_handler_concurrent_logging_keeps_complete_json_lines(tmp_path: Path) -> None:
    """多个业务线程经标准 logger 写入时不应产生重复或破损的 JSONL。"""

    handler = HybridRotatingFileHandler(
        tmp_path,
        retention_days=30,
        segment_max_bytes=1024 * 1024,
        max_total_bytes=2 * 1024 * 1024,
    )
    handler.setFormatter(JsonLogFormatter())
    handler.addFilter(ContextFilter())
    logger = logging.getLogger("agents.test.concurrent")
    old_handlers = list(logger.handlers)
    old_level = logger.level
    old_propagate = logger.propagate
    logger.handlers = [handler]
    logger.setLevel(logging.INFO)
    logger.propagate = False

    def write_record(index: int) -> None:
        """在独立线程上下文中写入一条可校验关联字段的日志。"""

        with logging_context(
            request_id=f"request-{index}",
            session_id=f"session-{index}",
            agent_id=index,
        ):
            logger.info("并发日志 %d", index)

    try:
        with ThreadPoolExecutor(max_workers=8) as executor:
            list(executor.map(write_record, range(200)))
    finally:
        handler.close()
        logger.handlers = old_handlers
        logger.setLevel(old_level)
        logger.propagate = old_propagate

    payloads = [
        json.loads(line)
        for line in (tmp_path / "runtime.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert len(payloads) == 200
    assert {payload["message"] for payload in payloads} == {
        f"并发日志 {index}" for index in range(200)
    }
    for payload in payloads:
        index = int(payload["message"].removeprefix("并发日志 "))
        assert payload["request_id"] == f"request-{index}"
        assert payload["session_id"] == f"session-{index}"
        assert payload["agent_id"] == index


def test_configure_logging_is_idempotent(tmp_path: Path) -> None:
    """同一配置重复初始化时应复用根处理器，避免每条日志重复输出。"""

    root = logging.getLogger()
    previous_level = root.level
    previous_config = getattr(root, "_cpf_logging_config", None)
    previous_service = getattr(root, "_cpf_logging_service", None)
    configure_logging(
        level="INFO",
        log_dir=tmp_path,
        retention_days=30,
        segment_max_mb=50,
        max_total_mb=512,
    )
    first_handlers = [handler for handler in root.handlers if getattr(handler, "_cpf_managed", False)]
    configure_logging(
        level="INFO",
        log_dir=tmp_path,
        retention_days=30,
        segment_max_mb=50,
        max_total_mb=512,
    )
    second_handlers = [handler for handler in root.handlers if getattr(handler, "_cpf_managed", False)]
    try:
        assert len(first_handlers) == 2
        assert second_handlers == first_handlers
    finally:
        for handler in second_handlers:
            root.removeHandler(handler)
            handler.close()
        root.setLevel(previous_level)
        if previous_config is None:
            root.__dict__.pop("_cpf_logging_config", None)
        else:
            root._cpf_logging_config = previous_config  # type: ignore[attr-defined]
        if previous_service is None:
            root.__dict__.pop("_cpf_logging_service", None)
        else:
            root._cpf_logging_service = previous_service  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_access_middleware_returns_request_id_and_logs_safe_http_fields() -> None:
    records: list[logging.LogRecord] = []

    class ListHandler(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            records.append(record)

    logger = logging.getLogger("agents.access")
    handler = ListHandler()
    old_level = logger.level
    logger.setLevel(logging.INFO)
    logger.addHandler(handler)

    async def app(scope, receive, send):
        scope["route"] = SimpleNamespace(path="/api/agents/{agent_id}")
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"{}"})

    middleware = AccessLogMiddleware(app, api_prefixes=("/api",))
    sent: list[dict] = []

    async def collect(message: dict) -> None:
        sent.append(message)

    scope = {
        "type": "http",
        "method": "GET",
        "path": "/api/agents/1",
        "headers": [(b"x-request-id", b"req-1"), (b"user-agent", b"pytest-agent")],
        "client": ("203.0.113.10", 1234),
    }
    try:
        await middleware(scope, lambda: None, collect)
    finally:
        logger.removeHandler(handler)
        logger.setLevel(old_level)

    response_headers = dict(sent[0]["headers"])
    assert response_headers[b"x-request-id"] == b"req-1"
    assert getattr(records[-1], "request_id") == "req-1"
    http = getattr(records[-1], "http")
    assert http == {
        "method": "GET",
        "route": "/api/agents/{agent_id}",
        "status_code": 200,
        "duration_ms": http["duration_ms"],
        "client_ip": "203.0.113.10",
        "user_agent": "pytest-agent",
    }
    assert "authorization" not in http
    assert get_log_context() == {}


def test_invalid_request_id_is_replaced() -> None:
    assert normalize_request_id("valid:id-1") == "valid:id-1"
    assert normalize_request_id("bad request id") != "bad request id"
