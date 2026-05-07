from unittest.mock import MagicMock

from agents.agents_scheduler.langgraph import prompts
from agents.agents_scheduler.langgraph.nodes import tool_execution_node
from agents.agents_scheduler.langgraph.tools import feed, social, utils


def _disable_relation_expansion(monkeypatch):
    monkeypatch.setattr(
        utils,
        "_expand_username_by_relation",
        lambda username, user_id, owner_id: username,
    )
    monkeypatch.setattr(
        utils,
        "_expand_content_mentions_by_relation",
        lambda content, owner_id: content,
    )
    monkeypatch.setattr(utils, "_get_follow_status_text", lambda user_id, current_user_id: "")


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


def test_expand_comments_returns_comment_and_reply_ids(monkeypatch):
    _disable_relation_expansion(monkeypatch)
    monkeypatch.setattr(feed, "get_current_user_id", lambda: 99)
    monkeypatch.setattr(feed, "_get_post", lambda post_id: _post_payload())
    monkeypatch.setattr(feed, "_get_comment", lambda post_id, comment_id: _comment_payload())
    monkeypatch.setattr(
        feed,
        "_get_comment_replies",
        lambda post_id, comment_id, limit=5: {
            "items": [
                _comment_payload(301, parent_id=comment_id, content="first reply"),
                _comment_payload(302, parent_id=comment_id, content="second reply"),
            ],
            "total": 2,
        },
    )

    result = feed.expand_comments.invoke(
        {"post_id": 10, "comment_id": 201, "reply_count": 2}
    )

    assert result["data"]["comment"]["id"] == 201
    assert result["data"]["comment"]["post_id"] == 10
    assert [reply["id"] for reply in result["data"]["replies"]] == [301, 302]
    assert result["data"]["replies"][0]["parent_id"] == 201


def test_tool_execution_then_decision_prompt_exposes_reply_parent_ids(monkeypatch):
    _disable_relation_expansion(monkeypatch)
    monkeypatch.setattr(prompts, "_build_attention_header", lambda: "关注：0 粉丝：0 消息：0")
    monkeypatch.setattr(feed, "get_current_user_id", lambda: 99)
    monkeypatch.setattr(feed, "_get_post", lambda post_id: _post_payload())
    monkeypatch.setattr(feed, "_get_comment", lambda post_id, comment_id: _comment_payload())
    monkeypatch.setattr(
        feed,
        "_get_comment_replies",
        lambda post_id, comment_id, limit=5: {
            "items": [_comment_payload(301, parent_id=comment_id, content="reply target")],
            "total": 1,
        },
    )

    state = {
        "username": "agent",
        "step_count": 0,
        "max_steps": 10,
        "exit_reason": None,
        "action_history": [],
        "current_location": "帖子详情页",
        "last_tool_result": None,
        "pending_tool": {
            "tool_name": "expand_comments",
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

    assert "id / 评论ID: 201" in prompt
    assert "id / 评论ID: 301" in prompt
    assert "post_id / 所属帖子ID: 10" in prompt
    assert "parent_id / 父评论ID: 201" in prompt


def test_comment_tree_from_platform_api_keeps_nested_reply_ids(monkeypatch):
    _disable_relation_expansion(monkeypatch)
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

    standardized = utils._standardize_comment(platform_comment_tree, current_user_id=99)
    formatted = prompts._format_tool_result(
        {"post": utils._standardize_post(_post_payload(), 99), "comments": [standardized], "total": 3}
    )

    assert standardized["children"][0]["id"] == 301
    assert standardized["children"][0]["children"][0]["id"] == 401
    assert "id / 评论ID: 201" in formatted
    assert "id / 评论ID: 301" in formatted
    assert "id / 评论ID: 401" in formatted


def test_create_comment_with_parent_sends_parent_id_and_returns_new_comment_id(monkeypatch):
    _disable_relation_expansion(monkeypatch)
    monkeypatch.setattr(social, "get_current_user_id", lambda: 99)
    monkeypatch.setattr(social, "_get_post", lambda post_id: _post_payload())
    monkeypatch.setattr(
        social,
        "_get_comment",
        lambda post_id, comment_id: _comment_payload(comment_id, content="parent comment"),
    )

    mock_request = MagicMock(
        return_value=_comment_payload(501, parent_id=201, content="new reply")
    )
    monkeypatch.setattr(social, "_make_request", mock_request)

    result = social.create_comment.invoke(
        {
            "post_id": 10,
            "content": "new reply",
            "parent_id": 201,
            "reason": "回复评论",
            "summary": "我准备回复这条评论",
        }
    )

    mock_request.assert_called_once()
    assert mock_request.call_args.kwargs["endpoint"] == "/posts/10/comments"
    assert mock_request.call_args.kwargs["json_data"] == {
        "content": "new reply",
        "parent_id": 201,
    }
    assert result["data"]["parent_comment"]["id"] == 201
    assert result["data"]["new_comment"]["id"] == 501
    assert result["data"]["new_comment"]["parent_id"] == 201


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

    assert "【父评论】" in formatted
    assert "id / 评论ID: 201" in formatted
    assert "【新评论】" in formatted
    assert "id / 评论ID: 501" in formatted
    assert "parent_id / 父评论ID: 201" in formatted


def test_notification_prompt_marks_comment_id_as_create_comment_parent_id():
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

    assert "comment_id / 评论ID: 201" in formatted
    assert "reply_post_id / 回复这条评论时传给 create_comment.post_id: 10" in formatted
    assert "reply_parent_id / 回复这条评论时传给 create_comment.parent_id: 201" in formatted
