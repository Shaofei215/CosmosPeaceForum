"""
Management Backend - 终端日志显示缓冲服务。

持久化由 ``agents.logging_config`` 的独立 JSONL handler 负责；本服务只维护
管理前端需要的进程内最近日志，因此“清空”不会再改写任何日志文件。
"""

import logging
import threading
from collections import deque
from datetime import datetime
from typing import List, Optional

from agents.logging_config import restore_agents_loggers

class TerminalLogHandler(logging.Handler):
    """自定义日志处理器，将日志写入捕获缓冲区"""

    def __init__(self, capture: "TerminalLogCapture"):
        super().__init__()
        self._capture = capture

    def emit(self, record: logging.LogRecord) -> None:
        if getattr(record, "_terminal_log_capture_emitted", False):
            return
        setattr(record, "_terminal_log_capture_emitted", True)
        level = (
            record.levelname
            if record.levelname in {"DEBUG", "INFO", "WARNING", "ERROR"}
            else "INFO"
        )
        self._capture.append(self.format(record), level=level)


class TerminalLogCapture:
    """终端日志捕获器"""

    def __init__(self, max_lines: int = 5000):
        self._logs: deque = deque(maxlen=max_lines)
        self._max_lines = max_lines
        self._lock = threading.Lock()
        self._handler: Optional[TerminalLogHandler] = None

    def _target_loggers(self) -> list[logging.Logger]:
        return [logging.getLogger()]

    def start(self):
        restore_agents_loggers()
        if self._handler is None:
            self._handler = TerminalLogHandler(self)
            self._handler.setFormatter(
                logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
            )
        for logger in self._target_loggers():
            if self._handler not in logger.handlers:
                logger.addHandler(self._handler)

    def stop(self):
        if self._handler is None:
            return
        for logger in self._target_loggers():
            if self._handler in logger.handlers:
                logger.removeHandler(self._handler)
        self._handler = None

    def append(self, message: str, level: str = "INFO") -> None:
        if not message or not message.strip():
            return
        log = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "level": level,
            "message": message.strip(),
        }
        with self._lock:
            self._logs.append(log)

    def _append(self, message: str, is_error: bool = False, level: Optional[str] = None):
        self.append(message, level or ("ERROR" if is_error else "INFO"))

    def _all_logs(self) -> List[dict]:
        with self._lock:
            return list(self._logs)

    def _filter_logs(
        self,
        logs: List[dict],
        level: Optional[str] = None,
        keyword: Optional[str] = None,
        role: Optional[str] = None,
    ) -> List[dict]:
        if level:
            logs = [log for log in logs if log["level"] == level]
        if keyword:
            normalized = keyword.lower()
            logs = [log for log in logs if normalized in log["message"].lower()]
        if role:
            marker = f"[{role}]"
            logs = [log for log in logs if marker in log["message"]]
        return logs

    def get_logs(
        self,
        skip: int = 0,
        limit: int = 100,
        level: Optional[str] = None,
        keyword: Optional[str] = None,
        role: Optional[str] = None,
    ) -> tuple[List[dict], int]:
        all_logs = self._filter_logs(self._all_logs(), level=level, keyword=keyword, role=role)
        return all_logs[skip : skip + limit], len(all_logs)

    def recent(
        self,
        count: int = 200,
        level: Optional[str] = None,
        keyword: Optional[str] = None,
        role: Optional[str] = None,
    ) -> tuple[List[dict], int]:
        logs = self._filter_logs(self._all_logs(), level=level, keyword=keyword, role=role)
        items = logs[-count:] if count else logs
        return items, len(logs)

    def get_recent_logs(
        self,
        count: int = 50,
        level: Optional[str] = None,
        keyword: Optional[str] = None,
        role: Optional[str] = None,
    ) -> List[dict]:
        logs, _ = self.recent(count=count, level=level, keyword=keyword, role=role)
        return logs

    def clear(self):
        with self._lock:
            self._logs.clear()


terminal_log_capture = TerminalLogCapture()
