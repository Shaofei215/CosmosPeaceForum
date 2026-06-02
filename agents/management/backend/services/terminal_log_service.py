"""
Management Backend - 终端日志捕获服务
通过自定义 logging.Handler 捕获所有日志输出
"""

import json
import logging
import os
import threading
from collections import deque
from datetime import datetime
from pathlib import Path
from typing import List, Optional


def get_default_terminal_log_path() -> Path:
    return Path(
        os.environ.get(
            "MANAGEMENT_TERMINAL_LOG_PATH",
            str(Path(__file__).resolve().parents[2] / "data" / "terminal_logs.jsonl"),
        )
    )


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

    def __init__(self, max_lines: int = 5000, log_file_path: Optional[Path] = None):
        self._logs: deque = deque(maxlen=max_lines)
        self._max_lines = max_lines
        self._lock = threading.Lock()
        self._handler: Optional[TerminalLogHandler] = None
        self._log_file_path = log_file_path

    def _target_loggers(self) -> list[logging.Logger]:
        return [logging.getLogger(), logging.getLogger("agents")]

    def start(self):
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
            self._append_to_file(log)

    def _append(self, message: str, is_error: bool = False, level: Optional[str] = None):
        self.append(message, level or ("ERROR" if is_error else "INFO"))

    def _append_to_file(self, log: dict) -> None:
        if self._log_file_path is None:
            return
        self._log_file_path.parent.mkdir(parents=True, exist_ok=True)
        with self._log_file_path.open("a", encoding="utf-8") as file:
            file.write(json.dumps(log, ensure_ascii=False) + "\n")
        self._trim_log_file()

    def _trim_log_file(self) -> None:
        if self._log_file_path is None or not self._log_file_path.exists():
            return
        if self._log_file_path.stat().st_size < 5 * 1024 * 1024:
            return
        lines = self._log_file_path.read_text(encoding="utf-8").splitlines()
        self._log_file_path.write_text(
            "\n".join(lines[-self._max_lines:]) + "\n",
            encoding="utf-8",
        )

    def _read_file_logs(self) -> List[dict]:
        if self._log_file_path is None or not self._log_file_path.exists():
            return []

        logs: list[dict] = []
        for line in self._log_file_path.read_text(encoding="utf-8").splitlines()[-self._max_lines:]:
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                continue
            if (
                isinstance(item, dict)
                and isinstance(item.get("timestamp"), str)
                and isinstance(item.get("level"), str)
                and isinstance(item.get("message"), str)
            ):
                logs.append(item)
        return logs

    def _all_logs(self) -> List[dict]:
        if self._log_file_path is not None and self._log_file_path.exists():
            return self._read_file_logs()
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
            if self._log_file_path is not None:
                self._log_file_path.parent.mkdir(parents=True, exist_ok=True)
                self._log_file_path.write_text("", encoding="utf-8")


terminal_log_capture = TerminalLogCapture(log_file_path=get_default_terminal_log_path())
