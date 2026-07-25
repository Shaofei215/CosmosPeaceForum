import os
from html import escape
from pathlib import Path
from secrets import token_hex
from typing import Mapping

import anyio
from starlette.exceptions import HTTPException
from starlette.datastructures import Headers
from starlette.responses import FileResponse, HTMLResponse, Response
from starlette.staticfiles import NotModifiedResponse, StaticFiles
from starlette.types import Scope, Send


async def _send_not_found(send: Send) -> None:
    await send({
        "type": "http.response.start",
        "status": 404,
        "headers": [(b"content-type", b"text/plain; charset=utf-8")],
    })
    await send({
        "type": "http.response.body",
        "body": b"Not Found",
        "more_body": False,
    })


def render_spa_index(index_file: Path, replacements: Mapping[str, str]) -> str:
    """读取 SPA 入口页面并注入经过 HTML 转义的运行时配置。

    Args:
        index_file: 前端构建产物中的 ``index.html``。
        replacements: HTML 占位符及其运行时配置值。

    Returns:
        str: 已替换运行时配置的入口页面。
    """

    html = index_file.read_text(encoding="utf-8")
    for placeholder, value in replacements.items():
        html = html.replace(placeholder, escape(value, quote=True))
    return html


class RaceSafeFileResponse(FileResponse):
    async def _handle_simple(
        self,
        send: Send,
        send_header_only: bool,
        send_pathsend: bool,
    ) -> None:
        if send_header_only:
            if not os.path.exists(self.path):
                await _send_not_found(send)
                return
            await send({
                "type": "http.response.start",
                "status": self.status_code,
                "headers": self.raw_headers,
            })
            await send({"type": "http.response.body", "body": b"", "more_body": False})
            return

        try:
            file = await anyio.open_file(self.path, mode="rb")
        except FileNotFoundError:
            await _send_not_found(send)
            return

        async with file:
            await send({
                "type": "http.response.start",
                "status": self.status_code,
                "headers": self.raw_headers,
            })
            more_body = True
            while more_body:
                chunk = await file.read(self.chunk_size)
                more_body = len(chunk) == self.chunk_size
                await send({
                    "type": "http.response.body",
                    "body": chunk,
                    "more_body": more_body,
                })

    async def _handle_single_range(
        self,
        send: Send,
        start: int,
        end: int,
        file_size: int,
        send_header_only: bool,
    ) -> None:
        self.headers["content-range"] = f"bytes {start}-{end - 1}/{file_size}"
        self.headers["content-length"] = str(end - start)

        if send_header_only:
            if not os.path.exists(self.path):
                await _send_not_found(send)
                return
            await send({"type": "http.response.start", "status": 206, "headers": self.raw_headers})
            await send({"type": "http.response.body", "body": b"", "more_body": False})
            return

        try:
            file = await anyio.open_file(self.path, mode="rb")
        except FileNotFoundError:
            await _send_not_found(send)
            return

        async with file:
            await send({"type": "http.response.start", "status": 206, "headers": self.raw_headers})
            await file.seek(start)
            more_body = True
            while more_body:
                chunk = await file.read(min(self.chunk_size, end - start))
                start += len(chunk)
                more_body = len(chunk) == self.chunk_size and start < end
                await send({
                    "type": "http.response.body",
                    "body": chunk,
                    "more_body": more_body,
                })

    async def _handle_multiple_ranges(
        self,
        send: Send,
        ranges: list[tuple[int, int]],
        file_size: int,
        send_header_only: bool,
    ) -> None:
        boundary = token_hex(13)
        content_length, header_generator = self.generate_multipart(
            ranges,
            boundary,
            file_size,
            self.headers["content-type"],
        )
        self.headers["content-range"] = f"multipart/byteranges; boundary={boundary}"
        self.headers["content-length"] = str(content_length)

        if send_header_only:
            if not os.path.exists(self.path):
                await _send_not_found(send)
                return
            await send({"type": "http.response.start", "status": 206, "headers": self.raw_headers})
            await send({"type": "http.response.body", "body": b"", "more_body": False})
            return

        try:
            file = await anyio.open_file(self.path, mode="rb")
        except FileNotFoundError:
            await _send_not_found(send)
            return

        async with file:
            await send({"type": "http.response.start", "status": 206, "headers": self.raw_headers})
            for start, end in ranges:
                await send({
                    "type": "http.response.body",
                    "body": header_generator(start, end),
                    "more_body": True,
                })
                await file.seek(start)
                while start < end:
                    chunk = await file.read(min(self.chunk_size, end - start))
                    start += len(chunk)
                    await send({
                        "type": "http.response.body",
                        "body": chunk,
                        "more_body": True,
                    })
                await send({"type": "http.response.body", "body": b"\n", "more_body": True})
            await send({
                "type": "http.response.body",
                "body": f"\n--{boundary}--\n".encode("latin-1"),
                "more_body": False,
            })


class RaceSafeStaticFiles(StaticFiles):
    def file_response(
        self,
        full_path: os.PathLike[str] | str,
        stat_result: os.stat_result,
        scope: Scope,
        status_code: int = 200,
    ) -> Response:
        request_headers = Headers(scope=scope)
        response = RaceSafeFileResponse(
            full_path,
            status_code=status_code,
            stat_result=stat_result,
        )
        if self.is_not_modified(response.headers, request_headers):
            return NotModifiedResponse(response.headers)
        return response


class SPAStaticFiles(RaceSafeStaticFiles):
    def __init__(
        self,
        *,
        directory: os.PathLike[str] | str | None = None,
        packages: list[str | tuple[str, str]] | None = None,
        html: bool = False,
        check_dir: bool = True,
        follow_symlink: bool = False,
        index_html: str | None = None,
        excluded_prefixes: tuple[str, ...] = ("/api", "/uploads"),
    ) -> None:
        """初始化支持运行时配置注入和客户端路由回退的静态文件服务。

        Args:
            directory: 静态文件目录。
            packages: Starlette 包静态目录配置。
            html: 是否启用 HTML 目录索引。
            check_dir: 初始化时是否检查目录存在。
            follow_symlink: 是否允许跟随符号链接。
            index_html: 已注入运行时配置的 SPA 入口内容。
            excluded_prefixes: 不允许回退到 SPA 的请求路径前缀。
        """

        super().__init__(
            directory=directory,
            packages=packages,
            html=html,
            check_dir=check_dir,
            follow_symlink=follow_symlink,
        )
        self.index_html = index_html
        self.excluded_prefixes = excluded_prefixes

    def _index_response(self, scope: Scope) -> HTMLResponse:
        """返回已注入配置的入口页面，并正确处理 HEAD 请求。"""

        response = HTMLResponse(self.index_html or "")
        if scope.get("method") == "HEAD":
            response.body = b""
        return response

    async def get_response(self, path: str, scope: Scope) -> Response:
        if self.index_html is not None and path in ("", ".", "index.html"):
            return self._index_response(scope)

        try:
            return await super().get_response(path, scope)
        except HTTPException as exc:
            if exc.status_code != 404:
                raise

            request_path = scope.get("path", "")
            if scope.get("method") not in ("GET", "HEAD"):
                raise
            if any(request_path.startswith(prefix) for prefix in self.excluded_prefixes):
                raise
            if "." in os.path.basename(request_path):
                raise

            if self.index_html is not None:
                return self._index_response(scope)
            return await super().get_response("index.html", scope)
