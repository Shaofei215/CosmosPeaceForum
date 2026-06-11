# 评论业务逻辑层
# 实现评论相关的核心业务逻辑，包括创建、查询、点赞等功能
import hashlib
from collections import defaultdict

from sqlalchemy.orm import Session, joinedload
from sqlalchemy.orm.attributes import set_committed_value
from sqlalchemy.exc import IntegrityError
from typing import Tuple, List, Optional

from social_platform.app.models.comment import Comment, CommentLike
from social_platform.app.models.post import Post
from social_platform.app.models.user import User
from social_platform.app.services import heat_service, mention_service, notification_service, repost_service

MIN_COMMENT_POOL_SIZE = 40
COMMENT_POOL_PAGE_MULTIPLIER = 4


class PostNotFoundError(Exception):
    """
    自定义异常：帖子不存在
    
    当尝试对不存在的帖子进行评论操作时抛出此异常
    """
    def __init__(self, post_id: int):
        """
        初始化异常
        
        Args:
            post_id: 不存在的帖子 ID
        """
        self.post_id = post_id
        super().__init__(f"帖子不存在 (ID: {post_id})")


class CommentNotFoundError(Exception):
    """
    自定义异常：评论不存在
    
    当尝试对不存在的评论进行操作时抛出此异常
    """
    def __init__(self, comment_id: int):
        """
        初始化异常
        
        Args:
            comment_id: 不存在的评论 ID
        """
        self.comment_id = comment_id
        super().__init__(f"评论不存在 (ID: {comment_id})")


class ParentCommentNotFoundError(Exception):
    """
    自定义异常：父评论不存在
    
    当尝试回复不存在的评论时抛出此异常
    """
    def __init__(self, parent_id: int):
        """
        初始化异常
        
        Args:
            parent_id: 不存在的父评论 ID
        """
        self.parent_id = parent_id
        super().__init__(f"父评论不存在 (ID: {parent_id})")


class ParentCommentMismatchError(Exception):
    """
    自定义异常：父评论与帖子不匹配
    
    当回复的评论不属于指定帖子时抛出此异常
    """
    def __init__(self, parent_id: int, post_id: int, actual_post_id: int):
        """
        初始化异常
        
        Args:
            parent_id: 父评论 ID
            post_id: 期望的帖子 ID
            actual_post_id: 实际的帖子 ID
        """
        self.parent_id = parent_id
        self.post_id = post_id
        self.actual_post_id = actual_post_id
        super().__init__(f"父评论 (ID: {parent_id}) 不属于帖子 (ID: {post_id})，实际属于帖子 (ID: {actual_post_id})")


def _normalize_comment_sort(sort: str) -> str:
    value = (sort or "default").lower()
    # default 表示评论区的推荐排序；保留 hot/recommended 作为兼容别名。
    aliases = {
        "default": "default",
        "recommended": "default",
        "hot": "default",
        "latest": "latest",
    }
    if value not in aliases:
        raise ValueError("sort 必须是 default 或 latest")
    return aliases[value]


def _comment_order_by(sort: str):
    if sort == "latest":
        return (Comment.created_at.desc(), Comment.id.desc())
    # 评论默认流使用缓存热度，时间倒序和 ID 只作为稳定兜底。
    return (Comment.heat_score.desc(), Comment.created_at.desc(), Comment.id.desc())


def _normalize_seed(seed: Optional[str]) -> str:
    return (seed or "default").strip() or "default"


def _seeded_jitter(seed: str, item_id: int) -> float:
    digest = hashlib.sha256(f"{seed}:{item_id}".encode("utf-8")).hexdigest()
    return int(digest[:12], 16) / float(0xFFFFFFFFFFFF)


def _comment_recommendation_rank(index: int, pool_size: int, comment: Comment, seed: str) -> float:
    jitter = _seeded_jitter(seed, comment.id)
    quality = 1 - index / max(pool_size - 1, 1)
    return quality * 0.8 + jitter * 0.2


