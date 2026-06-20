"""信息流领域读侧查询与响应组装。

本模块承接 feed 领域的列表、分页、推荐重排和当前用户状态增强逻辑。调用方包括
feed HTTP adapter 与搜索领域的内容搜索结果组装；本模块不发布领域事件，不提交事务。
"""

from __future__ import annotations

import hashlib
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Query, Session, joinedload

from social_platform.app.domains.feed.schemas import PostFeedItem
from social_platform.app.domains.follow.models import Follow
from social_platform.app.domains.post import poll_queries, queries as post_queries
from social_platform.app.domains.post.models import Post
from social_platform.app.domains.reaction.models import Like
from social_platform.app.domains.topic import queries as topic_queries
from social_platform.app.domains.user.models import User
from social_platform.app.schemas.response import APIResponse, PaginationInfo


MIN_RECOMMENDATION_POOL_SIZE = 80
POOL_PAGE_MULTIPLIER = 4


def get_feed(
    db: Session,
    page: int,
    page_size: int,
    current_user_id: int | None = None,
    feed_type: str = "recommended",
    seed: str | None = None,
) -> APIResponse[list[PostFeedItem]]:
    """获取全局信息流。

    Args:
        db: 当前数据库会话。
        page: 页码，从 1 开始。
        page_size: 每页记录数。
        current_user_id: 当前登录用户 ID；匿名访问时为 ``None``。
        feed_type: 信息流类型，支持 ``recommended``、``latest``、``following`` 及兼容别名。
        seed: 推荐流重排种子，同一 seed 下分页结果稳定。

    Returns:
        APIResponse[list[PostFeedItem]]: 带分页信息的信息流响应。

    Raises:
        ValueError: 当 feed_type 不受支持时抛出。
        数据库查询异常会透传给调用方。
    """

    normalized_feed_type = normalize_feed_type(feed_type)
    normalized_seed = normalize_seed(seed)

    if normalized_feed_type == "following" and current_user_id is None:
        return APIResponse(
            code=200,
            message="success",
            data=[],
            pagination=calculate_pagination(page, page_size, 0),
        )

    query = db.query(Post).filter(Post.moderation_status == "active")
    if normalized_feed_type == "following":
        query = query.join(Follow, Follow.following_id == Post.author_id).filter(
            Follow.follower_id == current_user_id,
        )

    total = query.with_entities(func.count(Post.id)).scalar() or 0
    posts = get_posts_for_feed(
        query=query,
        page=page,
        page_size=page_size,
        total=total,
        feed_type=normalized_feed_type,
        seed=normalized_seed,
    )

    return APIResponse(
        code=200,
        message="success",
        data=build_feed_items(db, posts, current_user_id) if posts else [],
        pagination=calculate_pagination(page, page_size, total),
    )


def get_user_feed(
    db: Session,
    user_id: int,
    page: int,
    page_size: int,
    current_user_id: int | None = None,
) -> APIResponse[list[PostFeedItem]]:
    """获取指定用户发布的帖子流。

    Args:
        db: 当前数据库会话。
        user_id: 目标用户 ID。
        page: 页码，从 1 开始。
        page_size: 每页记录数。
        current_user_id: 当前登录用户 ID；匿名访问时为 ``None``。

    Returns:
        APIResponse[list[PostFeedItem]]: 指定用户帖子流响应。

    Raises:
        ValueError: 当目标用户不存在时抛出。
        数据库查询异常会透传给调用方。
    """

    user = db.query(User.id).filter(User.id == user_id).first()
    if not user:
        raise ValueError(f"用户不存在 (ID: {user_id})")

    total = db.query(func.count(Post.id)).filter(
        Post.author_id == user_id,
        Post.moderation_status == "active",
    ).scalar() or 0
    offset = (page - 1) * page_size
    posts = db.query(Post).filter(
        Post.author_id == user_id,
        Post.moderation_status == "active",
    ).options(
        joinedload(Post.author),
        joinedload(Post.repost_root_post).joinedload(Post.author),
    ).order_by(
        Post.created_at.desc(),
    ).offset(offset).limit(page_size).all()

    return APIResponse(
        code=200,
        message="success",
        data=build_feed_items(db, posts, current_user_id) if posts else [],
        pagination=calculate_pagination(page, page_size, total),
    )


