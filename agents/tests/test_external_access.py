"""外部 Agent 网关基础单测。

覆盖签名滚动游标、工具白名单和参数校验，避免外部接口退化为任意平台代理。
"""

from __future__ import annotations

import pytest

from agents.agents_scheduler.langgraph.tools import feed, social
from agents.external_access.cursor import CursorError, decode_cursor, encode_cursor
from agents.external_access.schemas import ToolMeta
from agents.external_access.tools import TOOLS, ExternalToolContext, ExternalToolError, execute_tool
from agents.platform_tools import PlatformToolContext, execute_platform_tool


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
        if endpoint == "/notifications":
            skip = int((params or {}).get("skip", 0))
            return {
                "items": [
                    {
                        "id": 201 + skip,
                        "type": "mention",
                        "source_content": f"notification {201 + skip}",
                        "created_at": "2026-06-30T00:00:00+08:00",
                    }
                ],
                "total": 2,
                "unread_count": 0,
            }
        raise AssertionError(f"unexpected endpoint: {endpoint}")


def test_cursor_rejects_tampered_payload() -> None:
    """游标被篡改时应拒绝解码。"""

    cursor = encode_cursor({"kind": "global_feed", "offset": 1}, "secret")
    body, signature = cursor.split(".", 1)

    with pytest.raises(CursorError):
        decode_cursor(f"{body}x.{signature}", "secret")


def test_external_tool_whitelist_contains_v1_names() -> None:
    """v1 工具集必须精确等于文档中的外部白名单名称。"""

    assert set(TOOLS.keys()) == {
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
    }


def test_external_scroll_schema_requires_signed_cursor() -> None:
    """外部 scroll schema 必须要求签名游标，但共享核心不直接持有该字段。"""

    schema = TOOLS["scroll"].input_schema()

    assert "scroll_cursor" in schema["required"]
    assert schema["properties"]["scroll_cursor"]["minLength"] == 16
    assert "count" in schema["properties"]


def test_external_notifications_schema_matches_internal_tool() -> None:
    """外部通知工具不得公开内部工具没有的筛选参数。"""

    schema = TOOLS["view_notifications"].input_schema()

    assert set(schema["properties"]) == {"count"}


def test_external_business_parameters_match_internal_tools() -> None:
    """外部工具业务参数必须逐项向内部 LangChain 工具看齐。"""

    internal_tools = {
        "get_global_feed": feed.get_global_feed,
        "expand_post": feed.expand_post,
        "view_post_comments": feed.view_post_comments,
        "expand_comment": feed.expand_comment,
        "scroll": feed.scroll,
        "get_user_profile": social.get_user_profile,
        "search_platform": social.search_platform,
        "view_notifications": social.view_notifications,
        "view_notification_origin": social.view_notification_origin,
        "create_post": social.create_post,
        "create_comment": social.create_comment,
        "toggle_post_like": social.toggle_post_like,
        "toggle_comment_like": social.toggle_comment_like,
        "toggle_follow": social.toggle_follow,
    }

    for name, internal_tool in internal_tools.items():
        internal_schema = internal_tool.args_schema.model_json_schema()
        expected_properties = set(internal_schema.get("properties", {})) - {"reason", "summary"}
        expected_required = set(internal_schema.get("required", [])) - {"reason", "summary"}
        if name == "scroll":
            expected_properties.add("scroll_cursor")
            expected_required.add("scroll_cursor")

        external_schema = TOOLS[name].input_schema()
        assert set(external_schema.get("properties", {})) == expected_properties, name
        assert set(external_schema.get("required", [])) == expected_required, name


def test_external_meta_never_exposes_has_more() -> None:
    """外部协议只用游标表达可继续滚动，不得暴露额外分页布尔值。"""

    assert ToolMeta(request_id="request-id", scroll_cursor="cursor").model_dump() == {
        "request_id": "request-id",
        "schema_version": "1",
        "scroll_cursor": "cursor",
    }


def test_execute_tool_validates_arguments() -> None:
    """工具参数不合法时应在网关层失败，而不是拼接平台代理请求。"""

    context = ExternalToolContext(
        client=FakePlatformClient(),
        access_token="token",
        current_user={"id": 1},
        cursor_secret="secret",
    )

    with pytest.raises(ExternalToolError):
        execute_tool("get_global_feed", {"feed_type": "invalid"}, context)


def test_execute_feed_returns_signed_cursor() -> None:
    """可滚动读取工具应返回不含 Token 的签名游标。"""

    context = ExternalToolContext(
        client=FakePlatformClient(),
        access_token="token",
        current_user={"id": 1},
        cursor_secret="secret",
    )

    result = execute_tool("get_global_feed", {}, context)

    assert set(result.data) == {"posts"}
    assert result.scroll_cursor is not None
    payload = decode_cursor(result.scroll_cursor, "secret")
    assert payload["kind"] == "global_feed"
    assert "token" not in payload


def test_external_feed_content_matches_internal_builder() -> None:
    """外部适配器返回的数据必须与内部共享构建结果完全一致。"""

    internal = execute_platform_tool(
        "get_global_feed",
        {},
        PlatformToolContext(
            client=FakePlatformClient(),
            access_token="token",
            current_user={"id": 1},
        ),
    )
    external = execute_tool(
        "get_global_feed",
        {},
        ExternalToolContext(
            client=FakePlatformClient(),
            access_token="token",
            current_user={"id": 1},
            cursor_secret="secret",
        ),
    )

    assert external.action == internal.action
    assert external.data == internal.data
    assert "pagination" not in external.data


def test_external_notifications_scroll_with_signed_cursor() -> None:
    """外部通知读取必须通过签名游标继续读取，并在末页停止返回游标。"""

    context = ExternalToolContext(
        client=FakePlatformClient(),
        access_token="token",
        current_user={"id": 1},
        cursor_secret="secret",
    )

    first = execute_tool("view_notifications", {"count": 1}, context)
    assert first.scroll_cursor is not None
    payload = decode_cursor(first.scroll_cursor, "secret")
    assert payload["kind"] == "notifications"
    assert payload["offset"] == 1
    assert set(payload) == {"kind", "offset", "v", "exp"}

    second = execute_tool(
        "scroll",
        {"count": 1, "scroll_cursor": first.scroll_cursor},
        context,
    )
    assert second.data["notifications"][0]["id"] == 202
    assert set(first.data) == {"notifications", "total", "unread_count"}
    assert set(second.data) == {"notifications", "total", "unread_count"}
    assert second.scroll_cursor is None
