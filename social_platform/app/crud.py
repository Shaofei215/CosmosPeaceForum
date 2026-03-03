"""
CRUD操作模块
提供所有数据库操作的封装函数
"""
from sqlalchemy.orm import Session
from sqlalchemy import desc
from typing import List, Optional
from datetime import datetime

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
    """获取帖子列表（按时间倒序）"""
    return (
        db.query(models.Post)
        .order_by(desc(models.Post.created_at))
        .offset(skip)
        .limit(limit)
        .all()
    )


def get_user_posts(db: Session, user_id: int, skip: int = 0, limit: int = 50) -> List[models.Post]:
    """获取用户的帖子列表"""
    return (
        db.query(models.Post)
        .filter(models.Post.author_id == user_id)
        .order_by(desc(models.Post.created_at))
        .offset(skip)
        .limit(limit)
        .all()
    )


def create_comment(db: Session, comment: schemas.CommentCreate, post_id: int, author_id: int) -> models.Comment:
    """创建新评论"""
    db_comment = models.Comment(
        post_id=post_id,
        author_id=author_id,
        content=comment.content
    )
    db.add(db_comment)
    db.commit()
    db.refresh(db_comment)
    return db_comment


def get_comment(db: Session, comment_id: int) -> Optional[models.Comment]:
    """根据ID获取评论"""
    return db.query(models.Comment).filter(models.Comment.id == comment_id).first()


def get_post_comments(db: Session, post_id: int, skip: int = 0, limit: int = 50) -> List[models.Comment]:
    """获取帖子的评论列表"""
    return (
        db.query(models.Comment)
        .filter(models.Comment.post_id == post_id)
        .order_by(desc(models.Comment.created_at))
        .offset(skip)
        .limit(limit)
        .all()
    )


def create_reply(
    db: Session,
    reply: schemas.ReplyCreate,
    comment_id: int,
    author_id: int,
    parent_reply_id: Optional[int] = None
) -> models.Reply:
    """创建新回复（支持楼中楼）"""
    db_reply = models.Reply(
        comment_id=comment_id,
        author_id=author_id,
        content=reply.content,
        parent_reply_id=parent_reply_id or reply.parent_reply_id
    )
    db.add(db_reply)
    db.commit()
    db.refresh(db_reply)
    return db_reply


def get_reply(db: Session, reply_id: int) -> Optional[models.Reply]:
    """根据ID获取回复"""
    return db.query(models.Reply).filter(models.Reply.id == reply_id).first()


def get_comment_replies(db: Session, comment_id: int, skip: int = 0, limit: int = 50) -> List[models.Reply]:
    """获取评论的回复列表"""
    return (
        db.query(models.Reply)
        .filter(models.Reply.comment_id == comment_id)
        .order_by(desc(models.Reply.created_at))
        .offset(skip)
        .limit(limit)
        .all()
    )


def create_like(db: Session, user_id: int, post_id: int) -> models.Like:
    """创建帖子点赞"""
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
    """删除帖子点赞"""
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
    """检查用户是否已点赞帖子"""
    return (
        db.query(models.Like)
        .filter(models.Like.user_id == user_id, models.Like.post_id == post_id)
        .first()
        is not None
    )


def create_follow(db: Session, follower_id: int, following_id: int) -> models.Follow:
    """创建关注关系"""
    existing_follow = (
        db.query(models.Follow)
        .filter(
            models.Follow.follower_id == follower_id,
            models.Follow.following_id == following_id
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
            models.Follow.following_id == following_id
        )
        .first()
    )
    if db_follow:
        db.delete(db_follow)
        db.commit()
        return True
    return False


def check_follow_exists(db: Session, follower_id: int, following_id: int) -> bool:
    """检查关注关系是否存在"""
    return (
        db.query(models.Follow)
        .filter(
            models.Follow.follower_id == follower_id,
            models.Follow.following_id == following_id
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


# ==================== 已读记录相关操作 ====================

def get_user_read_post_ids(db: Session, user_id: int, limit: int = 1000) -> List[int]:
    """
    获取用户的已读帖子ID列表
    
    Args:
        db: 数据库会话
        user_id: 用户ID
        limit: 最大返回数量（默认1000，防止数据过多）
        
    Returns:
        已读帖子ID列表
    """
    read_records = (
        db.query(models.UserReadPost)
        .filter(models.UserReadPost.user_id == user_id)
        .order_by(desc(models.UserReadPost.read_at))
        .limit(limit)
        .all()
    )
    return [record.post_id for record in read_records]


def mark_post_as_read(db: Session, user_id: int, post_id: int) -> models.UserReadPost:
    """
    标记帖子为已读
    如果已存在则更新时间戳
    
    Args:
        db: 数据库会话
        user_id: 用户ID
        post_id: 帖子ID
        
    Returns:
        已读记录
    """
    # 检查是否已存在
    existing = (
        db.query(models.UserReadPost)
        .filter(
            models.UserReadPost.user_id == user_id,
            models.UserReadPost.post_id == post_id
        )
        .first()
    )
    
    if existing:
        # 更新时间戳
        existing.read_at = datetime.utcnow()
        db.commit()
        db.refresh(existing)
        return existing
    
    # 创建新记录
    db_read = models.UserReadPost(user_id=user_id, post_id=post_id)
    db.add(db_read)
    db.commit()
    db.refresh(db_read)
    return db_read


def mark_posts_as_read(db: Session, user_id: int, post_ids: List[int]) -> int:
    """
    批量标记帖子为已读
    
    Args:
        db: 数据库会话
        user_id: 用户ID
        post_ids: 帖子ID列表
        
    Returns:
        成功标记的数量
    """
    count = 0
    for post_id in post_ids:
        try:
            mark_post_as_read(db, user_id, post_id)
            count += 1
        except Exception:
            continue
    return count


def check_post_is_read(db: Session, user_id: int, post_id: int) -> bool:
    """
    检查帖子是否已读
    
    Args:
        db: 数据库会话
        user_id: 用户ID
        post_id: 帖子ID
        
    Returns:
        是否已读
    """
    return (
        db.query(models.UserReadPost)
        .filter(
            models.UserReadPost.user_id == user_id,
            models.UserReadPost.post_id == post_id
        )
        .first()
        is not None
    )


def clear_user_read_history(db: Session, user_id: int) -> int:
    """
    清空用户的已读历史
    
    Args:
        db: 数据库会话
        user_id: 用户ID
        
    Returns:
        删除的记录数
    """
    result = (
        db.query(models.UserReadPost)
        .filter(models.UserReadPost.user_id == user_id)
        .delete()
    )
    db.commit()
    return result