def build_feed_items(
    db: Session,
    posts: list[Post],
    current_user_id: int | None,
) -> list[PostFeedItem]:
    """将帖子 ORM 列表组装为信息流响应项。

    Args:
        db: 当前数据库会话。
        posts: 已查询并预加载作者信息的帖子列表。
        current_user_id: 当前登录用户 ID；匿名访问时为 ``None``。

    Returns:
        list[PostFeedItem]: 与 ``posts`` 顺序一致的信息流响应项。

    Raises:
        数据库查询异常会透传给调用方。
    """

    post_ids = [post.id for post in posts]
    like_status_map = get_user_like_status(db, post_ids, current_user_id)
    follow_status_map = get_author_follow_status(
        db,
        [post.author_id for post in posts],
        current_user_id,
    )
    mention_users_by_post = post_queries.build_mention_users_for_contents(
        db,
        [post.content for post in posts],
    )
    topic_mentions_by_post = topic_queries.build_topic_mentions_for_post_ids(db, post_ids)
    poll_map = poll_queries.build_poll_response_map(db, post_ids, current_user_id)

    feed_items: list[PostFeedItem] = []
    for post, mention_users in zip(posts, mention_users_by_post):
        author_follow_status = follow_status_map.get(post.author_id, {})
        feed_items.append(
            PostFeedItem(
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
                author_is_following=author_follow_status.get("is_following", False),
                author_is_followed_by=author_follow_status.get("is_followed_by", False),
                author_is_mutual=author_follow_status.get("is_mutual", False),
                like_count=post.like_count,
                comment_count=post.comment_count,
                repost_count=post.repost_count,
                heat_score=post.heat_score or 0,
                is_liked=like_status_map.get(post.id, False),
                repost_source_type=post.repost_source_type,
                repost_source_id=post.repost_source_id,
                repost_root_post_id=post.repost_root_post_id,
                repost_chain=post.repost_chain,
                repost_chain_authors=mention_users,
                mention_users=mention_users,
                topic_mentions=topic_mentions_by_post.get(post.id, []),
                repost_origin=post.repost_root_post if post.repost_root_post_id else None,
                repost_origin_missing=post_queries.is_repost_origin_missing(post),
                poll=poll_map.get(post.id),
            )
        )

    return feed_items


def get_user_like_status(
    db: Session,
    post_ids: list[int],
    user_id: int | None,
) -> dict[int, bool]:
    """批量获取当前用户对多个帖子的点赞状态。

    Args:
        db: 当前数据库会话。
        post_ids: 帖子 ID 列表。
        user_id: 当前登录用户 ID；匿名访问时为 ``None``。

    Returns:
        dict[int, bool]: 帖子 ID 到点赞状态的映射。
    """

    if not user_id or not post_ids:
        return {post_id: False for post_id in post_ids}

    liked_post_ids = {
        row[0]
        for row in db.query(Like.post_id).filter(
            Like.user_id == user_id,
            Like.post_id.in_(post_ids),
        ).all()
    }
    return {post_id: post_id in liked_post_ids for post_id in post_ids}


def get_author_follow_status(
    db: Session,
    author_ids: list[int],
    current_user_id: int | None,
) -> dict[int, dict[str, bool]]:
    """批量获取当前用户与多个作者之间的关注状态。

    Args:
        db: 当前数据库会话。
        author_ids: 作者用户 ID 列表。
        current_user_id: 当前登录用户 ID；匿名访问时为 ``None``。

    Returns:
        dict[int, dict[str, bool]]: 作者 ID 到关注状态字段的映射。
    """

    if not current_user_id or not author_ids:
        return {}

    target_author_ids = list(
        dict.fromkeys(author_id for author_id in author_ids if author_id != current_user_id)
    )
    if not target_author_ids:
        return {}

    following_ids = {
        row[0]
        for row in db.query(Follow.following_id).filter(
            Follow.follower_id == current_user_id,
            Follow.following_id.in_(target_author_ids),
        ).all()
    }
    follower_ids = {
        row[0]
        for row in db.query(Follow.follower_id).filter(
            Follow.following_id == current_user_id,
            Follow.follower_id.in_(target_author_ids),
        ).all()
    }

    return {
        author_id: {
            "is_following": author_id in following_ids,
            "is_followed_by": author_id in follower_ids,
            "is_mutual": author_id in following_ids and author_id in follower_ids,
        }
        for author_id in target_author_ids
    }


