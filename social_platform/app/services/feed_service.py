# Feed 信息流业务逻辑层
# 实现信息流相关的核心业务逻辑，包括分页、数据组装等
import hashlib
from typing import List, Optional, Dict
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func

from social_platform.app.models.follow import Follow
from social_platform.app.models.post import Post
from social_platform.app.models.like import Like
from social_platform.app.models.user import User
from social_platform.app.schemas.feed import PostFeedItem
from social_platform.app.schemas.response import PaginationInfo, APIResponse
from social_platform.app.services import repost_service

MIN_RECOMMENDATION_POOL_SIZE = 80
POOL_PAGE_MULTIPLIER = 4


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


def _normalize_feed_type(feed_type: str) -> str:
    value = (feed_type or "recommended").lower()
    # 兼容旧的 hot 命名，外部展示已统一为“推荐”。
    aliases = {
        "hot": "recommended",
        "recommend": "recommended",
        "recommended": "recommended",
        "latest": "latest",
        "following": "following",
    }
    if value not in aliases:
        raise ValueError("feed_type 必须是 recommended、latest 或 following")
    return aliases[value]


def _post_order_by(feed_type: str):
    if feed_type == "latest":
        return (Post.created_at.desc(), Post.id.desc())
    # 推荐流和关注流都使用缓存热度排序，避免每次请求实时计算整表分数。
    return (func.coalesce(Post.heat_score, 0).desc(), Post.created_at.desc(), Post.id.desc())


def _normalize_seed(seed: Optional[str]) -> str:
    return (seed or "default").strip() or "default"


def _seeded_jitter(seed: str, item_id: int) -> float:
    digest = hashlib.sha256(f"{seed}:{item_id}".encode("utf-8")).hexdigest()
    return int(digest[:12], 16) / float(0xFFFFFFFFFFFF)


def _recommendation_rank(index: int, pool_size: int, post: Post, seed: str) -> float:
    jitter = _seeded_jitter(seed, post.id)
    quality = 1 - index / max(pool_size - 1, 1)
    # Top-N 内按“热度名次 + 本次浏览扰动”融合，避免头部内容在刷新时完全固化。
    return quality * 0.7 + jitter * 0.3


def _get_posts_for_feed(
    query,
    page: int,
    page_size: int,
    total: int,
    feed_type: str,
    seed: str,
) -> List[Post]:
    offset = (page - 1) * page_size

    if feed_type == "latest":
        return query.options(
            joinedload(Post.author),
            joinedload(Post.repost_root_post).joinedload(Post.author),
        ).order_by(
            *_post_order_by(feed_type)
        ).offset(offset).limit(page_size).all()

    pool_size = min(
        total,
        max(MIN_RECOMMENDATION_POOL_SIZE, offset + page_size * POOL_PAGE_MULTIPLIER),
    )
    candidates = query.options(
        joinedload(Post.author),
        joinedload(Post.repost_root_post).joinedload(Post.author),
    ).order_by(
        *_post_order_by(feed_type)
    ).limit(pool_size).all()

    pool_size = len(candidates)
    candidates = [
        post
        for _, post in sorted(
            enumerate(candidates),
            key=lambda item: _recommendation_rank(item[0], pool_size, item[1], seed),
            reverse=True,
        )
    ]
    return candidates[offset:offset + page_size]


def _build_feed_items(
    db: Session,
    posts: List[Post],
    current_user_id: Optional[int],
) -> List[PostFeedItem]:
    post_ids = [post.id for post in posts]
    like_status_map = _get_user_like_status(db, post_ids, current_user_id)

    feed_items: List[PostFeedItem] = []
    for post in posts:
        feed_item = PostFeedItem(
            id=post.id,
            title=post.title,
            type=post.type,
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
            heat_score=post.heat_score or 0,
            is_liked=like_status_map.get(post.id, False),
            repost_source_type=post.repost_source_type,
            repost_source_id=post.repost_source_id,
            repost_root_post_id=post.repost_root_post_id,
            repost_chain=post.repost_chain,
            repost_chain_authors=repost_service.build_repost_chain_authors(db, post.content),
            repost_origin=post.repost_root_post if post.repost_root_post_id else None,
            repost_origin_missing=repost_service.is_repost_origin_missing(post),
        )
        feed_items.append(feed_item)

    return feed_items


def get_feed(
    db: Session,
    page: int,
    page_size: int,
    current_user_id: Optional[int] = None,
    feed_type: str = "recommended",
    seed: Optional[str] = None,
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
    feed_type = _normalize_feed_type(feed_type)
    seed = _normalize_seed(seed)

    # 关注流必须基于当前用户关系；匿名访问时保持公开读取语义，返回空列表。
    if feed_type == "following" and current_user_id is None:
        return APIResponse(
            code=200,
            message="success",
            data=[],
            pagination=_calculate_pagination(page, page_size, 0)
        )

    query = db.query(Post)

    if feed_type == "following":
        query = query.join(Follow, Follow.following_id == Post.author_id).filter(
            Follow.follower_id == current_user_id
        )

    # 1. 查询帖子总数
    total = query.with_entities(func.count(Post.id)).scalar()

    # 2. 查询帖子列表。推荐类流先取 Top-N 候选池，再用本次浏览 seed 重排。
    posts = _get_posts_for_feed(
        query=query,
        page=page,
        page_size=page_size,
        total=total,
        feed_type=feed_type,
        seed=seed,
    )

    # 如果没有帖子，返回空结果
    if not posts:
        return APIResponse(
            code=200,
            message="success",
            data=[],
            pagination=_calculate_pagination(page, page_size, total)
        )

    # 4. 组装 PostFeedItem 列表
    feed_items = _build_feed_items(db, posts, current_user_id)

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

    # 4. 组装 PostFeedItem 列表
    feed_items = _build_feed_items(db, posts, current_user_id)

    # 6. 计算分页信息
    pagination = _calculate_pagination(page, page_size, total)

    # 7. 返回标准化响应
    return APIResponse(
        code=200,
        message="success",
        data=feed_items,
        pagination=pagination
    )
