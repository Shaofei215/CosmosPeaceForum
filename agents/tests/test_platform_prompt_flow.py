from __future__ import annotations

import json
from typing import Any

import pytest

from agents.agents_scheduler.langgraph import prompts
from agents.agents_scheduler.langgraph.nodes import tool_execution_node
from agents.agents_scheduler.langgraph.tools import feed, social
from agents.agents_scheduler.langgraph.tools.support import shared_platform
from agents.platform_tools import PlatformToolContext
from agents.platform_tools.presenters import normalize_comment, normalize_post


class _FakePlatformClient:
    """为 Prompt 流程测试提供共享工具所需的平台响应。"""

    def __init__(
        self,
        reply_items: list[dict[str, Any]] | None = None,
    ) -> None:
        """初始化回复列表与请求记录。"""

        self.reply_items = reply_items or [
            _comment_payload(301, parent_id=201, content="first reply"),
            _comment_payload(302, parent_id=201, content="second reply"),
        ]
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
        """记录显式凭据请求，并按端点返回稳定测试数据。"""

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
        if endpoint.endswith("/follow-status"):
            return {"is_following": False, "is_mutual": False}
        if endpoint == "/posts/10":
            return _post_payload()
        if endpoint == "/posts/10/comments/201":
            return _comment_payload(201, content="parent comment")
        if endpoint == "/posts/10/comments/201/replies":
            return {"items": self.reply_items, "total": len(self.reply_items)}
        if method == "POST" and endpoint == "/posts/10/comments":
            return _comment_payload(501, parent_id=201, content="new reply")
        if method == "GET" and endpoint == "/posts/10/comments":
            request_params = params or {}
            skip = int(request_params.get("skip", 0))
            limit = int(request_params.get("limit", 5))
            return {
                "items": [
                    _comment_payload(comment_id, content=f"comment {comment_id}")
                    for comment_id in range(201 + skip, 201 + skip + limit)
                ],
                "total": 12,
            }
        if endpoint == "/reports":
            return {"id": 7, "status": "pending", "message": "举报已提交"}
        if endpoint == "/feeds/feed/all":
            page_size = int((params or {}).get("page_size", 5))
            posts = [
                {
                    **_post_payload(),
                    "id": post_id,
                    "content": f"post {post_id}",
                }
                for post_id in range(1, page_size + 1)
            ]
            return {"data": posts, "pagination": {"total": 12}}
        if endpoint == "/users/1":
            return {"id": 1, "username": "profile_user"}
        if endpoint == "/feeds/feed/user/1":
            page_size = int((params or {}).get("page_size", 5))
            posts = [
                {
                    **_post_payload(),
                    "id": post_id,
                    "author_id": 1,
                    "author_name": "profile_user",
                    "content": f"profile post {post_id}",
                }
                for post_id in range(1, page_size + 1)
            ]
            return {"data": posts, "pagination": {"total": 12}}
        raise AssertionError(f"unexpected request: {method} {endpoint}")


def _install_shared_client(
    monkeypatch: pytest.MonkeyPatch,
    client: _FakePlatformClient | None = None,
) -> _FakePlatformClient:
    """让内部 LangChain 适配器使用可观测的共享平台测试上下文。"""

    client = client or _FakePlatformClient()

    def build_context() -> PlatformToolContext:
        """使用当前滚动游标构造单次共享工具上下文。"""

        return PlatformToolContext(
            client=client,  # type: ignore[arg-type]
            access_token="test-token",
            current_user={"id": 99},
            cursor=shared_platform.get_scroll_cursor(),
        )

    monkeypatch.setattr(shared_platform, "_build_internal_context", build_context)
    return client


def _post_payload():
    return {
        "id": 10,
        "author_id": 1,
        "author_name": "post_author",
        "author_bio": "bio",
        "content": "post body",
        "created_at": "2026-05-07T10:00:00",
        "like_count": 3,
        "comment_count": 4,
        "is_liked": False,
    }


