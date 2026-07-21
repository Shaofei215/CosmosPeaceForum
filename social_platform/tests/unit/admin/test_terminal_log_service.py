"""公开平台管理端终端日志人工展示过滤测试。"""

from __future__ import annotations

import logging

from social_platform.app.admin.services.terminal_log_service import TerminalLogCapture


def test_terminal_buffer_filters_successful_access_logs() -> None:
    """前端终端隐藏 2xx 访问日志，同时保留业务日志和 5xx 请求。"""

    capture = TerminalLogCapture(max_lines=20)
    capture.start()
    try:
        assert capture._handler is not None
        business = logging.LogRecord(
            "social_platform.business",
            logging.INFO,
            __file__,
            1,
            "业务日志",
            (),
            None,
        )
        success = logging.LogRecord(
            "social_platform.access",
            logging.INFO,
            __file__,
            1,
            "HTTP 200",
            (),
            None,
        )
        success.event = "http.request"
        success.http = {"status_code": 200}
        failure = logging.LogRecord(
            "social_platform.access",
            logging.ERROR,
            __file__,
            1,
            "HTTP 500",
            (),
            None,
        )
        failure.event = "http.request"
        failure.http = {"status_code": 500}

        capture._handler.handle(business)
        capture._handler.handle(success)
        capture._handler.handle(failure)

        logs, total = capture.recent(count=20)
        assert total == 2
        assert [item["message"].split(": ")[-1] for item in logs] == ["业务日志", "HTTP 500"]
    finally:
        capture.stop()
