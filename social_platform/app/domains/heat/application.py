import logging
import math
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from social_platform.app.core.timezone import local_now
from social_platform.app.db.session import SessionLocal
from social_platform.app.domains.comment.models import Comment
from social_platform.app.domains.post.models import Post

logger = logging.getLogger(__name__)


def _age_hours(created_at: Optional[datetime], now: datetime) -> float:
    """计算对象创建至今的小时数，供热度衰减公式使用。"""
    if created_at is None:
        return 0.0
    return max((now - created_at).total_seconds() / 3600, 0)


def calculate_post_heat_score(post: Post, now: Optional[datetime] = None) -> float:
    """计算帖子热度分数，兼顾互动质量、新内容曝光与时间衰减。"""
    now = now or local_now()
    age_hours = _age_hours(post.created_at, now)
    # 平方根压缩互动滚雪球，避免早期高互动帖子长期垄断推荐候选池。
    weighted_interactions = (
        1 + (post.like_count or 0) * 1
        + (post.comment_count or 0) * 2
        + (post.repost_count or 0) * 4
    )
    quality_score = math.sqrt(weighted_interactions)
    # 六小时平滑窗口避免发布后分数断崖式下降，1.6 次幂让旧内容更快让位。
    time_decay = (age_hours + 6) ** 1.6
    return quality_score / time_decay


def calculate_comment_heat_score(comment: Comment, now: Optional[datetime] = None) -> float:
    """计算评论热度分数，综合点赞、回复和时间衰减。"""
    now = now or local_now()
    age_hours = _age_hours(comment.created_at, now)
    base_score = (comment.like_count or 0) * 1 + (comment.reply_count or 0) * 3
    time_decay = (age_hours + 2) ** 1.1
    fresh_boost = 1 + max(0, 12 - age_hours) / 12 * 0.3
    return (base_score + 1) / time_decay * fresh_boost


def refresh_post_heat_score(db: Session, post: Post, commit: bool = False) -> float:
    """刷新单条帖子热度；互动写操作中复用当前事务，因此默认不提交。"""
    now = local_now()
    post.heat_score = calculate_post_heat_score(post, now)
    post.heat_score_updated_at = now
    if commit:
        db.commit()
        db.refresh(post)
    return post.heat_score


def refresh_comment_heat_score(db: Session, comment: Comment, commit: bool = False) -> float:
    """刷新单条评论热度；互动写操作中复用当前事务，因此默认不提交。"""
    now = local_now()
    comment.heat_score = calculate_comment_heat_score(comment, now)
    comment.heat_score_updated_at = now
    if commit:
        db.commit()
        db.refresh(comment)
    return comment.heat_score


def refresh_all_heat_scores() -> None:
    """定时刷新全量热度，让时间衰减持续生效。"""
    db = SessionLocal()
    now = local_now()
    try:
        for post in db.query(Post).all():
            post.heat_score = calculate_post_heat_score(post, now)
            post.heat_score_updated_at = now

        for comment in db.query(Comment).all():
            comment.heat_score = calculate_comment_heat_score(comment, now)
            comment.heat_score_updated_at = now

        from social_platform.app.domains.topic import application as topic_application
        topic_application.refresh_all_topic_stats(db)
        db.commit()
        logger.info("热度分数刷新完成")
    except Exception:
        db.rollback()
        logger.exception("热度分数刷新失败")
    finally:
        db.close()
