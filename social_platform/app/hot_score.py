"""
帖子热度计算模块
提供热度计算、衰减和更新功能

热度公式: score = (点赞数*1 + 评论数*2) * 时间衰减系数
评论热度公式: score = 点赞数*1 * 时间衰减系数
"""
import math
import random
from datetime import datetime, timedelta
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import desc

from . import models


# 热度计算配置
HOT_SCORE_CONFIG = {
    "like_weight": 1,      # 点赞权重
    "comment_weight": 2,   # 评论权重
    "decay_half_life": 24, # 半衰期（小时）- 24小时后热度减半
    "freshness_bonus": 50, # 新鲜度加成（24小时内的新帖子）
    "freshness_window": 24, # 新鲜度窗口（小时）
    "comment_decay_half_life": 12, # 评论半衰期（小时）- 评论热度衰减更快
}


def calculate_hot_score(likes_count: int, comments_count: int, 
                        created_at: datetime, last_update: Optional[datetime] = None) -> int:
    """
    计算帖子热度分数
    
    Args:
        likes_count: 点赞数
        comments_count: 评论数
        created_at: 帖子创建时间
        last_update: 上次热度更新时间（可选）
        
    Returns:
        int: 热度分数
    """
    # 基础分数 = 点赞*1 + 评论*2
    base_score = likes_count * HOT_SCORE_CONFIG["like_weight"] + \
                 comments_count * HOT_SCORE_CONFIG["comment_weight"]
    
    # 计算时间衰减
    now = datetime.utcnow()
    
    # 使用上次更新时间或创建时间作为参考
    reference_time = last_update if last_update else created_at
    
    # 计算经过的时间（小时）
    hours_passed = (now - reference_time).total_seconds() / 3600
    
    # 指数衰减: decay = 0.5^(t/half_life)
    # 这样半衰期后热度减半
    half_life = HOT_SCORE_CONFIG["decay_half_life"]
    decay_factor = math.pow(0.5, hours_passed / half_life)
    
    # 应用衰减
    decayed_score = base_score * decay_factor
    
    # 新鲜度保护：24小时内的新帖子获得加成
    hours_since_created = (now - created_at).total_seconds() / 3600
    freshness_window = HOT_SCORE_CONFIG["freshness_window"]
    
    if hours_since_created < freshness_window:
        # 新鲜度加成随时间线性减少
        freshness_factor = 1 - (hours_since_created / freshness_window)
        freshness_bonus = HOT_SCORE_CONFIG["freshness_bonus"] * freshness_factor
        decayed_score += freshness_bonus
    
    # 确保最小值为0
    final_score = max(0, int(decayed_score))
    
    return final_score


def calculate_comment_hot_score(likes_count: int, created_at: datetime,
                                last_update: Optional[datetime] = None) -> int:
    """
    计算评论热度分数
    
    评论热度 = 点赞数 * 时间衰减系数
    评论半衰期更短（12小时），衰减更快
    
    Args:
        likes_count: 点赞数
        created_at: 评论创建时间
        last_update: 上次热度更新时间（可选）
        
    Returns:
        int: 热度分数
    """
    # 基础分数 = 点赞*1
    base_score = likes_count * HOT_SCORE_CONFIG["like_weight"]
    
    # 计算时间衰减
    now = datetime.utcnow()
    
    # 使用上次更新时间或创建时间作为参考
    reference_time = last_update if last_update else created_at
    
    # 计算经过的时间（小时）
    hours_passed = (now - reference_time).total_seconds() / 3600
    
    # 评论使用更短的半衰期（12小时）
    half_life = HOT_SCORE_CONFIG["comment_decay_half_life"]
    decay_factor = math.pow(0.5, hours_passed / half_life)
    
    # 应用衰减
    decayed_score = base_score * decay_factor
    
    # 确保最小值为0
    final_score = max(0, int(decayed_score))
    
    return final_score


