"""帖子点赞与点踩应用服务。"""

from dataclasses import dataclass
from datetime import timedelta

from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from typing import Tuple

from social_platform.app.core.config import get_settings
from social_platform.app.core.timezone import local_now
from social_platform.app.domains.notification.system import create_user_moderation_notice
from social_platform.app.domains.post import application as post_service
from social_platform.app.domains.post.events import PostDeleted
from social_platform.app.domains.post.models import Post
from social_platform.app.domains.reaction.events import DislikeChanged, LikeChanged
from social_platform.app.domains.reaction.models import Dislike, Like
from social_platform.app.domains.user.models import User
from social_platform.app.shared.events import publish_domain_event
from social_platform.app.shared.unit_of_work import commit_session, rollback_session


MAX_DISLIKES_PER_MINUTE = 10



class PostNotFoundError(Exception):
    """
    自定义异常：帖子不存在
    
    当尝试对不存在的帖子进行点赞操作时抛出此异常
    """
    def __init__(self, post_id: int):
        """
        初始化异常
        
        Args:
            post_id: 不存在的帖子 ID
        """
        self.post_id = post_id
        super().__init__(f"帖子不存在 (ID: {post_id})")


class DuplicateLikeError(Exception):
    """
    自定义异常：重复点赞
    
    当检测到重复点赞时抛出此异常
    注：由于数据库复合主键约束，实际上不会发生此情况
    """
    def __init__(self, user_id: int, post_id: int):
        """
        初始化异常
        
        Args:
            user_id: 用户 ID
            post_id: 帖子 ID
        """
        self.user_id = user_id
        self.post_id = post_id
        super().__init__(f"重复点赞 (用户：{user_id}, 帖子：{post_id})")


class SelfDislikeError(Exception):
    """用户不能给自己的帖子点踩。"""


class DuplicateDislikeError(Exception):
    """并发请求产生了重复点踩关系。"""


class DislikeRateLimitError(Exception):
    """用户在短时间内点踩过于频繁。"""


@dataclass(frozen=True)
class DislikeToggleResult:
    """帖子点踩切换后的完整状态。"""

    is_disliked: bool
    dislike_count: int
    is_liked: bool
    like_count: int
    archived: bool
    created_by_agent: bool = False


def toggle_like(
    post_id: int,
    user_id: int,
    db: Session,
    created_by_agent: bool = False,
) -> Tuple[bool, int]:
    """
    切换点赞状态（点赞/取消点赞）
    
    在数据库事务中同时执行点赞记录操作和帖子计数更新，
    确保数据一致性。任何一步失败都会回滚整个事务。
    
    Args:
        post_id: 帖子 ID
        user_id: 用户 ID
        db: 数据库会话
    
    Returns:
        Tuple[bool, int]: (是否已点赞，当前点赞总数)
        - is_liked: True 表示点赞成功，False 表示取消点赞成功
        - like_count: 操作后的点赞总数
    
    Raises:
        PostNotFoundError: 当帖子不存在时抛出
    
    Example:
        >>> is_liked, like_count = toggle_like(post_id=1, user_id=123, db=session)
        >>> print(f"点赞状态：{is_liked}, 点赞数：{like_count}")
    """
    # 检查帖子是否存在
    post = (
        db.query(Post)
        .filter(Post.id == post_id, Post.moderation_status == "active")
        .with_for_update()
        .first()
    )
    if not post:
        raise PostNotFoundError(post_id)
    
    # 检查是否已经点赞
    existing_like = db.query(Like).filter(
        Like.user_id == user_id,
        Like.post_id == post_id
    ).first()
    
    try:
        if existing_like:
            # 已点赞，执行取消点赞操作
            # 1. 删除点赞记录
            db.delete(existing_like)
            # 2. 减少帖子点赞计数（确保不会减到负数）
            post.like_count = max(0, post.like_count - 1)
            publish_domain_event(
                db,
                LikeChanged(
                    target_type="post",
                    target_id=post_id,
                    actor_id=user_id,
                    owner_id=post.author_id,
                    previous_state=True,
                    current_state=False,
                    post_id=post_id,
                    created_by_agent=existing_like.created_by_agent,
                ),
            )
            # 3. 提交事务
            commit_session(db)
            # 返回：已取消点赞，新的点赞数
            return (False, post.like_count)
        else:
            # 未点赞，执行点赞操作
            existing_dislike = db.query(Dislike).filter(
                Dislike.user_id == user_id,
                Dislike.post_id == post_id,
            ).first()
            if existing_dislike is not None:
                db.delete(existing_dislike)
                post.dislike_count = max(0, post.dislike_count - 1)
                publish_domain_event(
                    db,
                    DislikeChanged(
                        post_id=post_id,
                        actor_id=user_id,
                        owner_id=post.author_id,
                        previous_state=True,
                        current_state=False,
                        created_by_agent=existing_dislike.created_by_agent,
                    ),
                )
            # 1. 创建点赞记录
            new_like = Like(
                user_id=user_id,
                post_id=post_id,
                created_by_agent=created_by_agent,
            )
            db.add(new_like)
            # 2. 增加帖子点赞计数
            post.like_count = post.like_count + 1
            publish_domain_event(
                db,
                LikeChanged(
                    target_type="post",
                    target_id=post_id,
                    actor_id=user_id,
                    owner_id=post.author_id,
                    previous_state=False,
                    current_state=True,
                    post_id=post_id,
                    created_by_agent=created_by_agent,
                ),
            )
            # 3. 提交事务
            commit_session(db)
            # 返回：已点赞，新的点赞数
            return (True, post.like_count)
    
    except IntegrityError as e:
        # 数据库完整性错误（如复合主键冲突）
        rollback_session(db)
        # 抛出重复点赞异常
        raise DuplicateLikeError(user_id, post_id) from e


