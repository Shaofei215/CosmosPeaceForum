"""评论领域应用服务兼容入口。

第一阶段保留旧 ``comment_service`` 的函数实现，先把事件解耦和目录边界建立起来。
"""

from __future__ import annotations

from social_platform.app.services.comment_service import (  # noqa: F401
    CommentNotFoundError,
    ParentCommentMismatchError,
    ParentCommentNotFoundError,
    PostNotFoundError,
    create_comment,
    delete_comment,
    delete_comment_precise,
    get_comment_by_id,
    get_comment_replies,
    get_comment_tree,
    get_like_status,
    toggle_like,
)
