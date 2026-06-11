"""互动反应领域应用服务兼容入口。"""

from __future__ import annotations

from sqlalchemy.orm import Session

from social_platform.app.services import comment_service, like_service


def toggle_post_like(post_id: int, user_id: int, db: Session) -> tuple[bool, int]:
    """切换帖子点赞状态。

    Args:
        post_id: 帖子 ID。
        user_id: 操作者用户 ID。
        db: 当前数据库会话。

    Returns:
        tuple[bool, int]: 当前是否已点赞与最新点赞数。
    """

    return like_service.toggle_like(post_id=post_id, user_id=user_id, db=db)


def toggle_comment_like(comment_id: int, user_id: int, db: Session) -> tuple[bool, int]:
    """切换评论点赞状态。

    Args:
        comment_id: 评论 ID。
        user_id: 操作者用户 ID。
        db: 当前数据库会话。

    Returns:
        tuple[bool, int]: 当前是否已点赞与最新点赞数。
    """

    return comment_service.toggle_like(comment_id=comment_id, user_id=user_id, db=db)
