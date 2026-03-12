"""
热度计算模块
提供帖子、评论、回复的热度计算、衰减和更新功能

热度公式:
- 帖子：score = (点赞数*1 + 评论数*2 + 转发数*3) * 时间衰减系数 + 新鲜度加成
- 评论：score = (点赞数*1 + 回复数*2) * 时间衰减系数
- 回复：score = (点赞数*1 + 子回复数*2) * 时间衰减系数

推荐算法（2026-03-06 更新）:
- 不再使用"数量混合"（40% 热门 +30% 最新 +30% 随机）
- 改用"热度排序 + 新鲜度加成 + 随机扰动"
- 核心思想：所有内容包括基础热度分，新内容获得额外加成，部分获得随机扰动
- 优势：真正按质量排序，同时保证新内容和长尾内容的曝光机会
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
    "comment_weight": 2,   # 评论/回复权重
    "quote_weight": 3,     # 转发权重（传播价值最高）
    "decay_half_life": 24, # 帖子半衰期（小时）
    "freshness_bonus": 50, # 新鲜度加成
    "freshness_window": 24, # 新鲜度窗口（小时）
    "comment_decay_half_life": 12, # 评论半衰期（小时）
    "reply_decay_half_life": 8,    # 回复半衰期（小时）- 回复衰减更快
}


def calculate_hot_score(likes_count: int, comments_count: int, 
                        created_at: datetime, last_update: Optional[datetime] = None,
                        quotes_count: int = 0) -> int:
    """
    计算帖子热度分数
    
    Args:
        likes_count: 点赞数
        comments_count: 评论数
        created_at: 帖子创建时间
        last_update: 上次热度更新时间（可选）
        quotes_count: 转发数（可选）
        
    Returns:
        int: 热度分数
    """
    # 基础分数 = 点赞*1 + 评论*2 + 转发*3
    base_score = likes_count * HOT_SCORE_CONFIG["like_weight"] + \
                 comments_count * HOT_SCORE_CONFIG["comment_weight"] + \
                 quotes_count * HOT_SCORE_CONFIG["quote_weight"]
    
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


def update_post_hot_score(db: Session, post_id: int, recursive: bool = True) -> int:
    """
    更新帖子的热度分数
    
    Args:
        db: 数据库会话
        post_id: 帖子 ID
        recursive: 是否递归更新所有被转发的帖子（默认 True）
    
    Returns:
        int: 热度分数
    """
    post = db.query(models.Post).filter(models.Post.id == post_id).first()
    if not post:
        return 0
    
    likes_count = db.query(models.Like).filter(models.Like.post_id == post_id).count()
    # 评论数 = 评论数 + 回复数
    comment_count = db.query(models.Comment).filter(models.Comment.post_id == post_id).count()
    reply_count = db.query(models.Reply).join(models.Comment).filter(models.Comment.post_id == post_id).count()
    comments_count = comment_count + reply_count
    # 转发数
    quotes_count = db.query(models.Post).filter(models.Post.quote_from_id == post_id).count()
    
    new_score = calculate_hot_score(
        likes_count=likes_count,
        comments_count=comments_count,
        created_at=post.created_at,
        last_update=post.last_hot_update,
        quotes_count=quotes_count
    )
    
    post.hot_score = new_score
    post.last_hot_update = datetime.utcnow()
    
    db.commit()
    db.refresh(post)
    
    # 递归更新所有被转发的帖子
    if recursive and post.post_type == 'quote' and post.quote_from_id:
        update_post_hot_score(db, post.quote_from_id, recursive=True)
    
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
    
    posts = db.query(models.Post) \
             .order_by(desc(models.Post.hot_score)) \
             .offset(offset) \
             .limit(limit) \
             .all()
    
    # 为每个帖子添加统计属性
    for post in posts:
        post.likes_count = db.query(models.Like).filter(models.Like.post_id == post.id).count()
        # 评论数 = 评论数 + 回复数
        comment_count = db.query(models.Comment).filter(models.Comment.post_id == post.id).count()
        reply_count = db.query(models.Reply).join(models.Comment).filter(models.Comment.post_id == post.id).count()
        post.comments_count = comment_count + reply_count
        # 递归统计转发数（包括间接转发）
        from app.crud import count_all_reposts
        post.reposts_count = count_all_reposts(db, post.id)
        post.views_count = post.hot_score
        # 获取点赞用户列表（最多 3 个）
        likers = db.query(models.Like).filter(models.Like.post_id == post.id).limit(3).all()
        post.likers = [like.user for like in likers if like.user]
    
    return posts


def get_mixed_posts(db: Session, user_id: Optional[int] = None,
                    hot_ratio: float = 0.4, fresh_ratio: float = 0.3, 
                    random_ratio: float = 0.3, total_limit: int = 50) -> list:
    """
    获取推荐帖子列表 - 基于热度排序 + 新鲜度加成 + 随机扰动
    
    新算法核心思想：
    1. 所有帖子按基础热度排序
    2. 新帖子获得新鲜度加成（fresh_ratio 权重，默认 30%）
    3. 部分帖子获得随机扰动（random_ratio 权重，默认 30%）
    4. 最终按综合得分排序
    
    Args:
        db: 数据库会话
        user_id: 用户 ID（可选），如果提供则排除该用户已读的帖子
        hot_ratio: 热度权重（实际不直接使用，体现在 base_score 中）
        fresh_ratio: 新鲜度加成权重（默认 30%）
        random_ratio: 随机扰动权重（默认 30%）
        total_limit: 返回帖子总数
        
    Returns:
        排序后的帖子列表
    """
    from app import crud
    
    update_all_hot_scores(db)

    # 获取用户的已读帖子 ID（如果提供了 user_id）
    read_post_ids = set()
    if user_id:
        read_post_ids = set(crud.get_user_read_post_ids(db, user_id))
        if read_post_ids:
            print(f"[推荐算法] 用户 {user_id} 已读 {len(read_post_ids)} 条帖子，将过滤")

    # 1. 获取所有帖子（排除已读）
    query = db.query(models.Post)
    if read_post_ids:
        query = query.filter(~models.Post.id.in_(read_post_ids))
    all_posts = query.all()

    # 2. 为每个帖子计算综合得分
    freshness_window = timedelta(hours=HOT_SCORE_CONFIG["freshness_window"])
    fresh_cutoff = datetime.utcnow() - freshness_window
    
    scored_posts = []
    for post in all_posts:
        base_score = post.hot_score
        final_score = base_score
        
        # 新鲜度加成：新帖子获得额外分数（最高增加 base_score * fresh_ratio）
        if post.created_at >= fresh_cutoff:
            hours_old = (datetime.utcnow() - post.created_at).total_seconds() / 3600
            freshness_factor = 1 - (hours_old / HOT_SCORE_CONFIG["freshness_window"])
            freshness_bonus = int(base_score * freshness_factor * fresh_ratio)
            final_score += freshness_bonus
        
        # 随机扰动：给 random_ratio 概率的帖子额外加分（让低热度帖子也有机会）
        if random.random() < random_ratio:
            random_bonus = random.randint(0, int(base_score * random_ratio))
            final_score += random_bonus
        
        scored_posts.append((final_score, post))

    # 3. 按综合得分降序排序
    scored_posts.sort(key=lambda x: x[0], reverse=True)

    # 4. 取前 N 条
    sorted_posts = [p[1] for p in scored_posts[:total_limit]]

    # 为每个帖子添加统计属性
    for post in sorted_posts:
        post.likes_count = db.query(models.Like).filter(models.Like.post_id == post.id).count()
        # 评论数 = 评论数 + 回复数
        comment_count = db.query(models.Comment).filter(models.Comment.post_id == post.id).count()
        reply_count = db.query(models.Reply).join(models.Comment).filter(models.Comment.post_id == post.id).count()
        post.comments_count = comment_count + reply_count
        # 递归统计转发数（包括间接转发）
        from app.crud import count_all_reposts
        post.reposts_count = count_all_reposts(db, post.id)
        post.views_count = post.hot_score
        # 获取点赞用户列表（最多 3 个）
        likers = db.query(models.Like).filter(models.Like.post_id == post.id).limit(3).all()
        post.likers = [like.user for like in likers if like.user]

    # 6. 记录已读
    if user_id and sorted_posts:
        post_ids = [post.id for post in sorted_posts]
        crud.mark_posts_as_read(db, user_id, post_ids)
        print(f"[推荐算法] 用户 {user_id} 本次浏览 {len(post_ids)} 条帖子（热度排序 + 新鲜度加成 + 随机扰动），已记录为已读")

    return sorted_posts


def get_mixed_comments(db: Session, post_id: int, hot_ratio: float = 0.7,
                       total_limit: int = 50) -> list:
    """
    获取帖子的评论列表 - 基于热度排序 + 新鲜度加成
    
    新算法核心思想：
    1. 所有评论按基础热度排序
    2. 新评论获得新鲜度加成（hot_ratio 控制，默认 70% 热度 +30% 新鲜度）
    3. 最终按综合得分排序
    
    Args:
        db: 数据库会话
        post_id: 帖子 ID
        hot_ratio: 热度权重（实际体现为 1-hot_ratio 的新鲜度加成权重）
        total_limit: 返回评论总数
        
    Returns:
        排序后的评论列表
    """
    # 1. 更新该帖子所有评论的热度
    comments = db.query(models.Comment).filter(models.Comment.post_id == post_id).all()
    for comment in comments:
        update_comment_hot_score(db, comment.id)

    # 2. 为每条评论计算综合得分
    freshness_window = timedelta(hours=HOT_SCORE_CONFIG["comment_decay_half_life"])
    fresh_cutoff = datetime.utcnow() - freshness_window
    
    scored_comments = []
    for comment in comments:
        base_score = comment.hot_score
        final_score = base_score
        
        # 新鲜度加成：新评论获得额外分数
        if comment.created_at >= fresh_cutoff:
            hours_old = (datetime.utcnow() - comment.created_at).total_seconds() / 3600
            freshness_factor = 1 - (hours_old / HOT_SCORE_CONFIG["comment_decay_half_life"])
            # 新鲜度加成权重 = 1 - hot_ratio（默认 30%）
            freshness_bonus = int(base_score * freshness_factor * (1 - hot_ratio))
            final_score += freshness_bonus
        
        scored_comments.append((final_score, comment))

    # 3. 按综合得分降序排序
    scored_comments.sort(key=lambda x: x[0], reverse=True)

    # 4. 取前 N 条
    sorted_comments = [c[1] for c in scored_comments[:total_limit]]

    # 5. 为每条评论添加统计属性和回复
    for comment in sorted_comments:
        comment.likes_count = db.query(models.Like).filter(models.Like.comment_id == comment.id).count()
        replies = db.query(models.Reply).filter(models.Reply.comment_id == comment.id).all()
        comment.replies_count = len(replies)
        # 为每个回复添加点赞数
        for reply in replies:
            reply.likes_count = db.query(models.Like).filter(models.Like.reply_id == reply.id).count()
        comment.replies = replies

    return sorted_comments


def get_mixed_replies(db: Session, comment_id: int, hot_ratio: float = 0.7,
                      total_limit: int = 50) -> list:
    """
    获取评论的回复列表 - 基于热度排序 + 新鲜度加成
    
    新算法核心思想：
    1. 所有回复按基础热度排序
    2. 新回复获得新鲜度加成（hot_ratio 控制，默认 70% 热度 +30% 新鲜度）
    3. 最终按综合得分排序
    
    Args:
        db: 数据库会话
        comment_id: 评论 ID
        hot_ratio: 热度权重（实际体现为 1-hot_ratio 的新鲜度加成权重）
        total_limit: 返回回复总数
        
    Returns:
        排序后的回复列表
    """
    # 1. 更新该评论所有回复的热度
    replies = db.query(models.Reply).filter(models.Reply.comment_id == comment_id).all()
    for reply in replies:
        update_reply_hot_score(db, reply.id)

    # 2. 为每条回复计算综合得分
    freshness_window = timedelta(hours=HOT_SCORE_CONFIG["reply_decay_half_life"])
    fresh_cutoff = datetime.utcnow() - freshness_window
    
    scored_replies = []
    for reply in replies:
        base_score = reply.hot_score
        final_score = base_score
        
        # 新鲜度加成：新回复获得额外分数
        if reply.created_at >= fresh_cutoff:
            hours_old = (datetime.utcnow() - reply.created_at).total_seconds() / 3600
            freshness_factor = 1 - (hours_old / HOT_SCORE_CONFIG["reply_decay_half_life"])
            # 新鲜度加成权重 = 1 - hot_ratio（默认 30%）
            freshness_bonus = int(base_score * freshness_factor * (1 - hot_ratio))
            final_score += freshness_bonus
        
        scored_replies.append((final_score, reply))

    # 3. 按综合得分降序排序
    scored_replies.sort(key=lambda x: x[0], reverse=True)

    # 4. 取前 N 条
    sorted_replies = [r[1] for r in scored_replies[:total_limit]]

    return sorted_replies


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
