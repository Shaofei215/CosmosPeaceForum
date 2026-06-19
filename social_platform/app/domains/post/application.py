"""帖子领域应用服务。

该模块承接帖子写操作的事务编排：权限校验、模型变更、转发链维护和领域事件发布。
HTTP 路由只负责参数接收、认证依赖和异常映射。
"""

from __future__ import annotations

import re

from sqlalchemy.orm import Session, joinedload

from social_platform.app.admin.services.moderation_guard import ensure_action_allowed
from social_platform.app.domains.comment.models import Comment
from social_platform.app.domains.post import queries as post_queries
from social_platform.app.domains.post.events import (
    PostCreated,
    PostDeleted,
    PostUpdated,
    RepostCreated,
)
from social_platform.app.domains.post.models import Post
from social_platform.app.domains.post.schemas import PostCreate, PostUpdate, RepostCreate
from social_platform.app.domains.reaction.models import Like
from social_platform.app.domains.user.models import User
from social_platform.app.shared.events import publish_domain_event
from social_platform.app.shared.unit_of_work import commit_session


class ArticleTitleRequiredError(Exception):
    """文章标题缺失异常。"""

    def __init__(self) -> None:
        """初始化文章标题缺失异常。"""
        super().__init__("Article title is required")


class PostNotFoundError(Exception):
    """帖子不存在异常。

    Args:
        post_id: 不存在的帖子 ID。
    """

    def __init__(self, post_id: int) -> None:
        """初始化帖子不存在异常。"""
        self.post_id = post_id
        super().__init__("帖子不存在")


class PostPermissionError(Exception):
    """帖子权限异常。"""

    def __init__(self, message: str) -> None:
        """初始化帖子权限异常。"""
        super().__init__(message)


class RepostSourceNotFoundError(Exception):
    """转发源不存在异常。

    Args:
        source_type: 转发源类型，当前支持 ``post`` 和 ``comment``。
        source_id: 转发源 ID。
    """

    def __init__(self, source_type: str, source_id: int) -> None:
        """初始化转发源不存在异常。"""
        self.source_type = source_type
        self.source_id = source_id
        super().__init__(f"Repost source not found: {source_type} {source_id}")


class InvalidRepostSourceError(Exception):
    """非法转发源类型异常。

    Args:
        source_type: 外部传入的转发源类型。
    """

    def __init__(self, source_type: str) -> None:
        """初始化非法转发源类型异常。"""
        self.source_type = source_type
        super().__init__(f"Invalid repost source type: {source_type}")


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
    publish_domain_event(db, PostCreated(post_id=post.id, author_id=current_user.id))
    commit_session(db)
    db.refresh(post)
    return post