def _get_comments_for_tree(query, skip: int, limit: int, total: int, sort: str, seed: str) -> List[Comment]:
    if sort == "latest":
        return query.order_by(*_comment_order_by(sort)).offset(skip).limit(limit).all()

    pool_size = min(
        total,
        max(MIN_COMMENT_POOL_SIZE, skip + limit * COMMENT_POOL_PAGE_MULTIPLIER),
    )
    candidates = query.order_by(*_comment_order_by(sort)).limit(pool_size).all()
    pool_size = len(candidates)
    candidates = [
        comment
        for _, comment in sorted(
            enumerate(candidates),
            key=lambda item: _comment_recommendation_rank(item[0], pool_size, item[1], seed),
            reverse=True,
        )
    ]
    return candidates[skip:skip + limit]


def _resolve_thread_root_id(comment: Comment, db: Session) -> int:
    if comment.parent_id is None:
        return comment.id
    if comment.root_comment_id is not None:
        return comment.root_comment_id

    seen = {comment.id}
    parent_id = comment.parent_id
    while parent_id is not None and parent_id not in seen:
        parent = db.query(Comment.id, Comment.parent_id).filter(Comment.id == parent_id).first()
        if parent is None:
            return parent_id
        if parent.parent_id is None:
            return parent.id
        seen.add(parent.id)
        parent_id = parent.parent_id

    return comment.parent_id


def _legacy_descendant_ids_by_root(db: Session, root_ids: List[int]) -> dict[int, set[int]]:
    descendants_by_root = {root_id: set() for root_id in root_ids}
    seen_by_root = {root_id: {root_id} for root_id in root_ids}
    frontier_by_root = {root_id: {root_id} for root_id in root_ids}

    while True:
        parent_to_root = {
            parent_id: root_id
            for root_id, parent_ids in frontier_by_root.items()
            for parent_id in parent_ids
        }
        if not parent_to_root:
            break

        rows = db.query(Comment.id, Comment.parent_id).filter(
            Comment.parent_id.in_(parent_to_root.keys())
        ).all()
        next_frontier_by_root: dict[int, set[int]] = defaultdict(set)

        for comment_id, parent_id in rows:
            root_id = parent_to_root.get(parent_id)
            if root_id is None or comment_id in seen_by_root[root_id]:
                continue
            seen_by_root[root_id].add(comment_id)
            descendants_by_root[root_id].add(comment_id)
            next_frontier_by_root[root_id].add(comment_id)

        frontier_by_root = dict(next_frontier_by_root)

    return descendants_by_root


def _reply_ids_by_thread_root(db: Session, root_ids: List[int]) -> dict[int, set[int]]:
    reply_ids_by_root = {root_id: set() for root_id in root_ids}
    if not root_ids:
        return reply_ids_by_root

    for comment_id, root_comment_id in db.query(Comment.id, Comment.root_comment_id).filter(
        Comment.root_comment_id.in_(root_ids)
    ).all():
        reply_ids_by_root[root_comment_id].add(comment_id)

    for root_id, legacy_ids in _legacy_descendant_ids_by_root(db, root_ids).items():
        reply_ids_by_root[root_id].update(legacy_ids)

    return reply_ids_by_root


def _set_response_children_empty(comment: Comment) -> None:
    set_committed_value(comment, "children", [])


