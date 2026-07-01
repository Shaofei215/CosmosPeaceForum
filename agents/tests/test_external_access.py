"""外部 Agent 网关基础单测。

覆盖签名滚动游标、工具白名单和参数校验，避免外部接口退化为任意平台代理。
"""

from __future__ import annotations

import json
import importlib
from types import SimpleNamespace

import pytest
from fastapi import Request
from fastapi.security import HTTPAuthorizationCredentials

from agents.agents_scheduler.langgraph.tools import feed, hot_topic, social
from agents.external_access.cursor import CursorError, decode_cursor, encode_cursor
from agents.external_access.schemas import ToolExecutionRequest, ToolMeta
from agents.external_access.tools import (
    TOOLS,
    ExternalToolContext,
    ExternalToolError,
    ExternalToolResult,
    execute_tool,
)
from agents.platform_tools import PlatformToolContext, execute_platform_tool

external_router = importlib.import_module("agents.external_access.router")


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


class FakeGatewayClient:
    """模拟外部网关认证预检和未读数量查询。"""

    unread_count = 0

    def __init__(self, **_: object) -> None:
        """忽略真实客户端构造参数。"""

    def request(self, method, endpoint, *, access_token, json_data=None, params=None, extra_headers=None):
        """返回当前账号和测试配置的未读数量。"""

        if endpoint == "/auth/me":
            return {"id": 1, "username": "agent"}
        if endpoint == "/notifications/unread-count":
            return {"unread_count": self.unread_count}
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
        "vote_post_poll",
        "delete_content",
        "report_content",
        "repost",
        "view_full_hot_topics",
        "logout",
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
        "vote_post_poll": social.vote_post_poll,
        "delete_content": social.delete_content,
        "report_content": social.report_content,
        "repost": social.repost,
        "view_full_hot_topics": hot_topic.view_full_hot_topics,
        "logout": social.logout,
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
    assert set(first.data) == {"notifications"}
    assert set(second.data) == {"notifications"}
    assert second.scroll_cursor is None


@pytest.mark.parametrize("unread_count,expected", [(3, 3), (0, None)])
def test_external_tool_response_only_includes_positive_unread_count(
    monkeypatch: pytest.MonkeyPatch,
    unread_count: int,
    expected: int | None,
) -> None:
    """外部工具每次成功执行后查询未读数，零值不进入 data。"""

    FakeGatewayClient.unread_count = unread_count
    monkeypatch.setattr(external_router, "PlatformClient", FakeGatewayClient)
    monkeypatch.setattr(
        external_router,
        "get_config",
        lambda: SimpleNamespace(
            jwt_secret_key="secret",
            social_platform_api_base_url="http://platform/api/v1",
            admin_key="admin",
        ),
    )
    monkeypatch.setattr(
        external_router,
        "execute_tool",
        lambda name, arguments, context: ExternalToolResult(
            action="浏览了主页信息流",
            data={"posts": []},
        ),
    )
    request = Request({"type": "http", "method": "POST", "path": "/", "headers": []})

    response = external_router.run_tool(
        "get_global_feed",
        ToolExecutionRequest(arguments={}),
        request,
        HTTPAuthorizationCredentials(scheme="Bearer", credentials="token"),
    )

    assert not hasattr(response, "body")
    if expected is None:
        assert "unread_count" not in response.data
    else:
        assert response.data["unread_count"] == expected


def test_authenticated_external_tool_error_can_include_unread_count(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """认证仍有效的工具参数错误应尽量携带正数未读提醒。"""

    FakeGatewayClient.unread_count = 2
    monkeypatch.setattr(external_router, "PlatformClient", FakeGatewayClient)
    monkeypatch.setattr(
        external_router,
        "get_config",
        lambda: SimpleNamespace(
            jwt_secret_key="secret",
            social_platform_api_base_url="http://platform/api/v1",
            admin_key="admin",
        ),
    )

    def raise_invalid(*_: object) -> ExternalToolResult:
        """模拟共享工具参数校验失败。"""

        raise ExternalToolError("参数无效")

    monkeypatch.setattr(external_router, "execute_tool", raise_invalid)
    request = Request({"type": "http", "method": "POST", "path": "/", "headers": []})

    response = external_router.run_tool(
        "get_global_feed",
        ToolExecutionRequest(arguments={}),
        request,
        HTTPAuthorizationCredentials(scheme="Bearer", credentials="token"),
    )
    payload = json.loads(response.body)

    assert response.status_code == 422
    assert payload["data"] == {"unread_count": 2}
