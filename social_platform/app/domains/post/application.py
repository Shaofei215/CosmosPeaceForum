"""帖子领域应用服务。

该模块承接帖子写操作的事务编排：权限校验、模型变更、热度刷新和领域事件发布。
HTTP 路由只负责参数接收、认证依赖和异常映射。
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from social_platform.app.admin.services.moderation_guard import ensure_action_allowed
from social_platform.app.domains.events import PostCreated, PostDeleted, PostUpdated
from social_platform.app.models.comment import Comment
from social_platform.app.models.like import Like
from social_platform.app.models.post import Post
from social_platform.app.models.user import User
from social_platform.app.schemas.post import PostCreate, PostUpdate, RepostCreate
from social_platform.app.services import heat_service, repost_service
from social_platform.app.shared.events import publish_domain_event
from social_platform.app.shared.unit_of_work import commit_session



class ArticleTitleRequiredError(Exception):
    """文章标题缺失异常。"""

    def __init__(self) -> None:
        super().__init__("Article title is required")


class PostNotFoundError(Exception):
    """帖子不存在异常。

    Args:
        post_id: 不存在的帖子 ID。
    """

    def __init__(self, post_id: int) -> None:
        self.post_id = post_id
        super().__init__("帖子不存在")


class PostPermissionError(Exception):
    """帖子权限异常。"""

    def __init__(self, message: str) -> None:
        super().__init__(message)


def create_post(db: Session, current_user: User, post_data: PostCreate) -> Post:
    """创建帖子并发布帖子创建事件。

    Args:
        db: 当前数据库会话。
        current_user: 当前登录用户。
        post_data: 帖子创建请求数据。

    Returns:
        Post: 创建后的帖子对象。

    Raises:
        ArticleTitleRequiredError: 当文章类型帖子缺少标题时抛出。
    """

    ensure_action_allowed(db, current_user, "publish")
    if post_data.type == "article" and not (post_data.title or "").strip():
        raise ArticleTitleRequiredError()

    post = Post(
        author_id=current_user.id,
        title=post_data.title,
        type=post_data.type,
        content=post_data.content,
    )
    db.add(post)
    db.flush()
    heat_service.refresh_post_heat_score(db, post)
    publish_domain_event(db, PostCreated(post_id=post.id, author_id=current_user.id))
    commit_session(db)
    db.refresh(post)
    return post


def create_repost(db: Session, current_user: User, data: RepostCreate) -> Post:
    """创建转发。

    Args:
        db: 当前数据库会话。
        current_user: 当前登录用户。
        data: 转发请求数据。

    Returns:
        Post: 创建后的转发帖子。
    """

    ensure_action_allowed(db, current_user, "publish")
    ensure_action_allowed(db, current_user, "interaction")
    return repost_service.create_repost(
        db=db,
        user_id=current_user.id,
        source_type=data.source_type,
        source_id=data.source_id,
        content=data.content,
    )


def update_post(db: Session, current_user: User, post_id: int, post_update: PostUpdate) -> Post:
    """更新帖子并发布帖子更新事件。

    Args:
        db: 当前数据库会话。
        current_user: 当前登录用户。
        post_id: 待更新帖子 ID。
        post_update: 更新数据。

    Returns:
        Post: 更新后的帖子对象。

    Raises:
        PostNotFoundError: 当帖子不存在时抛出。
        PostPermissionError: 当当前用户不是作者时抛出。
    """

    post = db.query(Post).filter(Post.id == post_id).first()
    if not post:
        raise PostNotFoundError(post_id)
    if post.author_id != current_user.id:
        raise PostPermissionError("无权修改此帖子")

    update_data = post_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(post, field, value)

    publish_domain_event(db, PostUpdated(post_id=post.id, author_id=post.author_id))
    commit_session(db)
    db.refresh(post)
    repost_service.attach_repost_metadata(db, post)
    return post


def delete_post(db: Session, current_user: User, post_id: int) -> None:
    """删除帖子并发布帖子删除事件。

    Args:
        db: 当前数据库会话。
        current_user: 当前登录用户。
        post_id: 待删除帖子 ID。

    Raises:
        PostNotFoundError: 当帖子不存在时抛出。
        PostPermissionError: 当当前用户不是作者时抛出。
    """

    post = db.query(Post).filter(Post.id == post_id).first()
    if not post:
        raise PostNotFoundError(post_id)
    if post.author_id != current_user.id:
        raise PostPermissionError("无权删除此帖子")

    author_id = post.author_id
    db.query(Post).filter(Post.repost_root_post_id == post_id).update(
        {Post.repost_root_post_id: None},
        synchronize_session=False,
    )
    db.query(Like).filter(Like.post_id == post_id).delete(synchronize_session=False)
    db.query(Comment).filter(Comment.post_id == post_id).delete(synchronize_session=False)
    db.delete(post)
    publish_domain_event(db, PostDeleted(post_id=post_id, author_id=author_id))
    commit_session(db)
