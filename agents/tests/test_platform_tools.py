"""共享平台工具核心单测。

这些测试直接覆盖 `agents.platform_tools`，避免内部 LangChain adapter 或外部 HTTP
adapter 的兼容层掩盖共享核心的参数、展示模式和滚动语义问题。
"""

from __future__ import annotations

from typing import Any

import pytest

from agents.platform_tools import (
    PlatformToolContext,
    PlatformToolError,
    PresentationMode,
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
        raise AssertionError(f"unexpected endpoint: {endpoint}")


def test_expand_post_formats_article_differently_by_presentation_mode() -> None:
    """内部模式保留 Prompt 提示，外部模式返回原始 Markdown 正文。"""

    client = FakePlatformClient()
    internal = execute_platform_tool(
        "expand_post",
        {"post_id": 1},
        PlatformToolContext(
            client=client,
            access_token="token",
            current_user={"id": 1},
            mode=PresentationMode.INTERNAL,
        ),
    )
    external = execute_platform_tool(
        "expand_post",
        {"post_id": 1},
        PlatformToolContext(
            client=client,
            access_token="token",
            current_user={"id": 1},
            mode=PresentationMode.EXTERNAL,
        ),
    )

    assert internal.data["post"]["content"].startswith("文章标题：长文")
    assert external.data["post"]["content"] == "# 标题\n正文内容"


def test_feed_uses_explicit_token_and_returns_cursor() -> None:
    """读取工具必须使用上下文显式 Token，并返回未签名滚动状态给 adapter 包装。"""

    client = FakePlatformClient()
    result = execute_platform_tool(
        "get_global_feed",
        {"count": 1, "feed_type": "hot", "seed": "abc"},
        PlatformToolContext(
            client=client,
            access_token="token",
            current_user={"id": 1},
            mode=PresentationMode.EXTERNAL,
        ),
    )

    assert client.calls[0]["access_token"] == "token"
    assert client.calls[0]["params"] == {
        "page": 1,
        "page_size": 1,
        "feed_type": "recommended",
        "seed": "abc",
    }
    assert result.cursor == {"kind": "global_feed", "feed_type": "recommended", "seed": "abc", "offset": 1}
    assert result.has_more is True


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
