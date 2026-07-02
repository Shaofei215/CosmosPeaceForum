"""共享平台工具核心单测。

这些测试直接覆盖 `agents.platform_tools`，避免内部 LangChain adapter 或外部 HTTP
adapter 的兼容层掩盖共享核心的参数、展示模式和滚动语义问题。
"""

from __future__ import annotations

from typing import Any

import pytest

from agents.agents_scheduler.langgraph.tools.support import shared_platform
from agents.platform_tools import (
    PlatformToolContext,
    PlatformToolError,
    execute_platform_tool,
)


class FakePlatformClient:
    """记录请求并返回固定平台响应的测试客户端。"""

    def __init__(self) -> None:
        """初始化请求记录。"""

        self.calls: list[dict[str, Any]] = []

    def request(
        self,
        method: str,
        endpoint: str,
        *,
        access_token: str | None,
        json_data: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
        extra_headers: dict[str, str] | None = None,
    ) -> Any:
        """按 endpoint 返回共享工具需要的最小响应。"""

        self.calls.append(
            {
                "method": method,
                "endpoint": endpoint,
                "access_token": access_token,
                "json_data": json_data,
                "params": params,
                "extra_headers": extra_headers,
            }
        )
        if endpoint == "/posts/1":
            return {
                "id": 1,
                "author_id": 10,
                "author_name": "alice",
                "title": "长文",
                "type": "article",
                "content": "# 标题\n正文内容",
                "created_at": "2026-06-30T00:00:00+08:00",
                "like_count": 2,
                "comment_count": 1,
                "is_liked": False,
            }
        if endpoint == "/posts/1/comments":
            return {"items": [], "total": 12, "skip": 0, "limit": 5}
        if endpoint == "/users/10/follow-status":
            return {"is_following": False, "is_mutual": False, "is_followed_by": False}
        if endpoint == "/feeds/feed/all":
            return {
                "data": [
                    {
                        "id": 2,
                        "author_id": 11,
                        "author_name": "bob",
                        "type": "post",
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
                        "id": 101 + skip,
                        "type": "comment",
                        "source_content": f"notification {101 + skip}",
                        "created_at": "2026-06-30T00:00:00+08:00",
                    }
                ],
                "total": 2,
                "unread_count": 0,
                "skip": skip,
                "limit": (params or {}).get("limit", 1),
            }
        if endpoint == "/search":
            return {
                "data": [],
                "pagination": {
                    "page": 1,
                    "page_size": 5,
                    "total": 12,
                    "total_pages": 3,
                    "has_next": True,
                },
            }
        if endpoint == "/hot-topics":
            return [{"rank": 1, "title": "热榜", "summary": "摘要", "search_query": "关键词"}]
        if endpoint == "/users/11/follow-status":
            return {"is_following": True, "is_mutual": False, "is_followed_by": False}
        if endpoint == "/posts/":
            return {
                "id": 3,
                "author_id": 1,
                "author_name": "me",
                "type": json_data["type"],
                "title": json_data.get("title"),
                "content": json_data["content"],
                "created_at": "2026-06-30T00:00:00+08:00",
            }
        if endpoint == "/auth/logout":
            return {"message": "登出成功"}
        if endpoint == "/users/1" and method == "PUT":
            return {
                "id": 1,
                "username": (json_data or {}).get("username", "old_name"),
                "bio": (json_data or {}).get("bio", "old signature"),
                "avatar_url": None,
            }
        raise AssertionError(f"unexpected endpoint: {endpoint}")


def test_expand_post_uses_shared_agent_content_format() -> None:
    """内外部适配器共用内部 Agent 既有的文章内容格式。"""

    client = FakePlatformClient()
    result = execute_platform_tool(
        "expand_post",
        {"post_id": 1},
        PlatformToolContext(
            client=client,
            access_token="token",
            current_user={"id": 1},
        ),
    )

    assert result.data["post"]["content"].startswith("文章标题：长文")


def test_feed_uses_explicit_token_and_returns_cursor() -> None:
    """读取工具必须使用上下文显式 Token，并返回未签名滚动状态给 adapter 包装。"""

    client = FakePlatformClient()
    result = execute_platform_tool(
        "get_global_feed",
        {"feed_type": "hot", "seed": "abc"},
        PlatformToolContext(
            client=client,
            access_token="token",
            current_user={"id": 1},
        ),
    )

    assert client.calls[0]["access_token"] == "token"
    assert client.calls[0]["params"] == {
        "page": 1,
        "page_size": 5,
        "feed_type": "recommended",
        "seed": "abc",
    }
    assert set(result.data) == {"posts"}
    assert result.cursor == {"kind": "global_feed", "feed_type": "recommended", "seed": "abc", "offset": 1}


def test_notifications_and_scroll_share_cursor() -> None:
    """内部和外部共用的通知读取核心必须支持继续滚动。"""

    client = FakePlatformClient()
    context = PlatformToolContext(
        client=client,
        access_token="token",
        current_user={"id": 1},
    )

    first = execute_platform_tool(
        "view_notifications",
        {"count": 1},
        context,
    )
    second = execute_platform_tool(
        "scroll",
        {"count": 1},
        PlatformToolContext(
            client=client,
            access_token="token",
            current_user={"id": 1},
            cursor=first.cursor,
        ),
    )

    assert first.cursor == {"kind": "notifications", "offset": 1}
    assert second.data["notifications"][0]["id"] == 102
    assert set(first.data) == {"notifications"}
    assert set(second.data) == {"notifications"}
    assert second.cursor is None
    assert client.calls[-1]["params"] == {"skip": 1, "limit": 1}


