from agents.agents_scheduler.langgraph.prompts import _format_comment_fields, _format_post_fields
from agents.agents_scheduler.langgraph.tools import utils


def test_standardize_post_reads_nested_author_and_like_status(monkeypatch):
    monkeypatch.setattr(utils, "_expand_username_by_relation", lambda username, user_id, owner_id: username)
    monkeypatch.setattr(utils, "_expand_content_mentions_by_relation", lambda content, owner_id: content)
    monkeypatch.setattr(utils, "_get_follow_status_text", lambda user_id, current_user_id: "")

    standardized = utils._standardize_post(
        {
            "id": 42,
            "author_id": 7,
            "author": {"username": "march7th", "bio": "hi"},
            "content": "hello",
            "like_count": 3,
            "comment_count": 1,
            "is_liked_by_current_user": True,
        },
        current_user_id=99,
    )

    assert standardized["author_username"] == "march7th"
    assert standardized["author_bio"] == "hi"
    assert standardized["is_liked"] is True


def test_prompt_formatters_fall_back_for_empty_username():
    post_lines = _format_post_fields({"author_username": ""})
    comment_lines = _format_comment_fields({"author_username": ""})

    assert "author_username / 作者用户名: @?" in post_lines
    assert "author_username / 评论者用户名: @?" in comment_lines