def _comment_payload(comment_id=201, parent_id=None, content="root comment", children=None):
    return {
        "id": comment_id,
        "post_id": 10,
        "owner_id": comment_id + 1000,
        "owner": {"id": comment_id + 1000, "username": f"user_{comment_id}"},
        "content": content,
        "created_at": "2026-05-07T10:01:00",
        "parent_id": parent_id,
        "like_count": 1,
        "reply_count": len(children or []),
        "is_liked": False,
        "children": children or [],
    }


def test_expand_comment_returns_comment_and_reply_ids(monkeypatch):
    _install_shared_client(monkeypatch)

    result = feed.expand_comment.invoke(
        {"post_id": 10, "comment_id": 201, "reply_count": 2}
    )

    assert result["data"]["comment"]["id"] == 201
    assert result["data"]["comment"]["post_id"] == 10
    assert [reply["id"] for reply in result["data"]["replies"]] == [301, 302]
    assert result["data"]["replies"][0]["parent_id"] == 201


def test_tool_execution_then_decision_prompt_exposes_reply_parent_ids(monkeypatch):
    client = _FakePlatformClient(
        reply_items=[_comment_payload(301, parent_id=201, content="reply target")]
    )
    _install_shared_client(monkeypatch, client)

    state = {
        "username": "agent",
        "step_count": 0,
        "max_steps": 10,
        "exit_reason": None,
        "action_history": [],
        "current_location": "帖子详情页",
        "last_tool_result": None,
        "pending_tool": {
            "tool_name": "expand_comment",
            "args": {
                "post_id": 10,
                "comment_id": 201,
                "reason": "查看回复",
                "summary": "我想看这条评论下的回复",
            },
        },
        "pending_tools": None,
        "last_error": None,
        "summary": None,
        "recalled_memories": "",
    }

    next_state = tool_execution_node(state)
    prompt = prompts.build_decision_prompt(next_state)

    assert '"id":201' in prompt
    assert '"id":301' in prompt
    assert '"post_id":10' in prompt
    assert '"parent_id":201' in prompt


def test_comment_tree_from_platform_api_keeps_nested_reply_ids(monkeypatch):
    client = _FakePlatformClient()
    context = PlatformToolContext(
        client=client,  # type: ignore[arg-type]
        access_token="test-token",
        current_user={"id": 99},
    )
    platform_comment_tree = _comment_payload(
        201,
        content="root with child",
        children=[
            _comment_payload(
                301,
                parent_id=201,
                content="nested reply",
                children=[_comment_payload(401, parent_id=301, content="deep reply")],
            )
        ],
    )

    standardized = normalize_comment(platform_comment_tree, context)
    formatted = prompts._format_tool_result(
        {"post": normalize_post(_post_payload(), context), "comments": [standardized], "total": 3}
    )

    assert standardized["children"][0]["id"] == 301
    assert standardized["children"][0]["children"][0]["id"] == 401
    parsed = json.loads(formatted)
    assert parsed["comments"][0]["id"] == 201
    assert parsed["comments"][0]["children"][0]["id"] == 301
    assert parsed["comments"][0]["children"][0]["children"][0]["id"] == 401


def test_create_comment_with_parent_sends_parent_id_and_returns_new_comment_id(monkeypatch):
    client = _install_shared_client(monkeypatch)

    result = social.create_comment.invoke(
        {
            "post_id": 10,
            "content": "new reply",
            "parent_id": 201,
            "reason": "回复评论",
            "summary": "我准备回复这条评论",
        }
    )

    create_call = next(call for call in client.calls if call["method"] == "POST")
    assert create_call["endpoint"] == "/posts/10/comments"
    assert create_call["json_data"] == {
        "content": "new reply",
        "parent_id": 201,
    }
    assert result["data"]["parent_comment"]["id"] == 201
    assert result["data"]["new_comment"]["id"] == 501
    assert result["data"]["new_comment"]["parent_id"] == 201


