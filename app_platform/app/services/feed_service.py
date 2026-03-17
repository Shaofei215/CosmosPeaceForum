# Feed 信息流业务逻辑层
# 实现信息流相关的核心业务逻辑，包括分页、数据组装等
from typing import List, Optional, Dict, Tuple
from collections import defaultdict
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func

from app.models.post import Post
from app.models.like import Like
from app.models.comment import Comment
from app.models.user import User
from app.schemas.feed import PostFeedItem, CommentPreviewItem
from app.schemas.response import PaginationInfo, APIResponse


def _get_preview_comments(
    db: Session,
    post_ids: List[int],
    limit_per_post: int = 2
) -> Dict[int, List[Comment]]:
    """
    批量获取每个帖子的前 N 条一级评论
    
    关键实现：使用应用层分组而非 SQL LIMIT，
    因为 SQL 的 LIMIT 无法作用于"每个分组"。
    
    Args:
        db: 数据库会话
        post_ids: 帖子ID列表
        limit_per_post: 每个帖子返回的评论数量，默认2条
    
    Returns:
        Dict[int, List[Comment]]: 帖子ID到评论列表的映射
        每个帖子的评论列表最多包含 limit_per_post 条
    
    Example:
        >>> comments_map = _get_preview_comments(db, [1, 2, 3], limit_per_post=2)
        >>> comments_map[1]  # 获取帖子1的预览评论（最多2条）
        [Comment(id=1, ...), Comment(id=2, ...)]
    """
    if not post_ids:
        return {}
    
    # 批量查询所有一级评论（parent_id IS NULL）
    # 使用 joinedload 预加载评论作者，避免 N+1 查询
    all_comments = db.query(Comment).filter(
        Comment.post_id.in_(post_ids),
        Comment.parent_id == None  # 只取一级评论
    ).options(
        joinedload(Comment.owner)  # 预加载评论作者
    ).order_by(
        Comment.post_id,
        Comment.created_at.desc()  # 按时间倒序，最新的在前
    ).all()
    
    # 应用层分组：按 post_id 分组，每个帖子取前 N 条
    result: Dict[int, List[Comment]] = defaultdict(list)
    for comment in all_comments:
        if len(result[comment.post_id]) < limit_per_post:
            result[comment.post_id].append(comment)
    
    return dict(result)


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
    
    Example:
        >>> like_status = _get_user_like_status(db, [1, 2, 3], user_id=123)
        >>> like_status[1]  # 用户是否点赞了帖子1
        True
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
    
    Example:
        >>> pagination = _calculate_pagination(1, 20, 100)
        >>> pagination.total_pages
        5
        >>> pagination.has_next
        True
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
    
    返回包含作者信息、点赞状态、预览评论的完整帖子数据。
    使用分页控制返回数量，支持翻页功能。
    
    实现流程：
    1. 查询帖子总数（用于分页计算）
    2. 查询帖子列表（分页 + joinedload 预加载作者）
    3. 批量查询当前用户点赞状态（IN 查询）
    4. 批量查询所有相关评论（IN 查询 + 预加载评论作者）
    5. 应用层按 post_id 分组，每个帖子取前 2 条一级评论
    6. 计算 has_more_comments = post.comment_count > len(preview_comments)
    7. 组装 PostFeedItem 列表
    8. 计算分页信息
    9. 返回标准化响应结构
    
    Args:
        db: 数据库会话
        page: 页码（从1开始）
        page_size: 每页记录数
        current_user_id: 当前用户ID（可选），用于判断点赞状态
    
    Returns:
        APIResponse[List[PostFeedItem]]: 标准化响应，包含帖子列表和分页信息
    
    Example:
        >>> response = get_feed(db, page=1, page_size=20, current_user_id=123)
        >>> len(response.data)  # 当前页帖子数
        20
        >>> response.pagination.total  # 总帖子数
        100
    """
    # 1. 查询帖子总数
    total = db.query(func.count(Post.id)).scalar()
    
    # 2. 计算 offset
    offset = (page - 1) * page_size
    
    # 3. 查询帖子列表（分页 + joinedload 预加载作者）
    posts = db.query(Post).options(
        joinedload(Post.author)  # 预加载作者信息，避免 N+1
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
    
    # 5. 批量查询预览评论（应用层分组，每个帖子最多2条）
    preview_comments_map = _get_preview_comments(db, post_ids, limit_per_post=2)
    
    # 6. 组装 PostFeedItem 列表
    feed_items: List[PostFeedItem] = []
    for post in posts:
        # 获取该帖子的预览评论
        preview_comments = preview_comments_map.get(post.id, [])
        
        # 转换预览评论为响应格式
        preview_comment_items: List[CommentPreviewItem] = []
        for comment in preview_comments:
            preview_comment_items.append(
                CommentPreviewItem(
                    id=comment.id,
                    content=comment.content,
                    created_at=comment.created_at,
                    owner_id=comment.owner_id,
                    owner_name=comment.owner.username,
                    owner_avatar=comment.owner.avatar_url,
                    like_count=comment.like_count
                )
            )
        
        # 计算是否有更多评论
        has_more_comments = post.comment_count > len(preview_comments)
        
        # 构建 PostFeedItem
        feed_item = PostFeedItem(
            id=post.id,
            title=post.title,
            content=post.content,
            created_at=post.created_at,
            author_id=post.author_id,
            author_name=post.author.username,
            author_avatar=post.author.avatar_url,
            like_count=post.like_count,
            comment_count=post.comment_count,
            is_liked=like_status_map.get(post.id, False),
            has_more_comments=has_more_comments,
            preview_comments=preview_comment_items
        )
        feed_items.append(feed_item)
    
    # 7. 计算分页信息
    pagination = _calculate_pagination(page, page_size, total)
    
    # 8. 返回标准化响应
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
    
    Example:
        >>> response = get_user_feed(db, user_id=123, page=1, page_size=20)
        >>> response.data[0].author_id  # 所有帖子都来自用户123
        123
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
        joinedload(Post.author)
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
    
    # 5. 批量查询预览评论
    preview_comments_map = _get_preview_comments(db, post_ids, limit_per_post=2)
    
    # 6. 组装 PostFeedItem 列表
    feed_items: List[PostFeedItem] = []
    for post in posts:
        preview_comments = preview_comments_map.get(post.id, [])
        
        preview_comment_items: List[CommentPreviewItem] = []
        for comment in preview_comments:
            preview_comment_items.append(
                CommentPreviewItem(
                    id=comment.id,
                    content=comment.content,
                    created_at=comment.created_at,
                    owner_id=comment.owner_id,
                    owner_name=comment.owner.username,
                    owner_avatar=comment.owner.avatar_url,
                    like_count=comment.like_count
                )
            )
        
        has_more_comments = post.comment_count > len(preview_comments)
        
        feed_item = PostFeedItem(
            id=post.id,
            title=post.title,
            content=post.content,
            created_at=post.created_at,
            author_id=post.author_id,
            author_name=post.author.username,
            author_avatar=post.author.avatar_url,
            like_count=post.like_count,
            comment_count=post.comment_count,
            is_liked=like_status_map.get(post.id, False),
            has_more_comments=has_more_comments,
            preview_comments=preview_comment_items
        )
        feed_items.append(feed_item)
    
    # 7. 计算分页信息
    pagination = _calculate_pagination(page, page_size, total)
    
    # 8. 返回标准化响应
    return APIResponse(
        code=200,
        message="success",
        data=feed_items,
        pagination=pagination
    )
