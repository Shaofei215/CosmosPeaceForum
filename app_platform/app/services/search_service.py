# 平台搜索业务逻辑
import logging
from typing import List, Literal

from sqlalchemy import case, func
from sqlalchemy.orm import Session, joinedload

from app_platform.app.models.post import Post
from app_platform.app.models.user import User
from app_platform.app.schemas.feed import PostFeedItem
from app_platform.app.schemas.response import APIResponse, PaginationInfo
from app_platform.app.schemas.user import UserResponse
from app_platform.app.services import feed_service
from app_platform.app.services.search_index import get_content_index, get_user_index


logger = logging.getLogger(__name__)
SearchType = Literal["content", "user"]
MAX_INDEX_RESULTS = 500


def _calculate_pagination(page: int, page_size: int, total: int) -> PaginationInfo:
    total_pages = (total + page_size - 1) // page_size
    return PaginationInfo(
        page=page,
        page_size=page_size,
        total=total,
        total_pages=total_pages,
        has_next=page < total_pages,
        has_prev=page > 1,
    )


def rebuild_search_indexes(db: Session) -> None:
    try:
        get_content_index().rebuild(db.query(Post).all())
        get_user_index().rebuild(db.query(User).filter(User.username.isnot(None)).all())
    except Exception as exc:
        logger.warning("重建平台搜索索引失败: %s", exc)


def ensure_search_indexes(db: Session) -> None:
    try:
        content_index = get_content_index()
        user_index = get_user_index()
        if not content_index.exists() or not user_index.exists():
            rebuild_search_indexes(db)
    except Exception as exc:
        logger.warning("检查平台搜索索引失败: %s", exc)


def index_post(post: Post) -> None:
    try:
        get_content_index().upsert(post)
    except Exception as exc:
        logger.warning("更新帖子搜索索引失败: post_id=%s error=%s", getattr(post, "id", None), exc)


def delete_post(post_id: int) -> None:
    try:
        get_content_index().delete(post_id)
    except Exception as exc:
        logger.warning("删除帖子搜索索引失败: post_id=%s error=%s", post_id, exc)


def index_user(user: User) -> None:
    try:
        get_user_index().upsert(user)
    except Exception as exc:
        logger.warning("更新用户搜索索引失败: user_id=%s error=%s", getattr(user, "id", None), exc)


def delete_user(user_id: int) -> None:
    try:
        get_user_index().delete(user_id)
    except Exception as exc:
        logger.warning("删除用户搜索索引失败: user_id=%s error=%s", user_id, exc)


def search_content(
    db: Session,
    query: str,
    page: int,
    page_size: int,
    current_user_id: int | None = None,
) -> APIResponse[List[PostFeedItem]]:
    query = query.strip()
    if not query:
        return APIResponse(
            code=200,
            message="success",
            data=[],
            pagination=_calculate_pagination(page, page_size, 0),
        )

    ensure_search_indexes(db)
    hits = get_content_index().search(query, limit=MAX_INDEX_RESULTS)
    post_ids = [hit.id for hit in hits]
    total = len(post_ids)
    page_ids = post_ids[(page - 1) * page_size: page * page_size]

    if not page_ids:
        return APIResponse(
            code=200,
            message="success",
            data=[],
            pagination=_calculate_pagination(page, page_size, total),
        )

    order_case = case({post_id: index for index, post_id in enumerate(page_ids)}, value=Post.id)
    posts = db.query(Post).filter(Post.id.in_(page_ids)).options(
        joinedload(Post.author),
        joinedload(Post.repost_root_post).joinedload(Post.author),
    ).order_by(order_case).all()
    feed_items = feed_service._build_feed_items(db, posts, current_user_id)

    return APIResponse(
        code=200,
        message="success",
        data=feed_items,
        pagination=_calculate_pagination(page, page_size, total),
    )


def search_users(
    db: Session,
    query: str,
    page: int,
    page_size: int,
) -> APIResponse[List[UserResponse]]:
    query = query.strip()
    if not query:
        return APIResponse(
            code=200,
            message="success",
            data=[],
            pagination=_calculate_pagination(page, page_size, 0),
        )

    ensure_search_indexes(db)
    hits = get_user_index().search(query, limit=MAX_INDEX_RESULTS)
    hit_ids = [hit.id for hit in hits]

    # 用户名搜索对精确/前缀命中的预期很强，先补一层数据库规则排序，再接 BM25。
    normalized_query = query.lower()
    exact_users = db.query(User).filter(func.lower(User.username) == normalized_query).all()
    prefix_users = db.query(User).filter(
        func.lower(User.username).like(f"{normalized_query}%"),
        func.lower(User.username) != normalized_query,
    ).order_by(User.followers_count.desc(), User.id.asc()).limit(MAX_INDEX_RESULTS).all()

    ordered_ids = []
    seen_ids = set()
    for user in exact_users + prefix_users:
        if user.id not in seen_ids:
            ordered_ids.append(user.id)
            seen_ids.add(user.id)
    for user_id in hit_ids:
        if user_id not in seen_ids:
            ordered_ids.append(user_id)
            seen_ids.add(user_id)

    total = len(ordered_ids)
    page_ids = ordered_ids[(page - 1) * page_size: page * page_size]
    if not page_ids:
        return APIResponse(
            code=200,
            message="success",
            data=[],
            pagination=_calculate_pagination(page, page_size, total),
        )

    order_case = case({user_id: index for index, user_id in enumerate(page_ids)}, value=User.id)
    users = db.query(User).filter(User.id.in_(page_ids)).order_by(order_case).all()

    return APIResponse(
        code=200,
        message="success",
        data=[UserResponse.model_validate(user) for user in users],
        pagination=_calculate_pagination(page, page_size, total),
    )
