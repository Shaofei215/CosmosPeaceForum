"""
Tests for Terminal Log Service and API
"""

import logging
import pytest
from datetime import datetime

from agents.management.backend.schemas import (
    TerminalLogResponse,
    TerminalLogListResponse,
)
from agents.management.backend.services.terminal_log_service import TerminalLogCapture


class TestTerminalLogSchemas:
    def test_terminal_log_response(self):
        log = TerminalLogResponse(
            timestamp="2025-01-01 12:00:00",
            level="INFO",
            message="Test log message",
        )
        assert log.timestamp == "2025-01-01 12:00:00"
        assert log.level == "INFO"
        assert log.message == "Test log message"

    def test_terminal_log_list_response(self):
        items = [
            TerminalLogResponse(
                timestamp="2025-01-01 12:00:00",
                level="INFO",
                message="Log 1",
            ),
            TerminalLogResponse(
                timestamp="2025-01-01 12:00:01",
                level="ERROR",
                message="Log 2",
            ),
        ]
        resp = TerminalLogListResponse(items=items, total=2)
        assert resp.total == 2
        assert len(resp.items) == 2
        assert resp.items[0].level == "INFO"
        assert resp.items[1].level == "ERROR"


class TestTerminalLogCapture:
    @pytest.fixture(autouse=True)
    def setup(self):
        root = logging.getLogger()
        initial_handlers = root.handlers[:]
        yield
        root.handlers = initial_handlers

    @pytest.fixture
    def capture(self):
        return TerminalLogCapture(max_lines=100)

    def test_append_and_get_logs(self, capture):
        capture._append("Hello world")
        logs, total = capture.get_logs()
        assert total == 1
        assert logs[0]["message"] == "Hello world"
        assert logs[0]["level"] == "INFO"

    def test_append_error_level(self, capture):
        capture._append("Error occurred", is_error=True)
        logs, total = capture.get_logs()
        assert total == 1
        assert logs[0]["level"] == "ERROR"

    def test_append_empty_message(self, capture):
        capture._append("")
        capture._append("   ")
        logs, total = capture.get_logs()
        assert total == 0

    def test_get_recent_logs(self, capture):
        for i in range(10):
            capture._append(f"Log {i}")
        recent = capture.get_recent_logs(count=3)
        assert len(recent) == 3
        assert recent[0]["message"] == "Log 7"
        assert recent[1]["message"] == "Log 8"
        assert recent[2]["message"] == "Log 9"

    def test_get_recent_logs_exceeds_total(self, capture):
        capture._append("Only one")
        recent = capture.get_recent_logs(count=10)
        assert len(recent) == 1

    def test_get_logs_with_level_filter(self, capture):
        capture._append("Info message")
        capture._append("Error message", is_error=True)
        capture._append("Another info")

        logs, total = capture.get_logs(level="ERROR")
        assert total == 1
        assert logs[0]["message"] == "Error message"

        logs, total = capture.get_logs(level="INFO")
        assert total == 2

    def test_get_logs_with_keyword_filter(self, capture):
        capture._append("User login successful")
        capture._append("Agent started")
        capture._append("User logout")

        logs, total = capture.get_logs(keyword="user")
        assert total == 2
        assert all("User" in log["message"] for log in logs)

    def test_get_logs_with_pagination(self, capture):
        for i in range(20):
            capture._append(f"Log {i}")

        logs, total = capture.get_logs(skip=0, limit=5)
        assert total == 20
        assert len(logs) == 5
        assert logs[0]["message"] == "Log 0"

        logs, total = capture.get_logs(skip=15, limit=10)
        assert len(logs) == 5
        assert logs[0]["message"] == "Log 15"

    def test_file_backed_logs_are_shared_between_instances(self, tmp_path):
        log_file = tmp_path / "terminal_logs.jsonl"
        writer = TerminalLogCapture(max_lines=100, log_file_path=log_file)
        reader = TerminalLogCapture(max_lines=100, log_file_path=log_file)

        writer._append("Shared scheduler log", level="ERROR")

        logs, total = reader.recent(count=10)
        assert total == 1
        assert logs[0]["level"] == "ERROR"
        assert logs[0]["message"] == "Shared scheduler log"

        reader.clear()
        logs, total = writer.recent(count=10)
        assert logs == []
        assert total == 0

    def test_clear_logs(self, capture):
        capture._append("Log 1")
        capture._append("Log 2")
        capture.clear()
        logs, total = capture.get_logs()
        assert total == 0

    def test_max_lines_limit(self, capture):
        small_capture = TerminalLogCapture(max_lines=5)
        for i in range(10):
            small_capture._append(f"Log {i}")
        logs, total = small_capture.get_logs()
        assert total == 5
        assert logs[0]["message"] == "Log 5"

    def test_log_timestamp_format(self, capture):
        capture._append("Test")
        logs, _ = capture.get_logs()
        timestamp = logs[0]["timestamp"]
        parsed = datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S")
        assert parsed is not None

    def test_start_adds_handler(self, capture):
        root = logging.getLogger()
        count_before = len(root.handlers)
        capture.start()
        assert len(root.handlers) == count_before + 1
        capture.stop()

    def test_agents_logger_is_captured_when_root_handler_is_missing(self, capture):
        root = logging.getLogger()
        old_level = root.level
        root.setLevel(logging.INFO)

        capture.start()
        root.removeHandler(capture._handler)

        test_logger = logging.getLogger("agents.agents_scheduler.scheduler.internal_server")
        test_logger.info("scheduler internal log")

        logs, total = capture.get_logs()
        assert total == 1
        assert "scheduler internal log" in logs[0]["message"]

        capture.stop()
        root.setLevel(old_level)

    def test_stop_removes_handler(self, capture):
        root = logging.getLogger()
        count_before = len(root.handlers)
        capture.start()
        capture.stop()
        assert len(root.handlers) == count_before

    def test_start_idempotent(self, capture):
        root = logging.getLogger()
        count_before = len(root.handlers)
        capture.start()
        capture.start()
        assert len(root.handlers) == count_before + 1
        capture.stop()

    def test_stop_idempotent(self, capture):
        capture.stop()
        capture.stop()

    def test_logging_is_captured(self, capture):
        root = logging.getLogger()
        old_handlers = root.handlers[:]
        root.handlers = []

        capture.start()
        test_logger = logging.getLogger("test.module")
        test_logger.setLevel(logging.DEBUG)
        test_logger.info("test info log")
        test_logger.error("test error log")

        logs, total = capture.get_logs()
        assert total == 2
        assert "test info log" in logs[0]["message"]
        assert "test error log" in logs[1]["message"]

        capture.stop()
        root.handlers = old_handlers