def create_comment(
    post_id: int,
    user_id: int,
    content: str,
    parent_id: Optional[int],
    db: Session,
    repost: bool = False
) -> Comment:
    """
    创建评论或回复
    
    在数据库事务中创建评论，并更新相关的计数器：
    - 更新帖子的 comment_count
    - 如果是回复，只更新所属一级评论的 reply_count
    
    Args:
        post_id: 帖子 ID
        user_id: 用户 ID
        content: 评论内容
        parent_id: 父评论 ID，为空表示一级评论，有值表示回复
        db: 数据库会话
    
    Returns:
        Comment: 创建成功的评论对象
    
    Raises:
        PostNotFoundError: 当帖子不存在时抛出
        ParentCommentNotFoundError: 当父评论不存在时抛出
        ParentCommentMismatchError: 当父评论不属于指定帖子时抛出
    
    Example:
        >>> comment = create_comment(
        ...     post_id=1,
        ...     user_id=123,
        ...     content="这是一条评论",
        ...     parent_id=None,
        ...     db=session
        ... )
        >>> print(f"评论创建成功，ID: {comment.id}")
    """
    # 检查帖子是否存在
    post = db.query(Post).filter(Post.id == post_id).first()
    if not post:
        raise PostNotFoundError(post_id)
    
    # 如果指定了父评论，检查父评论是否存在且属于同一帖子。
    # parent_id 只表示“回复了哪条评论”；root_comment_id 才表示归属哪个一级评论 thread。
    parent_comment = None
    root_comment = None
    root_comment_id = None
    if parent_id is not None:
        parent_comment = db.query(Comment).filter(Comment.id == parent_id).first()
        if not parent_comment:
            raise ParentCommentNotFoundError(parent_id)
        if parent_comment.post_id != post_id:
            raise ParentCommentMismatchError(parent_id, post_id, parent_comment.post_id)
        root_comment_id = _resolve_thread_root_id(parent_comment, db)
        root_comment = (
            parent_comment
            if parent_comment.id == root_comment_id
            else db.query(Comment).filter(Comment.id == root_comment_id).first()
        )
    
    try:
        # 1. 创建新评论
        new_comment = Comment(
            post_id=post_id,
            owner_id=user_id,
            parent_id=parent_id,
            root_comment_id=root_comment_id,
            content=content,
            like_count=0,
            reply_count=0
        )
        db.add(new_comment)
        db.flush()  # 刷新以获取新评论的 ID
        
        # 2. 更新帖子的评论计数
        post.comment_count = post.comment_count + 1
        # 评论会影响帖子热度，新评论本身也需要立即进入默认评论流。
        heat_service.refresh_post_heat_score(db, post)
        heat_service.refresh_comment_heat_score(db, new_comment)
        
        # 3. 如果是回复，只更新所属一级评论的扁平回复计数。
        if root_comment is not None:
            root_comment.reply_count = root_comment.reply_count + 1
            heat_service.refresh_comment_heat_score(db, root_comment)
        
        notification_service.create_comment_notifications(
            db=db,
            post=post,
            comment=new_comment,
            sender_id=user_id,
            parent_comment=parent_comment,
        )

        if repost:
            repost_service.create_repost(
                db=db,
                user_id=user_id,
                source_type="comment",
                source_id=new_comment.id,
                content=content,
                commit=False,
            )

        # 4. 提交事务
        db.commit()
        db.refresh(new_comment)
        mention_service.attach_mention_users(db, new_comment)
        
        return new_comment
    
    except Exception as e:
        db.rollback()
        raise e


def toggle_like(
    comment_id: int,
    user_id: int,
    db: Session
) -> Tuple[bool, int]:
    """
    切换评论点赞状态（点赞/取消点赞）
    
    在数据库事务中同时执行点赞记录操作和评论计数更新，
    确保数据一致性。任何一步失败都会回滚整个事务。
    
    Args:
        comment_id: 评论 ID
        user_id: 用户 ID
        db: 数据库会话
    
    Returns:
        Tuple[bool, int]: (是否已点赞，当前点赞总数)
        - is_liked: True 表示点赞成功，False 表示取消点赞成功
        - like_count: 操作后的点赞总数
    
    Raises:
        CommentNotFoundError: 当评论不存在时抛出
    
    Example:
        >>> is_liked, like_count = toggle_like(comment_id=1, user_id=123, db=session)
        >>> print(f"点赞状态：{is_liked}, 点赞数：{like_count}")
    """
    # 检查评论是否存在
    comment = db.query(Comment).filter(Comment.id == comment_id).first()
    if not comment:
        raise CommentNotFoundError(comment_id)
    
    # 检查是否已经点赞
    existing_like = db.query(CommentLike).filter(
        CommentLike.user_id == user_id,
        CommentLike.comment_id == comment_id
    ).first()
    
    try:
        if existing_like:
            # 已点赞，执行取消点赞操作
            # 1. 删除点赞记录
            db.delete(existing_like)
            # 2. 减少评论点赞计数（确保不会减到负数）
            comment.like_count = max(0, comment.like_count - 1)
            heat_service.refresh_comment_heat_score(db, comment)
            # 3. 提交事务
            db.commit()
            db.refresh(comment)
            # 返回：已取消点赞，新的点赞数
            return (False, comment.like_count)
        else:
            # 未点赞，执行点赞操作
            # 1. 创建点赞记录
            new_like = CommentLike(user_id=user_id, comment_id=comment_id)
            db.add(new_like)
            # 2. 增加评论点赞计数
            comment.like_count = comment.like_count + 1
            heat_service.refresh_comment_heat_score(db, comment)
            notification_service.create_comment_like_notification(db, comment, user_id)
            # 3. 提交事务
            db.commit()
            db.refresh(comment)
            # 返回：已点赞，新的点赞数
            return (True, comment.like_count)
    
    except IntegrityError:
        # 数据库完整性错误（如复合主键冲突）
        db.rollback()
        # 重新查询状态
        comment = db.query(Comment).filter(Comment.id == comment_id).first()
        like_exists = db.query(CommentLike).filter(
            CommentLike.user_id == user_id,
            CommentLike.comment_id == comment_id
        ).first() is not None
        return (like_exists, comment.like_count if comment else 0)


