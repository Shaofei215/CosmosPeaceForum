import logging
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from app_platform.app.db.session import SessionLocal
from app_platform.app.models.comment import Comment
from app_platform.app.models.post import Post

logger = logging.getLogger(__name__)


def _age_hours(created_at: Optional[datetime], now: datetime) -> float:
    if created_at is None:
        return 0.0
    return max((now - created_at).total_seconds() / 3600, 0)


def calculate_post_heat_score(post: Post, now: Optional[datetime] = None) -> float:
    now = now or datetime.utcnow()
    age_hours = _age_hours(post.created_at, now)
    # 帖子热度只保存可解释的稳定质量分；请求层再做 Top-N 候选重排。
    base_score = (
        (post.like_count or 0) * 1
        + (post.comment_count or 0) * 3
        + (post.repost_count or 0) * 5
    )
    time_decay = (age_hours + 2) ** 1.3
    fresh_boost = 1 + max(0, 24 - age_hours) / 24 * 0.5
    return (base_score + 1) / time_decay * fresh_boost


def calculate_comment_heat_score(comment: Comment, now: Optional[datetime] = None) -> float:
    now = now or datetime.utcnow()
    age_hours = _age_hours(comment.created_at, now)
    base_score = (comment.like_count or 0) * 1
    time_decay = (age_hours + 2) ** 1.1
    fresh_boost = 1 + max(0, 12 - age_hours) / 12 * 0.3
    return (base_score + 1) / time_decay * fresh_boost


def refresh_post_heat_score(db: Session, post: Post, commit: bool = False) -> float:
    """刷新单条帖子热度；互动写操作中复用当前事务，因此默认不提交。"""
    now = datetime.utcnow()
    post.heat_score = calculate_post_heat_score(post, now)
    post.heat_score_updated_at = now
    if commit:
        db.commit()
        db.refresh(post)
    return post.heat_score


def refresh_comment_heat_score(db: Session, comment: Comment, commit: bool = False) -> float:
    """刷新单条评论热度；互动写操作中复用当前事务，因此默认不提交。"""
    now = datetime.utcnow()
    comment.heat_score = calculate_comment_heat_score(comment, now)
    comment.heat_score_updated_at = now
    if commit:
        db.commit()
        db.refresh(comment)
    return comment.heat_score


def refresh_all_heat_scores() -> None:
    """定时刷新全量热度，让时间衰减持续生效。"""
    db = SessionLocal()
    now = datetime.utcnow()
    try:
        for post in db.query(Post).all():
            post.heat_score = calculate_post_heat_score(post, now)
            post.heat_score_updated_at = now

        for comment in db.query(Comment).all():
            comment.heat_score = calculate_comment_heat_score(comment, now)
            comment.heat_score_updated_at = now

        db.commit()
        logger.info("热度分数刷新完成")
    except Exception:
        db.rollback()
        logger.exception("热度分数刷新失败")
    finally:
        db.close()