def update_post_hot_score(db: Session, post_id: int) -> int:
    """
    更新单个帖子的热度分数
    
    Args:
        db: 数据库会话
        post_id: 帖子ID
        
    Returns:
        int: 更新后的热度分数
    """
    post = db.query(models.Post).filter(models.Post.id == post_id).first()
    if not post:
        return 0
    
    # 获取点赞数和评论数
    likes_count = db.query(models.Like).filter(models.Like.post_id == post_id).count()
    comments_count = db.query(models.Comment).filter(models.Comment.post_id == post_id).count()
    
    # 计算新热度
    new_score = calculate_hot_score(
        likes_count=likes_count,
        comments_count=comments_count,
        created_at=post.created_at,
        last_update=post.last_hot_update
    )
    
    # 更新帖子
    post.hot_score = new_score
    post.last_hot_update = datetime.utcnow()
    
    db.commit()
    db.refresh(post)
    
    return new_score


def update_comment_hot_score(db: Session, comment_id: int) -> int:
    """
    更新单个评论的热度分数
    
    Args:
        db: 数据库会话
        comment_id: 评论ID
        
    Returns:
        int: 更新后的热度分数
    """
    comment = db.query(models.Comment).filter(models.Comment.id == comment_id).first()
    if not comment:
        return 0
    
    # TODO: 评论点赞功能实现后，这里需要查询评论的点赞数
    # 目前评论没有独立的点赞系统，暂时使用0
    likes_count = 0
    
    # 计算新热度
    new_score = calculate_comment_hot_score(
        likes_count=likes_count,
        created_at=comment.created_at,
        last_update=comment.last_hot_update
    )
    
    # 更新评论
    comment.hot_score = new_score
    comment.last_hot_update = datetime.utcnow()
    
    db.commit()
    db.refresh(comment)
    
    return new_score


def update_all_hot_scores(db: Session) -> int:
    """
    更新所有帖子的热度分数
    
    Args:
        db: 数据库会话
        
    Returns:
        int: 更新的帖子数量
    """
    posts = db.query(models.Post).all()
    updated_count = 0
    
    for post in posts:
        update_post_hot_score(db, post.id)
        updated_count += 1
    
    return updated_count


def get_hot_posts(db: Session, limit: int = 50, offset: int = 0) -> list:
    """
    获取热门帖子列表（按热度排序）
    
    Args:
        db: 数据库会话
        limit: 返回数量
        offset: 偏移量
        
    Returns:
        list: 帖子列表
    """
    # 先更新所有热度
    update_all_hot_scores(db)
    
    # 按热度排序返回
    return db.query(models.Post) \
             .order_by(desc(models.Post.hot_score)) \
             .offset(offset) \
             .limit(limit) \
             .all()


def get_mixed_posts(db: Session, hot_ratio: float = 0.7, 
                    total_limit: int = 50) -> list:
    """
    获取混合帖子（热门+最新）
    
    Args:
        db: 数据库会话
        hot_ratio: 热门帖子比例（默认70%）
        total_limit: 总数量
        
    Returns:
        list: 混合帖子列表
    """
    # 先更新所有热度
    update_all_hot_scores(db)
    
    hot_count = int(total_limit * hot_ratio)
    fresh_count = total_limit - hot_count
    
    # 获取热门帖子
    hot_posts = db.query(models.Post) \
                  .order_by(desc(models.Post.hot_score)) \
                  .limit(hot_count * 2) \
                  .all()
    
    # 获取最新帖子（24小时内）
    freshness_window = timedelta(hours=HOT_SCORE_CONFIG["freshness_window"])
    fresh_cutoff = datetime.utcnow() - freshness_window
    
    fresh_posts = db.query(models.Post) \
                    .filter(models.Post.created_at >= fresh_cutoff) \
                    .order_by(desc(models.Post.created_at)) \
                    .limit(fresh_count * 2) \
                    .all()
    
    # 随机选择
    selected_hot = random.sample(hot_posts, min(hot_count, len(hot_posts))) if hot_posts else []
    selected_fresh = random.sample(fresh_posts, min(fresh_count, len(fresh_posts))) if fresh_posts else []
    
    # 合并并随机打乱顺序
    mixed_posts = selected_hot + selected_fresh
    random.shuffle(mixed_posts)
    
    # 如果数量不足，用其他帖子补充
    if len(mixed_posts) < total_limit:
        existing_ids = {p.id for p in mixed_posts}
        additional = db.query(models.Post) \
                       .filter(~models.Post.id.in_(existing_ids)) \
                       .order_by(desc(models.Post.created_at)) \
                       .limit(total_limit - len(mixed_posts)) \
                       .all()
        mixed_posts.extend(additional)
    
    return mixed_posts[:total_limit]


