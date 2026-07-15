from agents.agents_scheduler.langgraph.tools.support import platform as utils


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
            "repost_source_type": "post",
            "repost_source_id": 12,
        },
        current_user_id=99,
    )

    assert standardized["author_username"] == "march7th"
    assert standardized["author_bio"] == "hi"
    assert standardized["is_liked"] is True
    assert "repost_source_type" not in standardized
    assert "repost_source_id" not in standardized