def get_like_status(
    comment_id: int,
    user_id: int,
    db: Session
) -> Tuple[bool, int]:
    """
    获取评论点赞状态
    
    查询指定用户对指定评论的点赞状态和评论的总点赞数。
    
    Args:
        comment_id: 评论 ID
        user_id: 用户 ID
        db: 数据库会话
    
    Returns:
        Tuple[bool, int]: (是否已点赞，当前点赞总数)
        - is_liked: 当前用户是否已点赞该评论
        - like_count: 评论的总点赞数
    
    Raises:
        CommentNotFoundError: 当评论不存在时抛出
    
    Example:
        >>> is_liked, like_count = get_like_status(comment_id=1, user_id=123, db=session)
        >>> if is_liked:
        ...     print("您已点赞此评论")
    """
    # 检查评论是否存在
    comment = db.query(Comment).filter(Comment.id == comment_id).first()
    if not comment:
        raise CommentNotFoundError(comment_id)
    
    # 查询用户是否已点赞
    like = db.query(CommentLike).filter(
        CommentLike.user_id == user_id,
        CommentLike.comment_id == comment_id
    ).first()
    
    # 返回：是否已点赞，评论总点赞数
    return (like is not None, comment.like_count)


def get_comment_tree(
    post_id: int,
    user_id: Optional[int],
    skip: int,
    limit: int,
    db: Session,
    sort: str = "default",
    seed: Optional[str] = None,
) -> Tuple[List[Comment], int]:
    """
    获取帖子的一级评论
    
    查询指定帖子的一级评论列表。回复通过 replies 接口按一级评论 thread 扁平分页加载。
    
    Args:
        post_id: 帖子 ID
        user_id: 当前用户 ID（用于判断点赞状态），可为空
        skip: 跳过的数量（分页）
        limit: 返回的最大数量（分页）
        db: 数据库会话
    
    Returns:
        Tuple[List[Comment], int]: (评论列表，总数)
        - 评论列表：一级评论对象列表，每个评论的 children 为空
        - 总数：帖子下一级评论总数
    
    Raises:
        PostNotFoundError: 当帖子不存在时抛出
    
    Example:
        >>> comments, total = get_comment_tree(
        ...     post_id=1,
        ...     user_id=123,
        ...     skip=0,
        ...     limit=20,
        ...     db=session
        ... )
        >>> print(f"共 {total} 条评论，本次返回 {len(comments)} 条一级评论")
    """
    sort = _normalize_comment_sort(sort)
    seed = _normalize_seed(seed)

    # 检查帖子是否存在
    post_exists = db.query(Post.id).filter(Post.id == post_id).first()
    if not post_exists:
        raise PostNotFoundError(post_id)
    
    root_query = db.query(Comment).filter(
        Comment.post_id == post_id,
        Comment.parent_id == None
    )
    root_total = root_query.count()

    # 查询一级评论（parent_id IS NULL）。回复由 /comments/{comment_id}/replies 按需分页加载。
    # 默认流先取 Top-N 候选池，再用本次浏览 seed 在候选池内轻量重排。
    root_comments = _get_comments_for_tree(
        query=root_query.options(joinedload(Comment.owner)),
        skip=skip,
        limit=limit,
        total=root_total,
        sort=sort,
        seed=seed,
    )
    
    # 如果没有一级评论，直接返回
    if not root_comments:
        return ([], root_total)
    
    # 获取所有一级评论的 ID
    root_comment_ids = [c.id for c in root_comments]
    mention_service.attach_mention_users_for_items(db, root_comments)

    for root_comment in root_comments:
        set_committed_value(root_comment, "reply_count", root_comment.reply_count or 0)
        _set_response_children_empty(root_comment)
    
    # 如果提供了 user_id，注入点赞状态
    if user_id is not None:
        # 批量查询用户的点赞记录
        liked_comment_ids = set(
            row[0] for row in db.query(CommentLike.comment_id).filter(
                CommentLike.user_id == user_id,
                CommentLike.comment_id.in_(root_comment_ids)
            ).all()
        )
        
        # 为每个评论设置点赞状态
        for root_comment in root_comments:
            root_comment.is_liked = root_comment.id in liked_comment_ids
    
    return (root_comments, root_total)