def create_repost_for_user(db: Session, current_user: User, data: RepostCreate) -> Post:
    """为当前登录用户创建转发。

    Args:
        db: 当前数据库会话。
        current_user: 当前登录用户。
        data: 转发请求数据。

    Returns:
        Post: 创建后的转发帖子。

    Raises:
        InvalidRepostSourceError: 当转发源类型不受支持时抛出。
        RepostSourceNotFoundError: 当转发源不存在时抛出。
    """

    ensure_action_allowed(db, current_user, "publish")
    ensure_action_allowed(db, current_user, "interaction")
    return create_repost(
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

    post = db.query(Post).filter(Post.id == post_id, Post.moderation_status == "active").first()
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
    post_queries.attach_repost_metadata(db, post)
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

    post = db.query(Post).filter(Post.id == post_id, Post.moderation_status == "active").first()
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


def create_repost(
    db: Session,
    user_id: int,
    source_type: str,
    source_id: int,
    content: str | None = None,
    commit: bool = True,
) -> Post:
    """创建转发帖子并发布转发创建事件。

    Args:
        db: 当前数据库会话。
        user_id: 创建转发的用户 ID。
        source_type: 转发源类型，当前支持 ``post`` 和 ``comment``。
        source_id: 转发源 ID。
        content: 用户输入的转发正文，可为空。
        commit: 是否在本函数内提交事务；评论联动转发会传入 ``False``。

    Returns:
        Post: 创建后的转发帖子。

    Raises:
        InvalidRepostSourceError: 当转发源类型不受支持时抛出。
        RepostSourceNotFoundError: 当转发源不存在时抛出。
    """

    normalized_source_type = source_type.lower()
    if normalized_source_type not in {"post", "comment"}:
        raise InvalidRepostSourceError(normalized_source_type)

    if normalized_source_type == "post":
        root_post, chain_content, source_post, source_comment = _build_post_repost(
            db,
            source_id,
            content,
        )
    else:
        root_post, chain_content, source_post, source_comment = _build_comment_repost(
            db,
            source_id,
            content,
        )

    repost = Post(
        author_id=user_id,
        content=chain_content,
        like_count=0,
        comment_count=0,
        repost_count=0,
        repost_source_type=normalized_source_type,
        repost_source_id=source_id,
        repost_root_post_id=root_post.id,
        repost_chain=chain_content,
    )
    db.add(repost)
    db.flush()

    if source_post is not None:
        source_post.repost_count = (source_post.repost_count or 0) + 1
    if root_post.id != getattr(source_post, "id", None):
        root_post.repost_count = (root_post.repost_count or 0) + 1

    publish_domain_event(
        db,
        RepostCreated(
            root_post_id=root_post.id,
            repost_id=repost.id,
            sender_id=user_id,
            source_post_id=source_post.id if source_post is not None else None,
            source_comment_id=source_comment.id if source_comment is not None else None,
            source_content=chain_content,
        ),
    )

    if commit:
        commit_session(db)
        db.refresh(repost)

    repost.repost_origin = root_post
    repost.repost_chain_authors = post_queries.build_repost_chain_authors(db, repost.content)
    repost.mention_users = post_queries.build_mention_users(db, repost.content)
    return repost


def _build_post_repost(
    db: Session,
    post_id: int,
    content: str | None,
) -> tuple[Post, str, Post, None]:
    """根据源帖子构造转发链正文。

    Args:
        db: 当前数据库会话。
        post_id: 源帖子 ID。
        content: 用户输入的转发正文。

    Returns:
        tuple[Post, str, Post, None]: 根帖、转发链正文、源帖和空评论。

    Raises:
        RepostSourceNotFoundError: 当源帖子不存在时抛出。
    """

    source_post = db.query(Post).options(
        joinedload(Post.author),
        joinedload(Post.repost_root_post).joinedload(Post.author),
    ).filter(Post.id == post_id, Post.moderation_status == "active").first()
    if not source_post:
        raise RepostSourceNotFoundError("post", post_id)

    root_post = source_post.repost_root_post if source_post.repost_root_post_id else source_post
    leading_content = _clean_content(content) or "转发"
    segments = [leading_content]
    if source_post.id != root_post.id:
        segments.append(_format_post_segment(source_post))

    return root_post, " //".join(segments), source_post, None


def _build_comment_repost(
    db: Session,
    comment_id: int,
    content: str | None,
) -> tuple[Post, str, Post, Comment]:
    """根据源评论构造转发链正文。

    Args:
        db: 当前数据库会话。
        comment_id: 源评论 ID。
        content: 用户输入的转发正文。

    Returns:
        tuple[Post, str, Post, Comment]: 根帖、转发链正文、源帖和源评论。

    Raises:
        RepostSourceNotFoundError: 当源评论不存在时抛出。
    """

    source_comment = db.query(Comment).options(
        joinedload(Comment.owner),
        joinedload(Comment.post).joinedload(Post.author),
        joinedload(Comment.post).joinedload(Post.repost_root_post).joinedload(Post.author),
    ).filter(Comment.id == comment_id, Comment.moderation_status == "active").first()
    if not source_comment:
        raise RepostSourceNotFoundError("comment", comment_id)

    source_post = source_comment.post
    if source_post.moderation_status != "active":
        raise RepostSourceNotFoundError("comment", comment_id)
    root_post = source_post.repost_root_post if source_post.repost_root_post_id else source_post
    if root_post.moderation_status != "active":
        raise RepostSourceNotFoundError("comment", comment_id)
    leading_content = _clean_content(content)

    segments = []
    if leading_content:
        segments.append(leading_content)
    skip_source = leading_content == source_comment.content.strip()
    segments.extend(_comment_chain_segments(db, source_comment, skip_source=skip_source))
    if not segments:
        segments.append("转发")

    return root_post, " //".join(segments), source_post, source_comment


def _comment_chain_segments(db: Session, comment: Comment, skip_source: bool = False) -> list[str]:
    """沿评论父链构造转发链片段。

    Args:
        db: 当前数据库会话。
        comment: 源评论。
        skip_source: 是否跳过源评论本身。

    Returns:
        list[str]: 已格式化的评论转发链片段。
    """

    comments = []
    current = comment
    if skip_source and current.parent_id:
        current = db.query(Comment).options(joinedload(Comment.owner)).filter(
            Comment.id == current.parent_id
        ).first()
    elif skip_source:
        current = None
    while current is not None:
        comments.append(current)
        current = db.query(Comment).options(joinedload(Comment.owner)).filter(
            Comment.id == current.parent_id
        ).first() if current.parent_id else None
    return [_format_comment_segment(item) for item in comments]


def _format_post_segment(post: Post) -> str:
    """格式化源帖子在转发链中的展示片段。

    Args:
        post: 源帖子对象。

    Returns:
        str: 转发链展示片段。
    """

    username = post.author.username if post.author else f"user{post.author_id}"
    if getattr(post, "type", "post") == "article":
        title = (post.title or "Untitled").strip()
        excerpt = _excerpt(post.content)
        return f"@{username}: 文章《{title}》 {excerpt}"
    return f"@{username}: {post.content}"


def _format_comment_segment(comment: Comment) -> str:
    """格式化源评论在转发链中的展示片段。

    Args:
        comment: 源评论对象。

    Returns:
        str: 转发链展示片段。
    """

    username = comment.owner.username if comment.owner else f"user{comment.owner_id}"
    return f"@{username}: {comment.content}"


def _clean_content(content: str | None) -> str:
    """清理用户输入的转发正文。

    Args:
        content: 用户输入的转发正文。

    Returns:
        str: 去除首尾空白后的正文；空输入返回空字符串。
    """

    return content.strip() if content and content.strip() else ""


def _excerpt(content: str, max_len: int = 160) -> str:
    """生成文章转发链摘要。

    Args:
        content: 文章正文。
        max_len: 最大摘要长度。

    Returns:
        str: 压缩空白后的文章摘要。
    """

    compact = re.sub(r"\s+", " ", content or "").strip()
    return compact[:max_len] + ("..." if len(compact) > max_len else "")