def toggle_dislike(
    post_id: int,
    user_id: int,
    db: Session,
    *,
    created_by_agent: bool = False,
    archive_threshold: int | None = None,
) -> DislikeToggleResult:
    """切换帖子点踩状态，并在达到阈值时自动归档帖子。

    Args:
        post_id: 目标帖子 ID。
        user_id: 当前认证用户 ID。
        db: 当前数据库会话。
        created_by_agent: 操作是否来自可信 Agent 通道。
        archive_threshold: 测试或内部调用覆盖的归档阈值；为空时读取平台配置。

    Returns:
        DislikeToggleResult: 点踩、点赞、计数和自动归档状态。

    Raises:
        PostNotFoundError: 帖子不存在或已归档。
        SelfDislikeError: 用户尝试给自己的帖子点踩。
        DuplicateDislikeError: 并发请求产生重复关系。
        DislikeRateLimitError: 用户一分钟内新增点踩达到安全上限。
    """

    post = (
        db.query(Post)
        .filter(Post.id == post_id, Post.moderation_status == "active")
        .with_for_update()
        .first()
    )
    if post is None:
        raise PostNotFoundError(post_id)
    if post.author_id == user_id:
        raise SelfDislikeError("不能给自己的帖子点踩")

    existing_dislike = db.query(Dislike).filter(
        Dislike.user_id == user_id,
        Dislike.post_id == post_id,
    ).first()

    if existing_dislike is None:
        # 锁定认证用户行，让同一账号跨帖子的并发新增点踩依次执行。
        db.query(User.id).filter(User.id == user_id).with_for_update().first()
        recent_dislike_count = db.query(Dislike).filter(
            Dislike.user_id == user_id,
            Dislike.created_at >= local_now() - timedelta(minutes=1),
        ).count()
        if recent_dislike_count >= MAX_DISLIKES_PER_MINUTE:
            raise DislikeRateLimitError("点踩过于频繁，请稍后再试")

    try:
        if existing_dislike is not None:
            db.delete(existing_dislike)
            post.dislike_count = max(0, post.dislike_count - 1)
            publish_domain_event(
                db,
                DislikeChanged(
                    post_id=post_id,
                    actor_id=user_id,
                    owner_id=post.author_id,
                    previous_state=True,
                    current_state=False,
                    created_by_agent=existing_dislike.created_by_agent,
                ),
            )
            commit_session(db)
            return DislikeToggleResult(
                is_disliked=False,
                dislike_count=post.dislike_count,
                is_liked=False,
                like_count=post.like_count,
                archived=False,
            )

        existing_like = db.query(Like).filter(
            Like.user_id == user_id,
            Like.post_id == post_id,
        ).first()
        if existing_like is not None:
            db.delete(existing_like)
            post.like_count = max(0, post.like_count - 1)
            publish_domain_event(
                db,
                LikeChanged(
                    target_type="post",
                    target_id=post_id,
                    actor_id=user_id,
                    owner_id=post.author_id,
                    previous_state=True,
                    current_state=False,
                    post_id=post_id,
                    created_by_agent=existing_like.created_by_agent,
                ),
            )

        relation = Dislike(
            user_id=user_id,
            post_id=post_id,
            created_by_agent=created_by_agent,
        )
        db.add(relation)
        db.flush()
        post.dislike_count += 1
        publish_domain_event(
            db,
            DislikeChanged(
                post_id=post_id,
                actor_id=user_id,
                owner_id=post.author_id,
                previous_state=False,
                current_state=True,
                created_by_agent=created_by_agent,
            ),
        )

        threshold = archive_threshold or get_settings().POST_DISLIKE_ARCHIVE_THRESHOLD
        archived = post.dislike_count >= threshold
        if archived:
            if post.repost_source_type:
                post_service.adjust_repost_counts(db, post, -1)
            post.moderation_status = "archived"
            post.archived_at = local_now()
            post.archived_by_admin_id = None
            post.archive_reason = f"点踩人数达到自动删除阈值（{threshold}）"
            create_user_moderation_notice(
                db,
                post.author_id,
                f"你的帖子因收到 {post.dislike_count} 次点踩，已被系统自动删除。如有异议，请联系管理员申诉。",
            )
            publish_domain_event(db, PostDeleted(post_id=post.id, author_id=post.author_id))

        commit_session(db)
        return DislikeToggleResult(
            is_disliked=True,
            dislike_count=post.dislike_count,
            is_liked=False,
            like_count=post.like_count,
            archived=archived,
            created_by_agent=created_by_agent,
        )
    except IntegrityError as exc:
        rollback_session(db)
        raise DuplicateDislikeError("重复点踩") from exc


