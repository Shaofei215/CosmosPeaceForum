# 平台搜索业务逻辑
import logging
from typing import Dict, List, Literal

from sqlalchemy import case, func
from sqlalchemy.orm import Session, joinedload

from social_platform.app.domains.feed.queries import build_feed_items
from social_platform.app.domains.feed.schemas import PostFeedItem
from social_platform.app.domains.post.models import Post
from social_platform.app.domains.user.models import User
from social_platform.app.schemas.response import APIResponse, PaginationInfo
from social_platform.app.domains.search.schemas import UserSearchItem
from social_platform.app.domains.user.schemas import UserResponse
from social_platform.app.domains.follow import application as follow_service
from social_platform.app.domains.search.index import get_content_index, get_user_index


logger = logging.getLogger(__name__)
SearchType = Literal["content", "user"]
MAX_INDEX_RESULTS = 500
TITLE_CONTAINS_BOOST = 0.20
TITLE_EXACT_BOOST = 0.35
CONTENT_CONTAINS_BOOST = 0.05
MAX_HEAT_BOOST = 0.10


def _calculate_pagination(page: int, page_size: int, total: int) -> PaginationInfo:
    """根据 skip、limit 和 total 计算搜索分页元信息。"""
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
    """从数据库事实表重建搜索投影索引，供启动修复和维护任务使用。"""
    try:
        get_content_index().rebuild(db.query(Post).filter(Post.moderation_status == "active").all())
        get_user_index().rebuild(db.query(User).filter(User.username.isnot(None)).all())
    except Exception as exc:
        logger.warning("重建平台搜索索引失败: %s", exc)


def ensure_search_indexes(db: Session) -> None:
    """在搜索前确保投影索引存在，缺失时从数据库重建。"""
    try:
        content_index = get_content_index()
        user_index = get_user_index()
        if not content_index.exists() or not user_index.exists():
            rebuild_search_indexes(db)
    except Exception as exc:
        logger.warning("检查平台搜索索引失败: %s", exc)


def index_post(post: Post) -> None:
    """将帖子写入内容搜索投影，通常在 after_commit 订阅器中调用。"""
    try:
        get_content_index().upsert(post)
    except Exception as exc:
        logger.warning("更新帖子搜索索引失败: post_id=%s error=%s", getattr(post, "id", None), exc)


def delete_post(post_id: int) -> None:
    """从内容搜索投影删除帖子，响应帖子删除事件。"""
    try:
        get_content_index().delete(post_id)
    except Exception as exc:
        logger.warning("删除帖子搜索索引失败: post_id=%s error=%s", post_id, exc)


def index_user(user: User) -> None:
    """将用户写入用户搜索投影，响应用户注册或资料更新事件。"""
    try:
        get_user_index().upsert(user)
    except Exception as exc:
        logger.warning("更新用户搜索索引失败: user_id=%s error=%s", getattr(user, "id", None), exc)


def delete_user(user_id: int) -> None:
    """从用户搜索投影删除用户，响应用户删除事件。"""
    try:
        get_user_index().delete(user_id)
    except Exception as exc:
        logger.warning("删除用户搜索索引失败: user_id=%s error=%s", user_id, exc)


def _normalize_query_text(value: str | None) -> str:
    """规范化搜索词，避免空白查询进入索引层。"""
    return (value or "").strip().lower()


def _rank_content_search_posts(
    posts: List[Post],
    hit_score_map: Dict[int, float],
    query: str,
) -> List[Post]:
    """融合 BM25 命中和业务热度，对内容搜索结果进行最终排序。"""
    if not posts:
        return []

    normalized_query = _normalize_query_text(query)
    max_bm25_score = max((score for score in hit_score_map.values() if score > 0), default=0)
    max_heat_score = max((post.heat_score or 0 for post in posts), default=0)
    hit_rank_map = {post_id: index for index, post_id in enumerate(hit_score_map.keys())}

    def final_score(post: Post) -> tuple[float, float, float, int]:
        """计算单条内容搜索结果的融合排序分数。"""
        bm25_score = hit_score_map.get(post.id, 0.0)
        bm25_boost = bm25_score / max_bm25_score if max_bm25_score > 0 else 0.0

        title = _normalize_query_text(post.title)
        content = _normalize_query_text(post.content)
        title_contains_boost = (
            TITLE_CONTAINS_BOOST if normalized_query and normalized_query in title else 0.0
        )
        title_exact_boost = (
            TITLE_EXACT_BOOST if normalized_query and title == normalized_query else 0.0
        )
        content_contains_boost = (
            CONTENT_CONTAINS_BOOST if normalized_query and normalized_query in content else 0.0
        )

        heat_score = post.heat_score or 0.0
        heat_boost = (heat_score / max_heat_score * MAX_HEAT_BOOST) if max_heat_score > 0 else 0.0
        score = (
            bm25_boost
            + title_contains_boost
            + title_exact_boost
            + content_contains_boost
            + heat_boost
        )
        return (score, bm25_boost, heat_score, -hit_rank_map.get(post.id, MAX_INDEX_RESULTS))

    return sorted(posts, key=final_score, reverse=True)


def search_content(
    db: Session,
    query: str,
    page: int,
    page_size: int,
    current_user_id: int | None = None,
) -> APIResponse[List[PostFeedItem]]:
    """执行帖子内容搜索并返回稳定分页响应。"""
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
    hit_score_map = {hit.id: hit.score for hit in hits}
    post_ids = list(hit_score_map.keys())

    if not post_ids:
        return APIResponse(
            code=200,
            message="success",
            data=[],
            pagination=_calculate_pagination(page, page_size, 0),
        )

    posts = db.query(Post).filter(
        Post.id.in_(post_ids),
        Post.moderation_status == "active",
    ).options(
        joinedload(Post.author),
        joinedload(Post.repost_root_post).joinedload(Post.author),
    ).all()
    ranked_posts = _rank_content_search_posts(posts, hit_score_map, query)

    total = len(ranked_posts)
    page_posts = ranked_posts[(page - 1) * page_size: page * page_size]
    feed_items = build_feed_items(db, page_posts, current_user_id)

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
    current_user_id: int | None = None,
) -> APIResponse[List[UserSearchItem]]:
    """执行用户搜索并返回稳定分页响应。"""
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
    follow_status = {}
    if current_user_id is not None:
        follow_status = follow_service.get_follow_status_batch(
            db=db,
            current_user_id=current_user_id,
            target_user_ids=page_ids,
        )

    return APIResponse(
        code=200,
        message="success",
        data=[
            UserSearchItem(
                **UserResponse.model_validate(user).model_dump(),
                is_following=follow_status.get(user.id, {}).get("is_following", False),
                is_followed_by=follow_status.get(user.id, {}).get("is_followed_by", False),
                is_mutual=follow_status.get(user.id, {}).get("is_mutual", False),
            )
            for user in users
        ],
        pagination=_calculate_pagination(page, page_size, total),
    )