def calculate_pagination(page: int, page_size: int, total: int) -> PaginationInfo:
    """根据当前页、页大小和总数计算分页信息。

    Args:
        page: 页码，从 1 开始。
        page_size: 每页记录数。
        total: 符合条件的总记录数。

    Returns:
        PaginationInfo: 标准分页元信息。
    """

    total_pages = (total + page_size - 1) // page_size
    return PaginationInfo(
        page=page,
        page_size=page_size,
        total=total,
        total_pages=total_pages,
        has_next=page < total_pages,
        has_prev=page > 1,
    )


def normalize_feed_type(feed_type: str) -> str:
    """规范化信息流类型并兼容历史别名。

    Args:
        feed_type: 外部传入的信息流类型。

    Returns:
        str: 规范化后的类型，取值为 ``recommended``、``latest`` 或 ``following``。

    Raises:
        ValueError: 当 feed_type 不受支持时抛出。
    """

    value = (feed_type or "recommended").lower()
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


def post_order_by(feed_type: str) -> tuple[Any, ...]:
    """根据信息流类型返回帖子查询排序条件。

    Args:
        feed_type: 已规范化的信息流类型。

    Returns:
        tuple[Any, ...]: 可传给 SQLAlchemy ``order_by`` 的排序表达式。
    """

    if feed_type == "latest":
        return (Post.created_at.desc(), Post.id.desc())
    return (func.coalesce(Post.heat_score, 0).desc(), Post.created_at.desc(), Post.id.desc())


def normalize_seed(seed: str | None) -> str:
    """规范化推荐重排种子。

    Args:
        seed: 外部传入的 seed，可为空。

    Returns:
        str: 非空 seed。
    """

    return (seed or "default").strip() or "default"


def seeded_jitter(seed: str, item_id: int) -> float:
    """基于 seed 和对象 ID 生成稳定扰动值。

    Args:
        seed: 推荐重排种子。
        item_id: 帖子 ID。

    Returns:
        float: ``0`` 到 ``1`` 之间的稳定扰动值。
    """

    digest = hashlib.sha256(f"{seed}:{item_id}".encode("utf-8")).hexdigest()
    return int(digest[:12], 16) / float(0xFFFFFFFFFFFF)


def recommendation_rank(index: int, pool_size: int, post: Post, seed: str) -> float:
    """计算推荐流候选帖子的轻量重排分数。

    Args:
        index: 候选帖子在热度排序池中的名次。
        pool_size: 候选池大小。
        post: 候选帖子。
        seed: 推荐重排种子。

    Returns:
        float: 融合热度名次与稳定扰动后的排序分数。
    """

    jitter = seeded_jitter(seed, post.id)
    quality = 1 - index / max(pool_size - 1, 1)
    return quality * 0.7 + jitter * 0.3


def get_posts_for_feed(
    query: Query,
    page: int,
    page_size: int,
    total: int,
    feed_type: str,
    seed: str,
) -> list[Post]:
    """按信息流排序策略读取当前分页窗口的帖子。

    Args:
        query: 已应用基础过滤条件的帖子查询。
        page: 页码，从 1 开始。
        page_size: 每页记录数。
        total: 符合条件的总记录数。
        feed_type: 已规范化的信息流类型。
        seed: 推荐重排种子。

    Returns:
        list[Post]: 当前分页窗口中的帖子列表。

    Raises:
        数据库查询异常会透传给调用方。
    """

    offset = (page - 1) * page_size
    post_query = query.options(
        joinedload(Post.author),
        joinedload(Post.repost_root_post).joinedload(Post.author),
    )

    if feed_type == "latest":
        return post_query.order_by(*post_order_by(feed_type)).offset(offset).limit(page_size).all()

    pool_size = min(
        total,
        max(MIN_RECOMMENDATION_POOL_SIZE, offset + page_size * POOL_PAGE_MULTIPLIER),
    )
    candidates = post_query.order_by(*post_order_by(feed_type)).limit(pool_size).all()
    actual_pool_size = len(candidates)
    candidates = [
        post
        for _, post in sorted(
            enumerate(candidates),
            key=lambda item: recommendation_rank(item[0], actual_pool_size, item[1], seed),
            reverse=True,
        )
    ]
    return candidates[offset:offset + page_size]