def get_dislike_status(post_id: int, user_id: int, db: Session) -> tuple[bool, int, bool]:
    """读取当前用户的帖子点踩状态、总数及 Agent 来源。"""

    post = db.query(Post).filter(
        Post.id == post_id,
        Post.moderation_status == "active",
    ).first()
    if post is None:
        raise PostNotFoundError(post_id)
    relation = db.query(Dislike).filter(
        Dislike.user_id == user_id,
        Dislike.post_id == post_id,
    ).first()
    return relation is not None, post.dislike_count, bool(relation and relation.created_by_agent)


def get_user_dislike_status(
    db: Session,
    post_ids: list[int],
    user_id: int | None,
) -> dict[int, bool]:
    """批量读取当前用户对帖子列表的点踩状态。"""

    if user_id is None or not post_ids:
        return {post_id: False for post_id in post_ids}
    disliked_ids = {
        row[0]
        for row in db.query(Dislike.post_id).filter(
            Dislike.user_id == user_id,
            Dislike.post_id.in_(post_ids),
        ).all()
    }
    return {post_id: post_id in disliked_ids for post_id in post_ids}


def get_like_status(
    post_id: int,
    user_id: int,
    db: Session
) -> Tuple[bool, int]:
    """
    获取点赞状态
    
    查询指定用户对指定帖子的点赞状态和帖子的总点赞数。
    
    Args:
        post_id: 帖子 ID
        user_id: 用户 ID
        db: 数据库会话
    
    Returns:
        Tuple[bool, int]: (是否已点赞，当前点赞总数)
        - is_liked: 当前用户是否已点赞该帖子
        - like_count: 帖子的总点赞数
    
    Raises:
        PostNotFoundError: 当帖子不存在时抛出
    
    Example:
        >>> is_liked, like_count = get_like_status(post_id=1, user_id=123, db=session)
        >>> if is_liked:
        ...     print("您已点赞此帖子")
    """
    # 检查帖子是否存在
    post = db.query(Post).filter(Post.id == post_id, Post.moderation_status == "active").first()
    if not post:
        raise PostNotFoundError(post_id)
    
    # 查询用户是否已点赞
    like = db.query(Like).filter(
        Like.user_id == user_id,
        Like.post_id == post_id
    ).first()
    
    # 返回：是否已点赞，帖子总点赞数
    return (like is not None, post.like_count)


def get_post_like_count(
    post_id: int,
    db: Session
) -> int:
    """
    获取帖子的点赞数
    
    Args:
        post_id: 帖子 ID
        db: 数据库会话
    
    Returns:
        int: 帖子的点赞总数
    
    Raises:
        PostNotFoundError: 当帖子不存在时抛出
    """
    post = db.query(Post).filter(Post.id == post_id, Post.moderation_status == "active").first()
    if not post:
        raise PostNotFoundError(post_id)
    
    return post.like_count


def is_user_liked(
    post_id: int,
    user_id: int,
    db: Session
) -> bool:
    """
    检查用户是否已点赞指定帖子
    
    Args:
        post_id: 帖子 ID
        user_id: 用户 ID
        db: 数据库会话
    
    Returns:
        bool: True 表示已点赞，False 表示未点赞
    
    Raises:
        PostNotFoundError: 当帖子不存在时抛出
    """
    # 检查帖子是否存在
    post = db.query(Post).filter(Post.id == post_id, Post.moderation_status == "active").first()
    if not post:
        raise PostNotFoundError(post_id)
    
    # 查询点赞记录
    like = db.query(Like).filter(
        Like.user_id == user_id,
        Like.post_id == post_id
    ).first()
    
    return like is not None