def get_mixed_comments(db: Session, post_id: int, hot_ratio: float = 0.7,
                       total_limit: int = 50) -> list:
    """
    获取帖子的混合评论（热门+最新）
    
    Args:
        db: 数据库会话
        post_id: 帖子ID
        hot_ratio: 热门评论比例（默认70%）
        total_limit: 总数量
        
    Returns:
        list: 混合评论列表
    """
    # 更新该帖子所有评论的热度
    comments = db.query(models.Comment).filter(models.Comment.post_id == post_id).all()
    for comment in comments:
        update_comment_hot_score(db, comment.id)
    
    hot_count = int(total_limit * hot_ratio)
    fresh_count = total_limit - hot_count
    
    # 获取热门评论
    hot_comments = db.query(models.Comment) \
                     .filter(models.Comment.post_id == post_id) \
                     .order_by(desc(models.Comment.hot_score)) \
                     .limit(hot_count * 2) \
                     .all()
    
    # 获取最新评论（12小时内）
    freshness_window = timedelta(hours=HOT_SCORE_CONFIG["comment_decay_half_life"])
    fresh_cutoff = datetime.utcnow() - freshness_window
    
    fresh_comments = db.query(models.Comment) \
                       .filter(models.Comment.post_id == post_id) \
                       .filter(models.Comment.created_at >= fresh_cutoff) \
                       .order_by(desc(models.Comment.created_at)) \
                       .limit(fresh_count * 2) \
                       .all()
    
    # 随机选择
    selected_hot = random.sample(hot_comments, min(hot_count, len(hot_comments))) if hot_comments else []
    selected_fresh = random.sample(fresh_comments, min(fresh_count, len(fresh_comments))) if fresh_comments else []
    
    # 合并并随机打乱顺序
    mixed_comments = selected_hot + selected_fresh
    random.shuffle(mixed_comments)
    
    # 如果数量不足，用其他评论补充
    if len(mixed_comments) < total_limit:
        existing_ids = {c.id for c in mixed_comments}
        additional = db.query(models.Comment) \
                       .filter(models.Comment.post_id == post_id) \
                       .filter(~models.Comment.id.in_(existing_ids)) \
                       .order_by(desc(models.Comment.created_at)) \
                       .limit(total_limit - len(mixed_comments)) \
                       .all()
        mixed_comments.extend(additional)
    
    return mixed_comments[:total_limit]


def get_comments_by_interest(db: Session, post_id: int, interest_score: float,
                             max_comments: int = 7) -> list:
    """
    根据兴趣系数获取评论
    
    阅读评论数 = floor(兴趣系数 × max_comments)
    例如：兴趣系数0.6，max_comments=7 → 阅读4条评论
    
    Args:
        db: 数据库会话
        post_id: 帖子ID
        interest_score: 兴趣系数（0-1）
        max_comments: 最大评论数（默认7）
        
    Returns:
        list: 评论列表
    """
    # 计算需要阅读多少条评论
    comments_to_read = int(interest_score * max_comments)
    
    if comments_to_read <= 0:
        return []
    
    # 获取混合排序的评论
    mixed_comments = get_mixed_comments(db, post_id, hot_ratio=0.7, total_limit=comments_to_read * 2)
    
    # 返回前 N 条
    return mixed_comments[:comments_to_read]


# 简单的热度趋势计算
def get_trending_posts(db: Session, hours: int = 24, limit: int = 10) -> list:
    """
    获取趋势帖子（最近热度上升最快的）
    
    Args:
        db: 数据库会话
        hours: 时间窗口（小时）
        limit: 返回数量
        
    Returns:
        list: 帖子列表
    """
    cutoff_time = datetime.utcnow() - timedelta(hours=hours)
    
    # 获取最近有互动的帖子
    recent_likes = db.query(models.Like.post_id) \
                     .filter(models.Like.created_at >= cutoff_time) \
                     .distinct()
    
    recent_comments = db.query(models.Comment.post_id) \
                        .filter(models.Comment.created_at >= cutoff_time) \
                        .distinct()
    
    # 合并并获取帖子
    trending = db.query(models.Post) \
                 .filter(models.Post.id.in_(recent_likes.union(recent_comments))) \
                 .order_by(desc(models.Post.hot_score)) \
                 .limit(limit) \
                 .all()
    
    return trending
