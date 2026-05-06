import re
from typing import Optional, Tuple

from sqlalchemy.orm import Session, joinedload

from app_platform.app.models.comment import Comment
from app_platform.app.models.post import Post
from app_platform.app.models.user import User
from app_platform.app.services import notification_service


class RepostSourceNotFoundError(Exception):
    def __init__(self, source_type: str, source_id: int):
        super().__init__(f"Repost source not found: {source_type} {source_id}")


class InvalidRepostSourceError(Exception):
    def __init__(self, source_type: str):
        super().__init__(f"Invalid repost source type: {source_type}")


def create_repost(
    db: Session,
    user_id: int,
    source_type: str,
    source_id: int,
    content: Optional[str] = None,
    commit: bool = True,
) -> Post:
    source_type = source_type.lower()
    if source_type not in {"post", "comment"}:
        raise InvalidRepostSourceError(source_type)

    if source_type == "post":
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
        repost_source_type=source_type,
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

    notification_service.create_repost_notifications(
        db=db,
        root_post=root_post,
        repost=repost,
        sender_id=user_id,
        source_post=source_post,
        source_comment=source_comment,
        source_content=chain_content,
    )

    if commit:
        db.commit()
        db.refresh(repost)

    repost.repost_origin = root_post
    repost.repost_chain_authors = build_repost_chain_authors(db, repost.content)
    return repost


def attach_repost_metadata(db: Session, post: Post) -> Post:
    post.repost_origin = post.repost_root_post if post.repost_root_post_id else None
    post.repost_chain_authors = build_repost_chain_authors(db, post.content)
    return post


def attach_repost_origin(post: Post) -> Post:
    post.repost_origin = post.repost_root_post if post.repost_root_post_id else None
    return post


def build_repost_chain_authors(db: Session, content: str) -> list[dict[str, object]]:
    usernames = list(dict.fromkeys(re.findall(r"@([^:\s/]+)", content or "")))
    if not usernames:
        return []

    users = db.query(User).filter(User.username.in_(usernames)).all()
    user_by_name = {user.username: user for user in users}
    return [
        {"user_id": user_by_name[username].id, "username": username}
        for username in usernames
        if username in user_by_name
    ]


def _build_post_repost(
    db: Session,
    post_id: int,
    content: Optional[str],
) -> Tuple[Post, str, Post, None]:
    source_post = db.query(Post).options(
        joinedload(Post.author),
        joinedload(Post.repost_root_post).joinedload(Post.author),
    ).filter(Post.id == post_id).first()
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
    content: Optional[str],
) -> Tuple[Post, str, Post, Comment]:
    source_comment = db.query(Comment).options(
        joinedload(Comment.owner),
        joinedload(Comment.post).joinedload(Post.author),
        joinedload(Comment.post).joinedload(Post.repost_root_post).joinedload(Post.author),
    ).filter(Comment.id == comment_id).first()
    if not source_comment:
        raise RepostSourceNotFoundError("comment", comment_id)

    source_post = source_comment.post
    root_post = source_post.repost_root_post if source_post.repost_root_post_id else source_post
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
    username = post.author.username if post.author else f"user{post.author_id}"
    return f"@{username}: {post.content}"


def _format_comment_segment(comment: Comment) -> str:
    username = comment.owner.username if comment.owner else f"user{comment.owner_id}"
    return f"@{username}: {comment.content}"


def _clean_content(content: Optional[str]) -> str:
    return content.strip() if content and content.strip() else ""
