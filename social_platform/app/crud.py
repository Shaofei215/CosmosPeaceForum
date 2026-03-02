"""
CRUD操作模块
提供所有数据库操作的封装函数
"""
from sqlalchemy.orm import Session
from sqlalchemy import desc
from typing import List, Optional

from app import models, schemas


def create_user(db: Session, user: schemas.UserCreate) -> models.User:
    """创建新用户"""
    db_user = models.User(username=user.username, bio=user.bio)
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user


def get_user(db: Session, user_id: int) -> Optional[models.User]:
    """根据ID获取用户"""
    return db.query(models.User).filter(models.User.id == user_id).first()


def get_user_by_username(db: Session, username: str) -> Optional[models.User]:
    """根据用户名获取用户"""
    return db.query(models.User).filter(models.User.username == username).first()


def get_users(db: Session, skip: int = 0, limit: int = 100) -> List[models.User]:
    """获取用户列表"""
    return db.query(models.User).offset(skip).limit(limit).all()


def create_post(db: Session, post: schemas.PostCreate, author_id: int) -> models.Post:
    """创建新帖子"""
    db_post = models.Post(author_id=author_id, content=post.content)
    db.add(db_post)
    db.commit()
    db.refresh(db_post)
    return db_post


def get_post(db: Session, post_id: int) -> Optional[models.Post]:
    """根据ID获取帖子"""
    return db.query(models.Post).filter(models.Post.id == post_id).first()


def get_posts(db: Session, skip: int = 0, limit: int = 50) -> List[models.Post]:
    """获取帖子列表（全局时间线）"""
    return (
        db.query(models.Post)
        .order_by(desc(models.Post.created_at))
        .offset(skip)
        .limit(limit)
        .all()
    )


def get_user_posts(db: Session, user_id: int, skip: int = 0, limit: int = 50) -> List[models.Post]:
    """获取指定用户的帖子"""
    return (
        db.query(models.Post)
        .filter(models.Post.author_id == user_id)
        .order_by(desc(models.Post.created_at))
        .offset(skip)
        .limit(limit)
        .all()
    )


def create_comment(
    db: Session, comment: schemas.CommentCreate, post_id: int, author_id: int
) -> models.Comment:
    """创建新评论"""
    db_comment = models.Comment(
        post_id=post_id, author_id=author_id, content=comment.content
    )
    db.add(db_comment)
    db.commit()
    db.refresh(db_comment)
    return db_comment


def get_post_comments(db: Session, post_id: int) -> List[models.Comment]:
    """获取帖子的评论列表"""
    return (
        db.query(models.Comment)
        .filter(models.Comment.post_id == post_id)
        .order_by(desc(models.Comment.created_at))
        .all()
    )


def get_comment(db: Session, comment_id: int) -> Optional[models.Comment]:
    """获取单个评论"""
    return db.query(models.Comment).filter(models.Comment.id == comment_id).first()


def create_like(db: Session, user_id: int, post_id: int) -> models.Like:
    """创建点赞"""
    existing_like = (
        db.query(models.Like)
        .filter(models.Like.user_id == user_id, models.Like.post_id == post_id)
        .first()
    )
    if existing_like:
        return existing_like

    db_like = models.Like(user_id=user_id, post_id=post_id)
    db.add(db_like)
    db.commit()
    db.refresh(db_like)
    return db_like


def delete_like(db: Session, user_id: int, post_id: int) -> bool:
    """删除点赞"""
    db_like = (
        db.query(models.Like)
        .filter(models.Like.user_id == user_id, models.Like.post_id == post_id)
        .first()
    )
    if db_like:
        db.delete(db_like)
        db.commit()
        return True
    return False


def check_like_exists(db: Session, user_id: int, post_id: int) -> bool:
    """检查用户是否已点赞"""
    return (
        db.query(models.Like)
        .filter(models.Like.user_id == user_id, models.Like.post_id == post_id)
        .first()
        is not None
    )


def create_follow(db: Session, follower_id: int, following_id: int) -> models.Follow:
    """创建关注关系"""
    if follower_id == following_id:
        return None

    existing_follow = (
        db.query(models.Follow)
        .filter(
            models.Follow.follower_id == follower_id,
            models.Follow.following_id == following_id,
        )
        .first()
    )
    if existing_follow:
        return existing_follow

    db_follow = models.Follow(follower_id=follower_id, following_id=following_id)
    db.add(db_follow)
    db.commit()
    db.refresh(db_follow)
    return db_follow


def delete_follow(db: Session, follower_id: int, following_id: int) -> bool:
    """删除关注关系"""
    db_follow = (
        db.query(models.Follow)
        .filter(
            models.Follow.follower_id == follower_id,
            models.Follow.following_id == following_id,
        )
        .first()
    )
    if db_follow:
        db.delete(db_follow)
        db.commit()
        return True
    return False


def check_follow_exists(db: Session, follower_id: int, following_id: int) -> bool:
    """检查是否已关注"""
    return (
        db.query(models.Follow)
        .filter(
            models.Follow.follower_id == follower_id,
            models.Follow.following_id == following_id,
        )
        .first()
        is not None
    )


def get_user_followers(db: Session, user_id: int) -> List[models.User]:
    """获取用户的粉丝列表"""
    follows = db.query(models.Follow).filter(models.Follow.following_id == user_id).all()
    follower_ids = [f.follower_id for f in follows]
    return db.query(models.User).filter(models.User.id.in_(follower_ids)).all()


def get_user_following(db: Session, user_id: int) -> List[models.User]:
    """获取用户关注的列表"""
    follows = db.query(models.Follow).filter(models.Follow.follower_id == user_id).all()
    following_ids = [f.following_id for f in follows]
    return db.query(models.User).filter(models.User.id.in_(following_ids)).all()


def get_user_feed(db: Session, user_id: int, limit: int = 50) -> List[models.Post]:
    """获取用户动态（关注用户的帖子）"""
    following_ids = [
        f.following_id
        for f in db.query(models.Follow).filter(models.Follow.follower_id == user_id).all()
    ]

    if not following_ids:
        return []

    return (
        db.query(models.Post)
        .filter(models.Post.author_id.in_(following_ids))
        .order_by(desc(models.Post.created_at))
        .limit(limit)
        .all()
    )
