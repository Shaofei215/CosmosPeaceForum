"""管理端终端日志捕获服务。"""

import logging
import threading
from collections import deque
from datetime import datetime
from typing import Optional


class TerminalLogHandler(logging.Handler):
    """将应用 logging 输出捕获到内存缓冲，供管理端实时查看。"""

    def __init__(self, capture: "TerminalLogCapture"):
        super().__init__()
        self._capture = capture

    def emit(self, record: logging.LogRecord) -> None:
        level = record.levelname if record.levelname in {"DEBUG", "INFO", "WARNING", "ERROR"} else "INFO"
        self._capture.append(self.format(record), level)


class TerminalLogCapture:
    """线程安全的内存日志缓冲。"""

    def __init__(self, max_lines: int = 5000):
        """初始化日志缓冲。

        Args:
            max_lines: 最多保留的日志行数。
        """

        self._logs: deque[dict[str, str]] = deque(maxlen=max_lines)
        self._lock = threading.Lock()
        self._handler: Optional[TerminalLogHandler] = None

    def start(self) -> None:
        """注册 logging handler，开始捕获全局日志。"""

        if self._handler is not None:
            return
        self._handler = TerminalLogHandler(self)
        self._handler.setFormatter(
            logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
        )
        logging.getLogger().addHandler(self._handler)

    def stop(self) -> None:
        """移除 logging handler，停止捕获全局日志。"""

        if self._handler is None:
            return
        logging.getLogger().removeHandler(self._handler)
        self._handler = None

    def append(self, message: str, level: str = "INFO") -> None:
        """向内存缓冲追加一条日志。"""

        if not message or not message.strip():
            return
        with self._lock:
            self._logs.append(
                {
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "level": level,
                    "message": message.strip(),
                }
            )

    def recent(
        self,
        count: int = 200,
        level: Optional[str] = None,
        keyword: Optional[str] = None,
    ) -> tuple[list[dict[str, str]], int]:
        """按数量、级别和关键词读取最近日志。"""

        with self._lock:
            logs = list(self._logs)
        if level:
            logs = [log for log in logs if log["level"] == level]
        if keyword:
            normalized = keyword.lower()
            logs = [log for log in logs if normalized in log["message"].lower()]
        items = logs[-count:] if count else logs
        return items, len(logs)

    def clear(self) -> None:
        """清空内存日志缓冲。"""

        with self._lock:
            self._logs.clear()


terminal_log_capture = TerminalLogCapture()