def get_comment_replies(
    post_id: int,
    comment_id: int,
    user_id: Optional[int],
    skip: int,
    limit: int,
    db: Session,
    sort: str = "default",
    seed: str = "default",
) -> Tuple[List[Comment], int]:
    """获取所属一级评论 thread 下的扁平回复列表。"""
    sort = _normalize_comment_sort(sort)
    seed = _normalize_seed(seed)

    parent = db.query(Comment).filter(Comment.id == comment_id).first()
    if not parent:
        raise CommentNotFoundError(comment_id)
    if parent.post_id != post_id:
        raise ParentCommentMismatchError(comment_id, post_id, parent.post_id)

    root_comment_id = _resolve_thread_root_id(parent, db)
    reply_ids = _reply_ids_by_thread_root(db, [root_comment_id]).get(root_comment_id, set())
    replies_query = db.query(Comment).filter(
        Comment.post_id == post_id,
        Comment.id.in_(reply_ids),
    )
    total = replies_query.count()
    replies = _get_comments_for_tree(
        query=replies_query.options(
            joinedload(Comment.owner),
            joinedload(Comment.parent).joinedload(Comment.owner),
        ),
        skip=skip,
        limit=limit,
        total=total,
        sort=sort,
        seed=seed,
    )

    if not replies:
        return ([], total)

    mention_service.attach_mention_users_for_items(db, replies)

    for reply in replies:
        _set_response_children_empty(reply)

    if user_id is not None:
        reply_ids = [reply.id for reply in replies]

        liked_comment_ids = set(
            row[0] for row in db.query(CommentLike.comment_id).filter(
                CommentLike.user_id == user_id,
                CommentLike.comment_id.in_(reply_ids)
            ).all()
        )

        for reply in replies:
            reply.is_liked = reply.id in liked_comment_ids

    return (replies, total)


def get_comment_by_id(
    comment_id: int,
    user_id: Optional[int],
    db: Session
) -> Optional[Comment]:
    """
    根据 ID 获取评论详情
    
    Args:
        comment_id: 评论 ID
        user_id: 当前用户 ID（用于判断点赞状态），可为空
        db: 数据库会话
    
    Returns:
        Optional[Comment]: 评论对象，不存在则返回 None
        评论对象的 is_liked 属性表示当前用户是否已点赞
    
    Example:
        >>> comment = get_comment_by_id(comment_id=1, user_id=123, db=session)
        >>> if comment:
        ...     print(f"评论内容：{comment.content}")
    """
    comment = db.query(Comment).options(
        joinedload(Comment.owner),
        joinedload(Comment.parent).joinedload(Comment.owner),
    ).filter(Comment.id == comment_id).first()
    if not comment:
        return None

    mention_service.attach_mention_users(db, comment)

    if comment.parent_id is not None and comment.root_comment_id is None:
        set_committed_value(
            comment,
            "root_comment_id",
            _resolve_thread_root_id(comment, db),
        )
    
    # 如果提供了 user_id，注入点赞状态
    if user_id is not None:
        like = db.query(CommentLike).filter(
            CommentLike.user_id == user_id,
            CommentLike.comment_id == comment_id
        ).first()
        comment.is_liked = like is not None
    else:
        comment.is_liked = False
    
    return comment


