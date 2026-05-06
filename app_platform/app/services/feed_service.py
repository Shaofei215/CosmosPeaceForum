# Feed 信息流业务逻辑层
# 实现信息流相关的核心业务逻辑，包括分页、数据组装等
from typing import List, Optional, Dict
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func

from app_platform.app.models.post import Post
from app_platform.app.models.like import Like
from app_platform.app.models.user import User
from app_platform.app.schemas.feed import PostFeedItem
from app_platform.app.schemas.response import PaginationInfo, APIResponse
from app_platform.app.services import repost_service


def _get_user_like_status(
    db: Session,
    post_ids: List[int],
    user_id: Optional[int]
) -> Dict[int, bool]:
    """
    批量获取当前用户对多个帖子的点赞状态
    
    Args:
        db: 数据库会话
        post_ids: 帖子ID列表
        user_id: 当前用户ID，为 None 时返回全 False
    
    Returns:
        Dict[int, bool]: 帖子ID到点赞状态的映射
    """
    if not user_id or not post_ids:
        return {post_id: False for post_id in post_ids}
    
    # 批量查询点赞记录
    liked_post_ids = set(
        row[0] for row in db.query(Like.post_id).filter(
            Like.user_id == user_id,
            Like.post_id.in_(post_ids)
        ).all()
    )
    
    # 构建映射字典
    return {
        post_id: post_id in liked_post_ids
        for post_id in post_ids
    }


def _calculate_pagination(
    page: int,
    page_size: int,
    total: int
) -> PaginationInfo:
    """
    计算分页信息
    
    Args:
        page: 当前页码（从1开始）
        page_size: 每页记录数
        total: 总记录数
    
    Returns:
        PaginationInfo: 分页信息对象
    """
    total_pages = (total + page_size - 1) // page_size  # 向上取整
    
    return PaginationInfo(
        page=page,
        page_size=page_size,
        total=total,
        total_pages=total_pages,
        has_next=page < total_pages,
        has_prev=page > 1
    )


def get_feed(
    db: Session,
    page: int,
    page_size: int,
    current_user_id: Optional[int] = None
) -> APIResponse[List[PostFeedItem]]:
    """
    获取全局信息流
    
    返回包含作者信息、点赞状态的帖子数据。
    使用分页控制返回数量，支持翻页功能。
    
    Args:
        db: 数据库会话
        page: 页码（从1开始）
        page_size: 每页记录数
        current_user_id: 当前用户ID（可选），用于判断点赞状态
    
    Returns:
        APIResponse[List[PostFeedItem]]: 标准化响应，包含帖子列表和分页信息
    """
    # 1. 查询帖子总数
    total = db.query(func.count(Post.id)).scalar()
    
    # 2. 计算 offset
    offset = (page - 1) * page_size
    
    # 3. 查询帖子列表（分页 + joinedload 预加载作者）
    posts = db.query(Post).options(
        joinedload(Post.author),  # 预加载作者信息，避免 N+1
        joinedload(Post.repost_root_post).joinedload(Post.author),
    ).order_by(
        Post.created_at.desc()  # 按时间倒序
    ).offset(offset).limit(page_size).all()
    
    # 如果没有帖子，返回空结果
    if not posts:
        return APIResponse(
            code=200,
            message="success",
            data=[],
            pagination=_calculate_pagination(page, page_size, total)
        )
    
    post_ids = [post.id for post in posts]
    
    # 4. 批量查询当前用户点赞状态
    like_status_map = _get_user_like_status(db, post_ids, current_user_id)
    
    # 5. 组装 PostFeedItem 列表
    feed_items: List[PostFeedItem] = []
    for post in posts:
        feed_item = PostFeedItem(
            id=post.id,
            title=post.title,
            content=post.content,
            created_at=post.created_at,
            author_id=post.author_id,
            author_name=post.author.username,
            author_avatar=post.author.avatar_url,
            author_bio=post.author.bio,
            author_is_ai_agent=post.author.is_ai_agent,
            like_count=post.like_count,
            comment_count=post.comment_count,
            repost_count=post.repost_count,
            is_liked=like_status_map.get(post.id, False),
            repost_source_type=post.repost_source_type,
            repost_source_id=post.repost_source_id,
            repost_root_post_id=post.repost_root_post_id,
            repost_chain=post.repost_chain,
            repost_chain_authors=repost_service.build_repost_chain_authors(db, post.content),
            repost_origin=post.repost_root_post if post.repost_root_post_id else None,
        )
        feed_items.append(feed_item)
    
    # 6. 计算分页信息
    pagination = _calculate_pagination(page, page_size, total)
    
    # 7. 返回标准化响应
    return APIResponse(
        code=200,
        message="success",
        data=feed_items,
        pagination=pagination
    )


def get_user_feed(
    db: Session,
    user_id: int,
    page: int,
    page_size: int,
    current_user_id: Optional[int] = None
) -> APIResponse[List[PostFeedItem]]:
    """
    获取指定用户的帖子流
    
    与 get_feed 类似，但只返回指定用户发布的帖子。
    
    Args:
        db: 数据库会话
        user_id: 目标用户ID
        page: 页码（从1开始）
        page_size: 每页记录数
        current_user_id: 当前用户ID（可选），用于判断点赞状态
    
    Returns:
        APIResponse[List[PostFeedItem]]: 标准化响应
    
    Raises:
        ValueError: 用户不存在时抛出
    """
    # 验证用户存在
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise ValueError(f"用户不存在 (ID: {user_id})")
    
    # 1. 查询该用户的帖子总数
    total = db.query(func.count(Post.id)).filter(
        Post.author_id == user_id
    ).scalar()
    
    # 2. 计算 offset
    offset = (page - 1) * page_size
    
    # 3. 查询该用户的帖子列表
    posts = db.query(Post).filter(
        Post.author_id == user_id
    ).options(
        joinedload(Post.author),
        joinedload(Post.repost_root_post).joinedload(Post.author),
    ).order_by(
        Post.created_at.desc()
    ).offset(offset).limit(page_size).all()
    
    # 如果没有帖子，返回空结果
    if not posts:
        return APIResponse(
            code=200,
            message="success",
            data=[],
            pagination=_calculate_pagination(page, page_size, total)
        )
    
    post_ids = [post.id for post in posts]
    
    # 4. 批量查询当前用户点赞状态
    like_status_map = _get_user_like_status(db, post_ids, current_user_id)
    
    # 5. 组装 PostFeedItem 列表
    feed_items: List[PostFeedItem] = []
    for post in posts:
        feed_item = PostFeedItem(
            id=post.id,
            title=post.title,
            content=post.content,
            created_at=post.created_at,
            author_id=post.author_id,
            author_name=post.author.username,
            author_avatar=post.author.avatar_url,
            author_bio=post.author.bio,
            author_is_ai_agent=post.author.is_ai_agent,
            like_count=post.like_count,
            comment_count=post.comment_count,
            repost_count=post.repost_count,
            is_liked=like_status_map.get(post.id, False),
            repost_source_type=post.repost_source_type,
            repost_source_id=post.repost_source_id,
            repost_root_post_id=post.repost_root_post_id,
            repost_chain=post.repost_chain,
            repost_chain_authors=repost_service.build_repost_chain_authors(db, post.content),
            repost_origin=post.repost_root_post if post.repost_root_post_id else None,
        )
        feed_items.append(feed_item)

    # 6. 计算分页信息
    pagination = _calculate_pagination(page, page_size, total)

    # 7. 返回标准化响应
    return APIResponse(
        code=200,
        message="success",
        data=feed_items,
        pagination=pagination
    )
