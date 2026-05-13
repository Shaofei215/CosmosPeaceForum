# 点赞业务逻辑层
# 实现点赞相关的核心业务逻辑
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from typing import Tuple

from app_platform.app.models.like import Like
from app_platform.app.models.post import Post
from app_platform.app.services import heat_service, notification_service


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


def toggle_like(
    post_id: int,
    user_id: int,
    db: Session
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
    post = db.query(Post).filter(Post.id == post_id).first()
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
            heat_service.refresh_post_heat_score(db, post)
            # 3. 提交事务
            db.commit()
            # 返回：已取消点赞，新的点赞数
            return (False, post.like_count)
        else:
            # 未点赞，执行点赞操作
            # 1. 创建点赞记录
            new_like = Like(user_id=user_id, post_id=post_id)
            db.add(new_like)
            # 2. 增加帖子点赞计数
            post.like_count = post.like_count + 1
            heat_service.refresh_post_heat_score(db, post)
            notification_service.create_post_like_notification(db, post, user_id)
            # 3. 提交事务
            db.commit()
            # 返回：已点赞，新的点赞数
            return (True, post.like_count)
    
    except IntegrityError as e:
        # 数据库完整性错误（如复合主键冲突）
        db.rollback()
        # 抛出重复点赞异常
        raise DuplicateLikeError(user_id, post_id) from e


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
    post = db.query(Post).filter(Post.id == post_id).first()
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
    post = db.query(Post).filter(Post.id == post_id).first()
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
    post = db.query(Post).filter(Post.id == post_id).first()
    if not post:
        raise PostNotFoundError(post_id)
    
    # 查询点赞记录
    like = db.query(Like).filter(
        Like.user_id == user_id,
        Like.post_id == post_id
    ).first()
    
    return like is not None
