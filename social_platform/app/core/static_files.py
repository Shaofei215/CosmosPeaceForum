import os
from secrets import token_hex

import anyio
from starlette.exceptions import HTTPException
from starlette.datastructures import Headers
from starlette.responses import FileResponse, Response
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
    async def get_response(self, path: str, scope: Scope) -> Response:
        try:
            return await super().get_response(path, scope)
        except HTTPException as exc:
            if exc.status_code != 404:
                raise

            request_path = scope.get("path", "")
            if scope.get("method") not in ("GET", "HEAD"):
                raise
            if request_path.startswith("/api") or request_path.startswith("/uploads"):
                raise
            if "." in os.path.basename(request_path):
                raise

            return await super().get_response("index.html", scope)