def test_internal_adapter_keeps_notification_scroll_state(monkeypatch: pytest.MonkeyPatch) -> None:
    """内部 LangGraph 适配器必须保存通知游标供下一次 scroll 使用。"""

    client = FakePlatformClient()
    stored_cursor: dict[str, Any] | None = None

    def build_context() -> PlatformToolContext:
        """按内部线程当前保存的游标构造测试上下文。"""

        return PlatformToolContext(
            client=client,
            access_token="token",
            current_user={"id": 1},
            cursor=stored_cursor,
        )

    def save_cursor(cursor: dict[str, Any] | None) -> None:
        """模拟内部执行上下文保存最近一次滚动游标。"""

        nonlocal stored_cursor
        stored_cursor = cursor

    monkeypatch.setattr(shared_platform, "_build_internal_context", build_context)
    monkeypatch.setattr(shared_platform, "_set_scroll_cursor", save_cursor)

    shared_platform.run_shared_tool("view_notifications", {"count": 1})
    second = shared_platform.run_shared_tool("scroll", {"count": 1})

    assert second.data["notifications"][0]["id"] == 102
    assert stored_cursor is None


def test_create_post_rejects_poll_on_article_before_platform_request() -> None:
    """共享核心应在本地拒绝明显无效参数，不能拼出平台写请求。"""

    client = FakePlatformClient()

    with pytest.raises(PlatformToolError):
        execute_platform_tool(
            "create_post",
            {"content": "正文", "title": "标题", "type": "article", "poll_options": ["A", "B"]},
            PlatformToolContext(client=client, access_token="token", current_user={"id": 1}),
        )

    assert client.calls == []


def test_logout_revokes_external_platform_session() -> None:
    """共享登出处理器必须撤销外部 Agent 当前使用的公开平台 Session。"""

    client = FakePlatformClient()

    result = execute_platform_tool(
        "logout",
        {},
        PlatformToolContext(client=client, access_token="token", current_user={"id": 1}),
    )

    assert result.data == {}
    assert client.calls[-1]["method"] == "POST"
    assert client.calls[-1]["endpoint"] == "/auth/logout"


def test_update_profile_syncs_internal_configuration() -> None:
    """资料工具应更新公开平台，并把确认后的完整资料交给内部同步回调。"""

    client = FakePlatformClient()
    synchronized_profiles: list[dict[str, Any]] = []

    def synchronize(profile: dict[str, Any]) -> bool:
        """记录共享核心传给内部 Scheduler 的资料。"""

        synchronized_profiles.append(profile)
        return True

    result = execute_platform_tool(
        "update_profile",
        {"username": "new_name", "personal_signature": "new signature"},
        PlatformToolContext(
            client=client,
            access_token="token",
            current_user={"id": 1, "username": "old_name", "bio": "old signature"},
            profile_sync=synchronize,
        ),
    )

    assert client.calls[-1]["json_data"] == {"username": "new_name", "bio": "new signature"}
    assert synchronized_profiles[0]["username"] == "new_name"
    assert result.data["username"] == "new_name"
    assert result.data["bio"] == "new signature"


def test_update_profile_rolls_back_platform_when_internal_sync_fails() -> None:
    """内部配置写入失败时必须恢复公开平台的旧用户名和签名。"""

    client = FakePlatformClient()
    context = PlatformToolContext(
        client=client,
        access_token="token",
        current_user={"id": 1, "username": "old_name", "bio": "old signature"},
        profile_sync=lambda _: False,
    )

    with pytest.raises(PlatformToolError, match="已自动回滚"):
        execute_platform_tool(
            "update_profile",
            {"username": "new_name", "personal_signature": "new signature"},
            context,
        )

    profile_calls = [call for call in client.calls if call["endpoint"] == "/users/1"]
    assert profile_calls[-1]["json_data"] == {
        "username": "old_name",
        "bio": "old signature",
    }


def test_update_profile_requires_at_least_one_field() -> None:
    """空资料更新必须在请求公开平台前被参数模型拒绝。"""

    client = FakePlatformClient()
    with pytest.raises(PlatformToolError):
        execute_platform_tool(
            "update_profile",
            {},
            PlatformToolContext(client=client, access_token="token", current_user={"id": 1}),
        )
    assert client.calls == []


def test_list_tools_return_entities_without_pagination_or_totals() -> None:
    """各列表工具应在构造结果时明确丢弃上游分页与总数字段。"""

    client = FakePlatformClient()
    context = PlatformToolContext(client=client, access_token="token", current_user={"id": 1})

    comments = execute_platform_tool(
        "view_post_comments",
        {"post_id": 1},
        context,
    )
    search = execute_platform_tool(
        "search_platform",
        {"type": "content", "query": "关键词"},
        context,
    )
    notifications = execute_platform_tool("view_notifications", {}, context)
    hot_topics = execute_platform_tool("view_full_hot_topics", {}, context)

    assert set(comments.data) == {"post", "comments"}
    assert set(search.data) == {"type", "query", "posts"}
    assert set(notifications.data) == {"notifications"}
    assert set(hot_topics.data) == {"hot_topics"}