def _get_descendant_comment_ids(comment_id: int, db: Session) -> List[int]:
    return list(_reply_ids_by_thread_root(db, [comment_id]).get(comment_id, set()))


def delete_comment(
    comment_id: int,
    user_id: int,
    db: Session
) -> bool:
    """
    删除评论
    
    删除评论并更新相关的计数器：
    - 更新帖子的 comment_count
    - 更新所属一级评论的 reply_count
    
    Args:
        comment_id: 评论 ID
        user_id: 用户 ID（用于权限验证）
        db: 数据库会话
    
    Returns:
        bool: 删除成功返回 True，评论不存在返回 False
    
    Raises:
        CommentNotFoundError: 当评论不存在时抛出
        PermissionError: 当用户无权删除评论时抛出
    
    Example:
        >>> success = delete_comment(comment_id=1, user_id=123, db=session)
        >>> if success:
        ...     print("评论删除成功")
    """
    comment = db.query(Comment).filter(Comment.id == comment_id).first()
    if not comment:
        raise CommentNotFoundError(comment_id)
    
    # 权限验证：只有评论作者可以删除
    if comment.owner_id != user_id:
        raise PermissionError(f"用户 (ID: {user_id}) 无权删除评论 (ID: {comment_id})")
    
    try:
        post_id = comment.post_id
        parent_id = comment.parent_id
        root_comment_id = (
            _resolve_thread_root_id(comment, db) if parent_id is not None else None
        )
        
        if parent_id is None:
            reply_ids = _get_descendant_comment_ids(comment_id, db)
            reply_count_to_subtract = 1 + len(reply_ids)
        else:
            reply_count_to_subtract = 1
            db.query(Comment).filter(Comment.parent_id == comment_id).update(
                {Comment.parent_id: parent_id},
                synchronize_session=False
            )
            db.flush()
        
        # 1. 删除评论。一级评论删除会级联删除 thread 下的回复；单条回复删除前会转移语义回复指针。
        db.delete(comment)
        
        # 2. 更新帖子的评论计数
        post = db.query(Post).filter(Post.id == post_id).first()
        if post:
            post.comment_count = max(0, post.comment_count - reply_count_to_subtract)
            heat_service.refresh_post_heat_score(db, post)
        
        # 3. 回复被删除时，只更新所属一级评论的扁平回复计数。
        if root_comment_id is not None:
            root = db.query(Comment).filter(Comment.id == root_comment_id).first()
            if root:
                root.reply_count = max(0, root.reply_count - 1)
                heat_service.refresh_comment_heat_score(db, root)
        
        # 4. 提交事务
        db.commit()
        
        return True
    
    except Exception as e:
        db.rollback()
        raise e


def delete_comment_precise(
    comment_id: int,
    user_id: int,
    db: Session
) -> bool:
    comment = db.query(Comment).filter(Comment.id == comment_id).first()
    if not comment:
        raise CommentNotFoundError(comment_id)

    if comment.owner_id != user_id:
        raise PermissionError(f"User (ID: {user_id}) cannot delete comment (ID: {comment_id})")

    try:
        post_id = comment.post_id
        parent_id = comment.parent_id
        root_comment_id = (
            _resolve_thread_root_id(comment, db) if parent_id is not None else None
        )

        if parent_id is None:
            count_to_subtract = 1 + len(_get_descendant_comment_ids(comment_id, db))
        else:
            count_to_subtract = 1
            db.query(Comment).filter(Comment.parent_id == comment_id).update(
                {Comment.parent_id: parent_id},
                synchronize_session=False
            )
            db.flush()

        db.delete(comment)

        post = db.query(Post).filter(Post.id == post_id).first()
        if post:
            post.comment_count = max(0, post.comment_count - count_to_subtract)
            heat_service.refresh_post_heat_score(db, post)

        if parent_id is not None:
            root = db.query(Comment).filter(Comment.id == root_comment_id).first()
            if root:
                root.reply_count = max(0, root.reply_count - count_to_subtract)
                heat_service.refresh_comment_heat_score(db, root)

        db.commit()
        return True
    except Exception:
        db.rollback()
        raise
