"""外部 Agent 网关基础单测。

覆盖签名滚动游标、工具白名单和参数校验，避免外部接口退化为任意平台代理。
"""

from __future__ import annotations

import pytest

from agents.external_access.cursor import CursorError, decode_cursor, encode_cursor
from agents.external_access.tools import TOOLS, ExternalToolContext, ExternalToolError, execute_tool


class FakePlatformClient:
    """用于工具执行单测的最小平台客户端。"""

    def request(self, method, endpoint, *, access_token, json_data=None, params=None, extra_headers=None):
        """返回固定平台响应。"""

        if endpoint == "/feeds/feed/all":
            return {
                "data": [
                    {
                        "id": 1,
                        "author_id": 2,
                        "author_name": "alice",
                        "content": "hello",
                        "created_at": "2026-06-30T00:00:00+08:00",
                    }
                ],
                "pagination": {"page": 1, "page_size": 1, "total": 2, "total_pages": 2, "has_next": True},
            }
        raise AssertionError(f"unexpected endpoint: {endpoint}")


def test_cursor_rejects_tampered_payload() -> None:
    """游标被篡改时应拒绝解码。"""

    cursor = encode_cursor({"kind": "global_feed", "offset": 1}, "secret")
    body, signature = cursor.split(".", 1)

    with pytest.raises(CursorError):
        decode_cursor(f"{body}x.{signature}", "secret")


def test_external_tool_whitelist_contains_v1_names() -> None:
    """v1 工具集应保持文档中的白名单名称。"""

    assert {
        "get_global_feed",
        "expand_post",
        "view_post_comments",
        "expand_comment",
        "scroll",
        "get_user_profile",
        "search_platform",
        "view_notifications",
        "view_notification_origin",
        "create_post",
        "create_comment",
        "toggle_post_like",
        "toggle_comment_like",
        "toggle_follow",
    }.issubset(TOOLS.keys())


def test_execute_tool_validates_arguments() -> None:
    """工具参数不合法时应在网关层失败，而不是拼接平台代理请求。"""

    context = ExternalToolContext(
        client=FakePlatformClient(),
        access_token="token",
        current_user={"id": 1},
        cursor_secret="secret",
    )

    with pytest.raises(ExternalToolError):
        execute_tool("get_global_feed", {"count": 0}, context)


def test_execute_feed_returns_signed_cursor() -> None:
    """可滚动读取工具应返回不含 Token 的签名游标。"""

    context = ExternalToolContext(
        client=FakePlatformClient(),
        access_token="token",
        current_user={"id": 1},
        cursor_secret="secret",
    )

    result = execute_tool("get_global_feed", {"count": 1}, context)

    assert result.has_more is True
    assert result.scroll_cursor is not None
    payload = decode_cursor(result.scroll_cursor, "secret")
    assert payload["kind"] == "global_feed"
    assert "token" not in payload
