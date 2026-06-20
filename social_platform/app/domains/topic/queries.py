"""帖子话题领域读侧查询。

本模块提供帖子响应需要的话题元数据批量组装能力，避免 feed 和详情页重复查询。
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from social_platform.app.domains.topic.models import PostTopic, Topic


TopicMentionData = dict[str, object]


def build_topic_mentions_for_post_ids(
    db: Session,
    post_ids: list[int],
) -> dict[int, list[TopicMentionData]]:
    """按帖子 ID 批量构建话题元数据。

    Args:
        db: 当前数据库会话。
        post_ids: 帖子 ID 列表。

    Returns:
        dict[int, list[TopicMentionData]]: 帖子 ID 到话题元数据列表的映射。
    """

    unique_post_ids = list(dict.fromkeys(post_ids))
    mentions_by_post = {post_id: [] for post_id in unique_post_ids}
    if not unique_post_ids:
        return mentions_by_post

    rows = (
        db.query(PostTopic.post_id, Topic.id, Topic.name, PostTopic.created_at)
        .join(Topic, Topic.id == PostTopic.topic_id)
        .filter(PostTopic.post_id.in_(unique_post_ids))
        .order_by(PostTopic.post_id.asc(), PostTopic.created_at.asc(), PostTopic.id.asc())
        .all()
    )
    for post_id, topic_id, name, _ in rows:
        mentions_by_post.setdefault(post_id, []).append({"id": topic_id, "name": name})
    return mentions_by_post


def build_topic_mentions(db: Session, post_id: int) -> list[TopicMentionData]:
    """为单个帖子构建话题元数据。

    Args:
        db: 当前数据库会话。
        post_id: 帖子 ID。

    Returns:
        list[TopicMentionData]: 话题元数据列表。
    """

    return build_topic_mentions_for_post_ids(db, [post_id]).get(post_id, [])

