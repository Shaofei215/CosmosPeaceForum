"""
Management Backend - 终端日志捕获服务
通过自定义 logging.Handler 捕获所有日志输出
"""

import logging
import threading
from collections import deque
from datetime import datetime
from typing import List, Optional


class TerminalLogHandler(logging.Handler):
    """自定义日志处理器，将日志写入捕获缓冲区"""

    def __init__(self, capture):
        super().__init__()
        self._capture = capture

    def emit(self, record):
        self._capture._append(self.format(record), record.levelno >= logging.ERROR)


class TerminalLogCapture:
    """终端日志捕获器"""

    def __init__(self, max_lines: int = 5000):
        self._logs: deque = deque(maxlen=max_lines)
        self._lock = threading.Lock()
        self._handler: Optional[TerminalLogHandler] = None

    def start(self):
        if self._handler is not None:
            return
        self._handler = TerminalLogHandler(self)
        self._handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s"))
        logging.getLogger().addHandler(self._handler)

    def stop(self):
        if self._handler is None:
            return
        logging.getLogger().removeHandler(self._handler)
        self._handler = None

    def _append(self, message: str, is_error: bool = False):
        if not message or not message.strip():
            return
        with self._lock:
            self._logs.append({
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "level": "ERROR" if is_error else "INFO",
                "message": message.strip(),
            })

    def get_logs(
        self,
        skip: int = 0,
        limit: int = 100,
        level: Optional[str] = None,
        keyword: Optional[str] = None,
    ) -> tuple[List[dict], int]:
        with self._lock:
            all_logs = list(self._logs)
        if level:
            all_logs = [log for log in all_logs if log["level"] == level]
        if keyword:
            all_logs = [log for log in all_logs if keyword.lower() in log["message"].lower()]
        return all_logs[skip : skip + limit], len(all_logs)

    def get_recent_logs(self, count: int = 50) -> List[dict]:
        with self._lock:
            return list(self._logs)[-count:]

    def clear(self):
        with self._lock:
            self._logs.clear()


terminal_log_capture = TerminalLogCapture()
