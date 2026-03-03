"""
热度计算模块
提供帖子、评论、回复的热度计算、衰减和更新功能

热度公式:
- 帖子: score = (点赞数*1 + 评论数*2) * 时间衰减系数 + 新鲜度加成
- 评论: score = (点赞数*1 + 回复数*2) * 时间衰减系数
- 回复: score = (点赞数*1 + 子回复数*2) * 时间衰减系数
"""
import math
import random
from datetime import datetime, timedelta
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import desc, func

from . import models


# 热度计算配置
HOT_SCORE_CONFIG = {
    "like_weight": 1,      # 点赞权重
    "comment_weight": 2,   # 评论/回复权重
    "decay_half_life": 24, # 帖子半衰期（小时）
    "freshness_bonus": 50, # 新鲜度加成
    "freshness_window": 24, # 新鲜度窗口（小时）
    "comment_decay_half_life": 12, # 评论半衰期（小时）
    "reply_decay_half_life": 8,    # 回复半衰期（小时）- 回复衰减更快
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
    reference_time = last_update if last_update else created_at
    hours_passed = (now - reference_time).total_seconds() / 3600
    
    # 指数衰减
    half_life = HOT_SCORE_CONFIG["decay_half_life"]
    decay_factor = math.pow(0.5, hours_passed / half_life)
    
    # 应用衰减
    decayed_score = base_score * decay_factor
    
    # 新鲜度保护
    hours_since_created = (now - created_at).total_seconds() / 3600
    freshness_window = HOT_SCORE_CONFIG["freshness_window"]
    
    if hours_since_created < freshness_window:
        freshness_factor = 1 - (hours_since_created / freshness_window)
        freshness_bonus = HOT_SCORE_CONFIG["freshness_bonus"] * freshness_factor
        decayed_score += freshness_bonus
    
    return max(0, int(decayed_score))


def calculate_comment_hot_score(likes_count: int, replies_count: int,
                                created_at: datetime, last_update: Optional[datetime] = None) -> int:
    """
    计算评论热度分数
    
    评论热度 = (点赞数*1 + 回复数*2) * 时间衰减系数
    
    Args:
        likes_count: 点赞数
        replies_count: 回复数
        created_at: 评论创建时间
        last_update: 上次热度更新时间（可选）
        
    Returns:
        int: 热度分数
    """
    # 基础分数 = 点赞*1 + 回复*2
    base_score = likes_count * HOT_SCORE_CONFIG["like_weight"] + \
                 replies_count * HOT_SCORE_CONFIG["comment_weight"]
    
    # 计算时间衰减
    now = datetime.utcnow()
    reference_time = last_update if last_update else created_at
    hours_passed = (now - reference_time).total_seconds() / 3600
    
    # 评论使用更短的半衰期
    half_life = HOT_SCORE_CONFIG["comment_decay_half_life"]
    decay_factor = math.pow(0.5, hours_passed / half_life)
    
    decayed_score = base_score * decay_factor
    return max(0, int(decayed_score))


def calculate_reply_hot_score(likes_count: int, child_replies_count: int,
                              created_at: datetime, last_update: Optional[datetime] = None) -> int:
    """
    计算回复热度分数
    
    回复热度 = (点赞数*1 + 子回复数*2) * 时间衰减系数
    
    Args:
        likes_count: 点赞数
        child_replies_count: 子回复数
        created_at: 回复创建时间
        last_update: 上次热度更新时间（可选）
        
    Returns:
        int: 热度分数
    """
    # 基础分数 = 点赞*1 + 子回复*2
    base_score = likes_count * HOT_SCORE_CONFIG["like_weight"] + \
                 child_replies_count * HOT_SCORE_CONFIG["comment_weight"]
    
    # 计算时间衰减
    now = datetime.utcnow()
    reference_time = last_update if last_update else created_at
    hours_passed = (now - reference_time).total_seconds() / 3600
    
    # 回复使用最短的半衰期
    half_life = HOT_SCORE_CONFIG["reply_decay_half_life"]
    decay_factor = math.pow(0.5, hours_passed / half_life)
    
    decayed_score = base_score * decay_factor
    return max(0, int(decayed_score))


def update_post_hot_score(db: Session, post_id: int) -> int:
    """更新单个帖子的热度分数"""
    post = db.query(models.Post).filter(models.Post.id == post_id).first()
    if not post:
        return 0
    
    likes_count = db.query(models.Like).filter(models.Like.post_id == post_id).count()
    comments_count = db.query(models.Comment).filter(models.Comment.post_id == post_id).count()
    
    new_score = calculate_hot_score(
        likes_count=likes_count,
        comments_count=comments_count,
        created_at=post.created_at,
        last_update=post.last_hot_update
    )
    
    post.hot_score = new_score
    post.last_hot_update = datetime.utcnow()
    
    db.commit()
    db.refresh(post)
    
    return new_score


def update_comment_hot_score(db: Session, comment_id: int) -> int:
    """更新单个评论的热度分数"""
    comment = db.query(models.Comment).filter(models.Comment.id == comment_id).first()
    if not comment:
        return 0
    
    # 获取点赞数和回复数
    likes_count = db.query(models.Like).filter(models.Like.comment_id == comment_id).count()
    replies_count = db.query(models.Reply).filter(models.Reply.comment_id == comment_id).count()
    
    new_score = calculate_comment_hot_score(
        likes_count=likes_count,
        replies_count=replies_count,
        created_at=comment.created_at,
        last_update=comment.last_hot_update
    )
    
    comment.hot_score = new_score
    comment.last_hot_update = datetime.utcnow()
    
    db.commit()
    db.refresh(comment)
    
    return new_score


def update_reply_hot_score(db: Session, reply_id: int) -> int:
    """更新单个回复的热度分数"""
    reply = db.query(models.Reply).filter(models.Reply.id == reply_id).first()
    if not reply:
        return 0
    
    # 获取点赞数和子回复数
    likes_count = db.query(models.Like).filter(models.Like.reply_id == reply_id).count()
    child_replies_count = db.query(models.Reply).filter(models.Reply.parent_reply_id == reply_id).count()
    
    new_score = calculate_reply_hot_score(
        likes_count=likes_count,
        child_replies_count=child_replies_count,
        created_at=reply.created_at,
        last_update=reply.last_hot_update
    )
    
    reply.hot_score = new_score
    reply.last_hot_update = datetime.utcnow()
    
    db.commit()
    db.refresh(reply)
    
    return new_score


def update_all_hot_scores(db: Session) -> int:
    """更新所有帖子的热度分数"""
    posts = db.query(models.Post).all()
    updated_count = 0
    
    for post in posts:
        update_post_hot_score(db, post.id)
        updated_count += 1
    
    return updated_count


def get_hot_posts(db: Session, limit: int = 50, offset: int = 0) -> list:
    """获取热门帖子列表（按热度排序）"""
    update_all_hot_scores(db)
    
    return db.query(models.Post) \
             .order_by(desc(models.Post.hot_score)) \
             .offset(offset) \
             .limit(limit) \
             .all()


def get_mixed_posts(db: Session, user_id: Optional[int] = None,
                    hot_ratio: float = 0.4, fresh_ratio: float = 0.3, 
                    random_ratio: float = 0.3, total_limit: int = 50) -> list:
    """
    获取三层混合帖子（40%热门 + 30%最新 + 30%随机），支持按用户过滤已读
    
    Args:
        db: 数据库会话
        user_id: 用户ID（可选），如果提供则排除该用户已读的帖子
        hot_ratio: 热门帖子比例（默认40%）
        fresh_ratio: 最新帖子比例（默认30%）
        random_ratio: 随机帖子比例（默认30%）
        total_limit: 返回帖子总数
        
    Returns:
        混合排序的帖子列表
    """
    from app import crud
    
    update_all_hot_scores(db)

    # 计算各类帖子数量
    hot_count = int(total_limit * hot_ratio)
    fresh_count = int(total_limit * fresh_ratio)
    random_count = total_limit - hot_count - fresh_count  # 剩余为随机

    # 获取用户的已读帖子ID（如果提供了user_id）
    read_post_ids = set()
    if user_id:
        read_post_ids = set(crud.get_user_read_post_ids(db, user_id))
        if read_post_ids:
            print(f"[推荐算法] 用户 {user_id} 已读 {len(read_post_ids)} 条帖子，将过滤")

    # 获取热门帖子
    hot_posts_query = db.query(models.Post).order_by(desc(models.Post.hot_score))
    if read_post_ids:
        hot_posts_query = hot_posts_query.filter(~models.Post.id.in_(read_post_ids))
    hot_posts = hot_posts_query.limit(hot_count * 3).all()

    # 获取最新帖子
    freshness_window = timedelta(hours=HOT_SCORE_CONFIG["freshness_window"])
    fresh_cutoff = datetime.utcnow() - freshness_window

    fresh_posts_query = db.query(models.Post) \
                          .filter(models.Post.created_at >= fresh_cutoff) \
                          .order_by(desc(models.Post.created_at))
    if read_post_ids:
        fresh_posts_query = fresh_posts_query.filter(~models.Post.id.in_(read_post_ids))
    fresh_posts = fresh_posts_query.limit(fresh_count * 3).all()

    # 获取随机帖子（排除已读）
    random_posts_query = db.query(models.Post).order_by(func.random())
    if read_post_ids:
        random_posts_query = random_posts_query.filter(~models.Post.id.in_(read_post_ids))
    random_posts = random_posts_query.limit(random_count * 3).all()

    # 使用集合追踪已选择的帖子ID，确保完全不重复
    selected_ids = set()
    mixed_posts = []

    # 1. 先从热门帖子中选择
    random.shuffle(hot_posts)
    for post in hot_posts:
        if post.id not in selected_ids and len(mixed_posts) < hot_count:
            mixed_posts.append(post)
            selected_ids.add(post.id)

    # 2. 再从最新帖子中选择
    random.shuffle(fresh_posts)
    for post in fresh_posts:
        if post.id not in selected_ids and len(mixed_posts) < hot_count + fresh_count:
            mixed_posts.append(post)
            selected_ids.add(post.id)

    # 3. 最后从随机帖子中选择
    random.shuffle(random_posts)
    for post in random_posts:
        if post.id not in selected_ids and len(mixed_posts) < total_limit:
            mixed_posts.append(post)
            selected_ids.add(post.id)

    # 如果仍然不足，从其他帖子中补充（排除已选择的和已读的）
    if len(mixed_posts) < total_limit:
        additional_query = db.query(models.Post) \
                             .filter(~models.Post.id.in_(selected_ids))
        if read_post_ids:
            additional_query = additional_query.filter(~models.Post.id.in_(read_post_ids))
        additional = additional_query.order_by(func.random()) \
                                     .limit(total_limit - len(mixed_posts)) \
                                     .all()
        mixed_posts.extend(additional)

    # 最后随机打乱顺序
    random.shuffle(mixed_posts)

    # 记录这次浏览的帖子为已读
    if user_id and mixed_posts:
        post_ids = [post.id for post in mixed_posts]
        crud.mark_posts_as_read(db, user_id, post_ids)
        print(f"[推荐算法] 用户 {user_id} 本次浏览 {len(post_ids)} 条帖子（{hot_count}热门+{fresh_count}最新+{random_count}随机），已记录为已读")

    return mixed_posts[:total_limit]


def get_mixed_comments(db: Session, post_id: int, hot_ratio: float = 0.7,
                       total_limit: int = 50) -> list:
    """获取帖子的混合评论（热门+最新）"""
    # 更新该帖子所有评论的热度
    comments = db.query(models.Comment).filter(models.Comment.post_id == post_id).all()
    for comment in comments:
        update_comment_hot_score(db, comment.id)

    hot_count = int(total_limit * hot_ratio)
    fresh_count = total_limit - hot_count

    # 获取热门评论（获取更多以确保去重后仍有足够数量）
    hot_comments = db.query(models.Comment) \
                     .filter(models.Comment.post_id == post_id) \
                     .order_by(desc(models.Comment.hot_score)) \
                     .limit(hot_count * 3) \
                     .all()

    # 获取最新评论（获取更多以确保去重后仍有足够数量）
    freshness_window = timedelta(hours=HOT_SCORE_CONFIG["comment_decay_half_life"])
    fresh_cutoff = datetime.utcnow() - freshness_window

    fresh_comments = db.query(models.Comment) \
                       .filter(models.Comment.post_id == post_id) \
                       .filter(models.Comment.created_at >= fresh_cutoff) \
                       .order_by(desc(models.Comment.created_at)) \
                       .limit(fresh_count * 3) \
                       .all()

    # 使用集合追踪已选择的评论ID，确保完全不重复
    selected_ids = set()
    mixed_comments = []

    # 先从热门评论中选择（不重复）
    random.shuffle(hot_comments)
    for comment in hot_comments:
        if comment.id not in selected_ids and len(mixed_comments) < hot_count:
            mixed_comments.append(comment)
            selected_ids.add(comment.id)

    # 再从最新评论中选择（不重复）
    random.shuffle(fresh_comments)
    for comment in fresh_comments:
        if comment.id not in selected_ids and len(mixed_comments) < total_limit:
            mixed_comments.append(comment)
            selected_ids.add(comment.id)

    # 如果仍然不足，从其他评论中补充（排除已选择的）
    if len(mixed_comments) < total_limit:
        additional = db.query(models.Comment) \
                       .filter(models.Comment.post_id == post_id) \
                       .filter(~models.Comment.id.in_(selected_ids)) \
                       .order_by(desc(models.Comment.created_at)) \
                       .limit(total_limit - len(mixed_comments)) \
                       .all()
        mixed_comments.extend(additional)

    # 最后随机打乱顺序
    random.shuffle(mixed_comments)

    return mixed_comments[:total_limit]


def get_mixed_replies(db: Session, comment_id: int, hot_ratio: float = 0.7,
                      total_limit: int = 50) -> list:
    """获取评论的混合回复（热门+最新）"""
    # 更新该评论所有回复的热度
    replies = db.query(models.Reply).filter(models.Reply.comment_id == comment_id).all()
    for reply in replies:
        update_reply_hot_score(db, reply.id)

    hot_count = int(total_limit * hot_ratio)
    fresh_count = total_limit - hot_count

    # 获取热门回复（获取更多以确保去重后仍有足够数量）
    hot_replies = db.query(models.Reply) \
                    .filter(models.Reply.comment_id == comment_id) \
                    .order_by(desc(models.Reply.hot_score)) \
                    .limit(hot_count * 3) \
                    .all()

    # 获取最新回复（获取更多以确保去重后仍有足够数量）
    freshness_window = timedelta(hours=HOT_SCORE_CONFIG["reply_decay_half_life"])
    fresh_cutoff = datetime.utcnow() - freshness_window

    fresh_replies = db.query(models.Reply) \
                      .filter(models.Reply.comment_id == comment_id) \
                      .filter(models.Reply.created_at >= fresh_cutoff) \
                      .order_by(desc(models.Reply.created_at)) \
                      .limit(fresh_count * 3) \
                      .all()

    # 使用集合追踪已选择的回复ID，确保完全不重复
    selected_ids = set()
    mixed_replies = []

    # 先从热门回复中选择（不重复）
    random.shuffle(hot_replies)
    for reply in hot_replies:
        if reply.id not in selected_ids and len(mixed_replies) < hot_count:
            mixed_replies.append(reply)
            selected_ids.add(reply.id)

    # 再从最新回复中选择（不重复）
    random.shuffle(fresh_replies)
    for reply in fresh_replies:
        if reply.id not in selected_ids and len(mixed_replies) < total_limit:
            mixed_replies.append(reply)
            selected_ids.add(reply.id)

    # 如果仍然不足，从其他回复中补充（排除已选择的）
    if len(mixed_replies) < total_limit:
        additional = db.query(models.Reply) \
                       .filter(models.Reply.comment_id == comment_id) \
                       .filter(~models.Reply.id.in_(selected_ids)) \
                       .order_by(desc(models.Reply.created_at)) \
                       .limit(total_limit - len(mixed_replies)) \
                       .all()
        mixed_replies.extend(additional)

    # 最后随机打乱顺序
    random.shuffle(mixed_replies)

    return mixed_replies[:total_limit]


def get_comments_by_interest(db: Session, post_id: int, interest_score: float,
                             max_items: int = 5) -> list:
    """
    根据兴趣系数获取评论和回复
    
    阅读评论数 = floor(兴趣系数 × max_items)
    每条评论下阅读回复数 = floor(兴趣系数 × max_items)
    
    Args:
        db: 数据库会话
        post_id: 帖子ID
        interest_score: 兴趣系数（0-1）
        max_items: 最大数量（默认5）
        
    Returns:
        list: 包含评论和回复的字典列表
    """
    items_to_read = int(interest_score * max_items)
    
    if items_to_read <= 0:
        return []
    
    # 获取混合排序的评论
    mixed_comments = get_mixed_comments(db, post_id, hot_ratio=0.7, total_limit=items_to_read * 2)
    selected_comments = mixed_comments[:items_to_read]
    
    result = []
    for comment in selected_comments:
        comment_data = {
            "id": comment.id,
            "type": "comment",
            "author": comment.author.username if comment.author else "Unknown",
            "content": comment.content,
            "hot_score": comment.hot_score,
            "created_at": comment.created_at.isoformat() if comment.created_at else None,
            "replies": []
        }
        
        # 获取该评论下的回复
        if items_to_read > 0:
            mixed_replies = get_mixed_replies(db, comment.id, hot_ratio=0.7, total_limit=items_to_read * 2)
            selected_replies = mixed_replies[:items_to_read]
            
            for reply in selected_replies:
                comment_data["replies"].append({
                    "id": reply.id,
                    "type": "reply",
                    "author": reply.author.username if reply.author else "Unknown",
                    "content": reply.content,
                    "hot_score": reply.hot_score,
                    "created_at": reply.created_at.isoformat() if reply.created_at else None
                })
        
        result.append(comment_data)
    
    return result


def get_trending_posts(db: Session, hours: int = 24, limit: int = 10) -> list:
    """获取趋势帖子（最近热度上升最快的）"""
    cutoff_time = datetime.utcnow() - timedelta(hours=hours)
    
    recent_likes = db.query(models.Like.post_id) \
                     .filter(models.Like.created_at >= cutoff_time) \
                     .distinct()
    
    recent_comments = db.query(models.Comment.post_id) \
                        .filter(models.Comment.created_at >= cutoff_time) \
                        .distinct()
    
    trending = db.query(models.Post) \
                 .filter(models.Post.id.in_(recent_likes.union(recent_comments))) \
                 .order_by(desc(models.Post.hot_score)) \
                 .limit(limit) \
                 .all()
    
    return trending
