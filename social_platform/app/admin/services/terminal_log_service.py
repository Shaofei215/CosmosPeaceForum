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
    def __init__(self, max_lines: int = 5000):
        self._logs: deque[dict[str, str]] = deque(maxlen=max_lines)
        self._lock = threading.Lock()
        self._handler: Optional[TerminalLogHandler] = None

    def start(self) -> None:
        if self._handler is not None:
            return
        self._handler = TerminalLogHandler(self)
        self._handler.setFormatter(
            logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
        )
        logging.getLogger().addHandler(self._handler)

    def stop(self) -> None:
        if self._handler is None:
            return
        logging.getLogger().removeHandler(self._handler)
        self._handler = None

    def append(self, message: str, level: str = "INFO") -> None:
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

    def recent(self, count: int = 200, level: Optional[str] = None, keyword: Optional[str] = None):
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
        with self._lock:
            self._logs.clear()


terminal_log_capture = TerminalLogCapture()