def test_report_content_sends_report_payload(monkeypatch):
    client = _install_shared_client(monkeypatch)

    result = social.report_content.invoke(
        {
            "content_type": "comment",
            "content_id": 201,
            "report_reason": "疑似辱骂",
            "reason": "看到评论违规",
            "summary": "我正在查看评论区",
        }
    )

    assert client.calls == [
        {
            "method": "POST",
            "endpoint": "/reports",
            "access_token": "test-token",
            "json_data": {"target_type": "comment", "target_id": 201, "reason": "疑似辱骂"},
            "params": None,
            "extra_headers": None,
        }
    ]
    assert result["data"]["content_type"] == "comment"
    assert result["data"]["content_id"] == 201
    assert result["data"]["report_reason"] == "疑似辱骂"
    assert result["data"]["report"]["status"] == "pending"


def test_report_content_uses_default_report_reason(monkeypatch):
    client = _install_shared_client(monkeypatch)

    result = social.report_content.invoke(
        {"content_type": "post", "content_id": 10, "report_reason": "   "}
    )

    assert client.calls[0]["json_data"] == {
        "target_type": "post",
        "target_id": 10,
        "reason": "疑似违反社区规则",
    }
    assert result["data"]["report_reason"] == "疑似违反社区规则"


def test_prompt_for_created_reply_includes_new_comment_id():
    formatted = prompts._format_tool_result(
        {
            "post": {"id": 10, "author_id": 1, "author_username": "post_author", "content": "post"},
            "parent_comment": {
                "id": 201,
                "post_id": 10,
                "author_id": 2,
                "author_username": "parent_author",
                "content": "parent",
            },
            "new_comment": {
                "id": 501,
                "post_id": 10,
                "author_id": 99,
                "author_username": "agent",
                "content": "new reply",
                "parent_id": 201,
            },
        }
    )

    parsed = json.loads(formatted)
    assert parsed["parent_comment"]["id"] == 201
    assert parsed["new_comment"]["id"] == 501
    assert parsed["new_comment"]["parent_id"] == 201


def test_scroll_continues_global_feed_without_args(monkeypatch):
    shared_platform.clear_scroll_cursor()
    _install_shared_client(monkeypatch)

    first = feed.get_global_feed.invoke({})
    second = feed.scroll.invoke({})

    assert [post["id"] for post in first["data"]["posts"]] == [1, 2, 3, 4, 5]
    assert [post["id"] for post in second["data"]["posts"]] == [6, 7, 8, 9, 10]


def test_scroll_continues_post_comments(monkeypatch):
    shared_platform.clear_scroll_cursor()
    _install_shared_client(monkeypatch)

    first = feed.view_post_comments.invoke({"post_id": 10})
    second = feed.scroll.invoke({})

    assert [comment["id"] for comment in first["data"]["comments"]] == [201, 202, 203, 204, 205]
    assert [comment["id"] for comment in second["data"]["comments"]] == [206, 207, 208, 209, 210]


def test_scroll_continues_user_profile_posts(monkeypatch):
    shared_platform.clear_scroll_cursor()
    _install_shared_client(monkeypatch)

    profile = social.get_user_profile.invoke({"user_id": 1})
    next_posts = feed.scroll.invoke({})

    assert [post["id"] for post in profile["data"]["recent_posts"]] == [1, 2, 3, 4, 5]
    assert [post["id"] for post in next_posts["data"]["posts"]] == [6, 7, 8, 9, 10]


def test_notification_prompt_preserves_post_and_comment_ids():
    formatted = prompts._format_tool_result(
        {
            "notifications": [
                {
                    "id": 77,
                    "type": "comment",
                    "sender_id": 2,
                    "sender_username": "sender",
                    "resource_type": "comment",
                    "post_id": 10,
                    "comment_id": 201,
                    "source_content": "please reply",
                }
            ],
            "total": 1,
            "unread_count": 0,
        }
    )

    parsed = json.loads(formatted)
    assert parsed["notifications"][0]["comment_id"] == 201
    assert parsed["notifications"][0]["post_id"] == 10
