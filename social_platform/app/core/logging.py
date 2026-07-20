"""公开平台统一日志、上下文与 HTTP 访问日志。

本模块是公开平台所有运行日志的唯一初始化入口。它把同一条 ``LogRecord``
同时写到便于人工阅读的标准输出、结构化 JSONL 留存文件和现有管理端终端
缓冲，并通过请求上下文为业务日志补充关联 ID。
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import sys
import time
from contextlib import contextmanager
from contextvars import ContextVar, Token
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Callable, Iterator, Mapping, MutableMapping
from uuid import uuid4


SERVICE_NAME = "social-platform"
_REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_LOG_CONTEXT: ContextVar[dict[str, Any]] = ContextVar("social_platform_log_context", default={})


def get_log_context() -> dict[str, Any]:
    """返回当前执行上下文的日志字段副本。"""

    return dict(_LOG_CONTEXT.get())


def get_request_id() -> str | None:
    """返回当前请求或后台任务的关联 ID。"""

    value = _LOG_CONTEXT.get().get("request_id")
    return str(value) if value is not None else None


def bind_log_context(**values: Any) -> Token[dict[str, Any]]:
    """合并并绑定日志上下文，返回供调用方恢复上下文的令牌。"""

    context = get_log_context()
    context.update({key: value for key, value in values.items() if value is not None})
    return _LOG_CONTEXT.set(context)


def reset_log_context(token: Token[dict[str, Any]]) -> None:
    """恢复 ``bind_log_context`` 之前的上下文。"""

    _LOG_CONTEXT.reset(token)


@contextmanager
def logging_context(**values: Any) -> Iterator[None]:
    """在代码块内临时追加结构化日志上下文。"""

    token = bind_log_context(**values)
    try:
        yield
    finally:
        reset_log_context(token)


def normalize_request_id(value: str | None) -> str:
    """校验调用方提供的请求 ID，无效时生成新的 UUID。"""

    candidate = (value or "").strip()
    return candidate if _REQUEST_ID_PATTERN.fullmatch(candidate) else uuid4().hex


def _component_for_logger(logger_name: str) -> str:
    """根据 logger 命名空间归类公开平台组件。"""

    if logger_name.startswith("alembic"):
        return "migration"
    if logger_name.startswith("apscheduler") or ".tasks." in logger_name:
        return "scheduler"
    if logger_name.startswith("social_platform.app.admin"):
        return "admin"
    return "api"


class ContextFilter(logging.Filter):
    """把 ``ContextVar`` 中的字段附加到每条日志记录。"""

    def filter(self, record: logging.LogRecord) -> bool:
        """将当前上下文字段补入记录并允许该记录继续处理。"""

        context = get_log_context()
        for key, value in context.items():
            if not hasattr(record, key):
                setattr(record, key, value)
        return True


class JsonLogFormatter(logging.Formatter):
    """将日志记录序列化为统一 JSONL 对象。"""

    def format(self, record: logging.LogRecord) -> str:
        """返回符合双体日志字段契约的单行 JSON 字符串。"""

        timestamp = datetime.fromtimestamp(record.created).astimezone().isoformat(timespec="milliseconds")
        payload: dict[str, Any] = {
            "timestamp": timestamp,
            "level": record.levelname,
            "service": SERVICE_NAME,
            "component": getattr(record, "component", _component_for_logger(record.name)),
            "logger": record.name,
            "event": getattr(record, "event", "application.log"),
            "message": record.getMessage(),
            "thread": record.threadName,
            "request_id": getattr(record, "request_id", None),
        }
        for field in ("session_id", "agent_id"):
            value = getattr(record, field, None)
            if value is not None:
                payload[field] = value
        http = getattr(record, "http", None)
        if isinstance(http, Mapping):
            payload["http"] = dict(http)
        if record.exc_info:
            payload["exception"] = {
                "type": record.exc_info[0].__name__ if record.exc_info[0] else "Exception",
                "message": str(record.exc_info[1]),
                "stack": self.formatException(record.exc_info),
            }
        return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


class HybridRotatingFileHandler(logging.Handler):
    """按自然日或容量轮转，并同时执行期限与总容量清理的 JSONL handler。"""

    def __init__(
        self,
        log_dir: Path,
        *,
        retention_days: int,
        segment_max_bytes: int,
        max_total_bytes: int,
        now_factory: Callable[[], datetime] | None = None,
    ) -> None:
        """初始化轮转 handler，并在不阻断业务的前提下准备存储目录。

        Args:
            log_dir: 活跃文件与归档文件所在目录。
            retention_days: 归档最长保留天数。
            segment_max_bytes: 单个活跃文件触发轮转的字节数。
            max_total_bytes: 当前文件与所有归档的总容量上限。
            now_factory: 可选的带时区当前时间函数，供测试控制跨日行为。
        """

        super().__init__()
        self.log_dir = log_dir
        self.active_path = log_dir / "runtime.jsonl"
        self.retention_days = retention_days
        self.segment_max_bytes = segment_max_bytes
        self.max_total_bytes = max_total_bytes
        self._now_factory = now_factory or (lambda: datetime.now().astimezone())
        self._stream: Any | None = None
        self._active_size = self.active_path.stat().st_size if self.active_path.exists() else 0
        self._archive_total_bytes = 0
        self._opened_date = self._now_factory().date()
        self._last_error_notice = 0.0
        self._prepare_storage()

    def _prepare_storage(self) -> None:
        """创建日志目录并执行一次历史归档清理。"""

        try:
            self.log_dir.mkdir(parents=True, exist_ok=True)
            self.cleanup()
        except OSError as exc:
            self._report_storage_error(exc)

    def _open(self) -> None:
        """按追加模式延迟打开活跃 JSONL 文件。"""

        if self._stream is None:
            self.log_dir.mkdir(parents=True, exist_ok=True)
            self._stream = self.active_path.open("a", encoding="utf-8")
            self._active_size = self.active_path.stat().st_size
            try:
                os.chmod(self.active_path, 0o640)
            except OSError:
                pass

    def _should_rollover(self, encoded_size: int) -> bool:
        """判断追加指定字节数前是否需要按日期或容量轮转。"""

        now = self._now_factory()
        if now.date() != self._opened_date:
            return True
        try:
            return self._active_size + encoded_size > self.segment_max_bytes
        except OSError:
            return False

    def _archive_path(self, now: datetime) -> Path:
        """为本次轮转生成不会覆盖既有归档的路径。"""

        stem = f"runtime.{now.strftime('%Y%m%d-%H%M%S')}"
        sequence = 0
        while True:
            suffix = "" if sequence == 0 else f".{sequence}"
            candidate = self.log_dir / f"{stem}{suffix}.jsonl"
            if not candidate.exists():
                return candidate
            sequence += 1

    def _rollover(self) -> None:
        """关闭并归档活跃文件，然后执行期限和容量清理。"""

        now = self._now_factory()
        if self._stream is not None:
            self._stream.flush()
            self._stream.close()
            self._stream = None
        if self.active_path.exists() and self.active_path.stat().st_size:
            self.active_path.replace(self._archive_path(now))
        self._active_size = 0
        self._opened_date = now.date()
        self.cleanup(now=now)

    def emit(self, record: logging.LogRecord) -> None:
        """写入并立即刷新一条 JSONL 日志，存储错误不会向业务抛出。"""

        try:
            rendered = self.format(record) + "\n"
            encoded_size = len(rendered.encode("utf-8"))
            if self._should_rollover(encoded_size):
                self._rollover()
            self._open()
            assert self._stream is not None
            self._stream.write(rendered)
            self._stream.flush()
            self._active_size += encoded_size
            if self._archive_total_bytes + self._active_size > self.max_total_bytes:
                self.cleanup()
        except (OSError, UnicodeError, ValueError) as exc:
            self._report_storage_error(exc)

    def cleanup(self, *, now: datetime | None = None) -> None:
        """删除过期归档，并按最旧优先强制执行总容量上限。"""

        current = now or self._now_factory()
        cutoff = current - timedelta(days=self.retention_days)
        archives = sorted(
            self.log_dir.glob("runtime.*.jsonl"),
            key=lambda path: path.stat().st_mtime,
        )
        for path in list(archives):
            modified = datetime.fromtimestamp(path.stat().st_mtime).astimezone()
            if modified < cutoff:
                path.unlink(missing_ok=True)
                archives.remove(path)

        files = [path for path in archives if path.exists()]
        if self.active_path.exists():
            files.append(self.active_path)
        total_size = sum(path.stat().st_size for path in files)
        for path in archives:
            if total_size <= self.max_total_bytes:
                break
            if path.exists():
                size = path.stat().st_size
                path.unlink(missing_ok=True)
                total_size -= size
        self._archive_total_bytes = sum(
            path.stat().st_size for path in archives if path.exists()
        )

    def _report_storage_error(self, exc: BaseException) -> None:
        """绕过 logging 递归，按分钟限频向 stderr 报告持久化错误。"""

        now = time.monotonic()
        if now - self._last_error_notice < 60:
            return
        self._last_error_notice = now
        try:
            sys.stderr.write(f"日志持久化失败，将继续输出控制台日志: {exc}\n")
            sys.stderr.flush()
        except OSError:
            pass

    def close(self) -> None:
        """刷新并关闭活跃文件句柄。"""

        try:
            if self._stream is not None:
                self._stream.flush()
                self._stream.close()
                self._stream = None
        finally:
            super().close()


def configure_logging(
    *,
    level: str,
    log_dir: str | Path,
    retention_days: int,
    segment_max_mb: int,
    max_total_mb: int,
) -> None:
    """幂等配置公开平台根日志处理器。"""

    numeric_level = getattr(logging, level.upper(), logging.INFO)
    desired = (
        SERVICE_NAME,
        numeric_level,
        str(Path(log_dir).resolve()),
        retention_days,
        segment_max_mb,
        max_total_mb,
    )
    root = logging.getLogger()
    if getattr(root, "_cpf_logging_config", None) == desired:
        return

    for handler in list(root.handlers):
        if getattr(handler, "_cpf_managed", False):
            root.removeHandler(handler)
            handler.close()

    context_filter = ContextFilter()
    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s", "%Y-%m-%d %H:%M:%S"))
    console.addFilter(context_filter)
    console._cpf_managed = True  # type: ignore[attr-defined]

    file_handler = HybridRotatingFileHandler(
        Path(log_dir),
        retention_days=retention_days,
        segment_max_bytes=segment_max_mb * 1024 * 1024,
        max_total_bytes=max_total_mb * 1024 * 1024,
    )
    file_handler.setFormatter(JsonLogFormatter())
    file_handler.addFilter(context_filter)
    file_handler._cpf_managed = True  # type: ignore[attr-defined]

    root.addHandler(console)
    root.addHandler(file_handler)
    root.setLevel(numeric_level)
    root._cpf_logging_config = desired  # type: ignore[attr-defined]
    root._cpf_logging_service = SERVICE_NAME  # type: ignore[attr-defined]

    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        target = logging.getLogger(name)
        target.handlers.clear()
        target.propagate = True
    logging.getLogger("uvicorn.access").disabled = True


class AccessLogMiddleware:
    """为 API 请求建立关联上下文并输出统一访问日志的纯 ASGI 中间件。"""

    def __init__(
        self,
        app: Any,
        *,
        api_prefixes: tuple[str, ...],
        health_paths: tuple[str, ...] = ("/health",),
    ) -> None:
        """初始化访问中间件并声明需要记录的 API 与健康检查路径。"""

        self.app = app
        self.api_prefixes = api_prefixes
        self.health_paths = health_paths
        self.logger = logging.getLogger("social_platform.access")

    def _is_logged_path(self, path: str) -> bool:
        """判断请求路径是否属于需要留存的后端接口。"""

        return path in self.health_paths or any(path.startswith(prefix) for prefix in self.api_prefixes)

    async def __call__(self, scope: MutableMapping[str, Any], receive: Any, send: Any) -> None:
        """执行下游 ASGI 应用，并在完整响应结束后记录访问结果。"""

        if scope.get("type") != "http" or not self._is_logged_path(str(scope.get("path", ""))):
            await self.app(scope, receive, send)
            return

        headers = {key.decode("latin-1").lower(): value.decode("latin-1") for key, value in scope.get("headers", [])}
        request_id = normalize_request_id(headers.get("x-request-id"))
        scope.setdefault("state", {})["request_id"] = request_id
        client = scope.get("client")
        client_ip = client[0] if client else None
        method = str(scope.get("method", "GET"))
        path = str(scope.get("path", ""))
        started = time.perf_counter()
        status_code = 500
        token = bind_log_context(request_id=request_id, client_ip=client_ip)

        async def send_with_request_id(message: MutableMapping[str, Any]) -> None:
            """捕获响应状态，并把最终请求 ID 写入响应头。"""

            nonlocal status_code
            if message.get("type") == "http.response.start":
                status_code = int(message.get("status", 500))
                response_headers = list(message.get("headers", []))
                response_headers = [
                    (key, value)
                    for key, value in response_headers
                    if key.lower() != b"x-request-id"
                ]
                response_headers.append((b"x-request-id", request_id.encode("ascii")))
                message["headers"] = response_headers
            await send(message)

        failed = False
        try:
            await self.app(scope, receive, send_with_request_id)
        except asyncio.CancelledError:
            status_code = 499
            raise
        except Exception:
            failed = True
            route = getattr(scope.get("route"), "path", path)
            elapsed_ms = round((time.perf_counter() - started) * 1000, 3)
            self.logger.exception(
                "HTTP %s %s 未处理异常",
                method,
                route,
                extra={
                    "event": "http.exception",
                    "request_id": request_id,
                    "http": {
                        "method": method,
                        "route": route,
                        "status_code": status_code,
                        "duration_ms": elapsed_ms,
                        "client_ip": client_ip,
                        "user_agent": headers.get("user-agent", ""),
                    },
                },
            )
            raise
        finally:
            if not failed:
                route = getattr(scope.get("route"), "path", path)
                elapsed_ms = round((time.perf_counter() - started) * 1000, 3)
                if method == "OPTIONS" or path in self.health_paths:
                    level = logging.DEBUG
                elif status_code >= 500:
                    level = logging.ERROR
                elif status_code >= 400:
                    level = logging.WARNING
                else:
                    level = logging.INFO
                self.logger.log(
                    level,
                    "HTTP %s %s %d %.3fms",
                    method,
                    route,
                    status_code,
                    elapsed_ms,
                    extra={
                        "event": "http.request",
                        "request_id": request_id,
                        "http": {
                            "method": method,
                            "route": route,
                            "status_code": status_code,
                            "duration_ms": elapsed_ms,
                            "client_ip": client_ip,
                            "user_agent": headers.get("user-agent", ""),
                        },
                    },
                )
            reset_log_context(token)
