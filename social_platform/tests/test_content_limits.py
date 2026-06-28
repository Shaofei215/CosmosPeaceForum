"""文章、帖子和评论正文长度约束测试。"""

import pytest
from pydantic import ValidationError

from social_platform.app.core.content_limits import (
    ARTICLE_CONTENT_MAX_LENGTH,
    COMMENT_CONTENT_MAX_LENGTH,
    POST_CONTENT_MAX_LENGTH,
)
from social_platform.app.domains.comment.schemas import CommentCreate, CommentUpdate
from social_platform.app.domains.post.schemas import PostCreate, PostUpdate, RepostCreate


def test_post_and_article_create_use_type_specific_limits() -> None:
    """普通帖子和文章应分别接受恰好达到各自上限的正文。"""

    assert len(PostCreate(content="帖" * POST_CONTENT_MAX_LENGTH).content) == 1_000
    article = PostCreate(
        type="article",
        title="测试文章",
        content="文" * ARTICLE_CONTENT_MAX_LENGTH,
    )
    assert len(article.content) == 10_000


@pytest.mark.parametrize(
    ("payload", "schema"),
    [
        ({"content": "帖" * (POST_CONTENT_MAX_LENGTH + 1)}, PostCreate),
        (
            {
                "type": "article",
                "title": "测试文章",
                "content": "文" * (ARTICLE_CONTENT_MAX_LENGTH + 1),
            },
            PostCreate,
        ),
        ({"content": "转" * (POST_CONTENT_MAX_LENGTH + 1), "source_type": "post", "source_id": 1}, RepostCreate),
    ],
)
def test_post_writes_reject_content_over_limit(
    payload: dict[str, object],
    schema: type[PostCreate] | type[RepostCreate],
) -> None:
    """帖子、文章和转发附言超过对应上限时应由 API schema 拒绝。"""

    with pytest.raises(ValidationError):
        schema(**payload)


def test_post_update_allows_article_limit_for_application_type_check() -> None:
    """更新 schema 应允许文章上限，普通帖子上限由应用层结合存量类型判断。"""

    assert len(PostUpdate(content="文" * ARTICLE_CONTENT_MAX_LENGTH).content or "") == 10_000


@pytest.mark.parametrize("schema", [CommentCreate, CommentUpdate])
def test_comment_writes_reject_content_over_limit(
    schema: type[CommentCreate] | type[CommentUpdate],
) -> None:
    """评论和回复超过统一上限时应由 API schema 拒绝。"""

    with pytest.raises(ValidationError):
        schema(content="评" * (COMMENT_CONTENT_MAX_LENGTH + 1))
