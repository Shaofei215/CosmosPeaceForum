"""帖子话题领域应用服务。

本模块负责 ``#话题#`` 解析、帖子话题关联维护和话题热度刷新。写侧由领域事件
订阅器调用，公开 API 只读取这里维护的投影。
"""

from __future__ import annotations

import math
import re
from datetime import datetime
from typing import Iterable

from sqlalchemy import func
from sqlalchemy.orm import Session

from social_platform.app.domains.post.models import Post
from social_platform.app.domains.topic.models import PostTopic, Topic


TOPIC_NAME_MAX_LENGTH = 40
TOPIC_PATTERN = re.compile(r"#([a-zA-Z0-9_\-\u4e00-\u9fa5]{1,40})#")


def extract_topic_names(content: str | None) -> list[str]:
    """从正文中提取去重后的规范话题名。

    Args:
        content: 帖子正文，可为空。

    Returns:
        list[str]: 按首次出现顺序去重的话题名，不包含两侧 ``#``。
    """

    names: list[str] = []
    seen: set[str] = set()
    for match in TOPIC_PATTERN.finditer(content or ""):
        name = match.group(1).strip()
        if not name or name in seen:
            continue
        names.append(name)
        seen.add(name)
    return names


def _now() -> datetime:
    """返回当前 UTC 时间。"""

    return datetime.utcnow()


def _get_or_create_topics(db: Session, names: list[str]) -> dict[str, Topic]:
    """按名称批量读取或创建话题。

    Args:
        db: 当前数据库会话。
        names: 需要确保存在的话题名。

    Returns:
        dict[str, Topic]: 话题名到 ORM 对象的映射。
    """

    if not names:
        return {}

    existing = db.query(Topic).filter(Topic.name.in_(names)).all()
    topic_by_name = {topic.name: topic for topic in existing}
    for name in names:
        if name in topic_by_name:
            continue
        topic = Topic(name=name, created_at=_now(), updated_at=_now())
        db.add(topic)
        db.flush()
        topic_by_name[name] = topic
    return topic_by_name


def _calculate_topic_heat(post_count: int, post_heat_sum: float, last_used_at: datetime | None) -> float:
    """计算话题热度分数。

    Args:
        post_count: 使用该话题的 active 帖子数量。
        post_heat_sum: 使用该话题的 active 帖子热度总和。
        last_used_at: 最近一次使用时间。

    Returns:
        float: 可排序的话题热度分数。
    """

    if post_count <= 0:
        return 0.0

    if last_used_at is None:
        freshness = 0.0
    else:
        age_hours = max((_now() - last_used_at).total_seconds() / 3600, 0)
        freshness = 6 / math.sqrt(age_hours + 2)

    return math.log1p(post_count) * 8 + math.log1p(max(post_heat_sum, 0.0)) * 20 + freshness


def refresh_topic_stats(db: Session, topic_ids: Iterable[int]) -> None:
    """刷新指定话题的帖子数量、热度和最近使用时间。

    Args:
        db: 当前数据库会话。
        topic_ids: 待刷新的话题 ID 集合。
    """

    unique_topic_ids = list(dict.fromkeys(topic_id for topic_id in topic_ids if topic_id))
    if not unique_topic_ids:
        return

    topics = db.query(Topic).filter(Topic.id.in_(unique_topic_ids)).all()
    for topic in topics:
        row = (
            db.query(
                func.count(Post.id),
                func.coalesce(func.sum(Post.heat_score), 0.0),
                func.max(Post.created_at),
            )
            .join(PostTopic, PostTopic.post_id == Post.id)
            .filter(PostTopic.topic_id == topic.id, Post.moderation_status == "active")
            .one()
        )
        post_count = int(row[0] or 0)
        post_heat_sum = float(row[1] or 0.0)
        last_used_at = row[2]
        topic.post_count = post_count
        topic.heat_score = _calculate_topic_heat(post_count, post_heat_sum, last_used_at)
        topic.last_used_at = last_used_at
        topic.updated_at = _now()


def refresh_all_topic_stats(db: Session) -> None:
    """刷新所有话题统计，供定时热度任务调用。"""

    topic_ids = [topic_id for (topic_id,) in db.query(Topic.id).all()]
    refresh_topic_stats(db, topic_ids)


def ensure_topic_projection(db: Session) -> None:
    """确保话题投影存在，供应用启动时兼容历史帖子。

    Args:
        db: 当前数据库会话。

    Raises:
        数据库异常会透传给调用方，由启动流程统一处理。
    """

    existing_association_count = db.query(func.count(PostTopic.id)).scalar() or 0
    if existing_association_count > 0:
        return

    posts = db.query(Post).filter(Post.moderation_status == "active").all()
    for post in posts:
        if extract_topic_names(post.content):
            sync_post_topics(db, post.id, post.content)
    db.commit()


def refresh_topics_for_post(db: Session, post_id: int | None) -> None:
    """刷新某个帖子关联的话题统计。

    Args:
        db: 当前数据库会话。
        post_id: 发生互动变化的帖子 ID。
    """

    if post_id is None:
        return
    topic_ids = [
        topic_id
        for (topic_id,) in db.query(PostTopic.topic_id).filter(PostTopic.post_id == post_id).all()
    ]
    refresh_topic_stats(db, topic_ids)


def sync_post_topics(db: Session, post_id: int, content: str | None) -> None:
    """同步单个帖子的正文话题关联。

    Args:
        db: 当前数据库会话。
        post_id: 待同步的帖子 ID。
        content: 最新帖子正文。
    """

    names = extract_topic_names(content)
    old_topic_ids = [
        topic_id
        for (topic_id,) in db.query(PostTopic.topic_id).filter(PostTopic.post_id == post_id).all()
    ]
    db.query(PostTopic).filter(PostTopic.post_id == post_id).delete(synchronize_session=False)

    topic_by_name = _get_or_create_topics(db, names)
    new_topic_ids: list[int] = []
    for name in names:
        topic = topic_by_name[name]
        db.add(PostTopic(post_id=post_id, topic_id=topic.id, created_at=_now()))
        new_topic_ids.append(topic.id)

    db.flush()
    refresh_topic_stats(db, [*old_topic_ids, *new_topic_ids])


def remove_post_topics(db: Session, post_id: int) -> None:
    """删除帖子的话题关联并刷新受影响话题。

    Args:
        db: 当前数据库会话。
        post_id: 被删除或归档的帖子 ID。
    """

    topic_ids = [
        topic_id
        for (topic_id,) in db.query(PostTopic.topic_id).filter(PostTopic.post_id == post_id).all()
    ]
    if not topic_ids:
        return
    db.query(PostTopic).filter(PostTopic.post_id == post_id).delete(synchronize_session=False)
    db.flush()
    refresh_topic_stats(db, topic_ids)


def list_trending_topics(db: Session, limit: int = 12) -> list[Topic]:
    """读取热门话题候选列表。

    Args:
        db: 当前数据库会话。
        limit: 最大返回数量。

    Returns:
        list[Topic]: 按热度降序排列的话题列表。
    """

    safe_limit = max(1, min(int(limit), 50))
    return (
        db.query(Topic)
        .filter(Topic.post_count > 0)
        .order_by(Topic.heat_score.desc(), Topic.last_used_at.desc(), Topic.id.desc())
        .limit(safe_limit)
        .all()
    )


def normalize_topic_query(value: str | None) -> str:
    """规范化话题搜索词。

    Args:
        value: 用户输入的话题名，允许带 ``#`` 或 ``#话题#``。

    Returns:
        str: 去掉边界符后的话题名。
    """

    query = (value or "").strip()
    if query.startswith("#") and query.endswith("#") and len(query) >= 2:
        query = query[1:-1]
    elif query.startswith("#"):
        query = query[1:]
    return query.strip()[:TOPIC_NAME_MAX_LENGTH]
