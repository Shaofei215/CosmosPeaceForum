# 关注业务逻辑层
# 实现关注系统的核心业务逻辑，包括关注/取消关注、状态查询、列表获取等功能
from sqlalchemy.orm import Session, joinedload
from sqlalchemy.exc import IntegrityError
from sqlalchemy import func
from typing import Tuple, List, Dict, Optional

from social_platform.app.domains.follow.models import Follow
from social_platform.app.domains.user.models import User
from social_platform.app.domains.follow.events import FollowChanged
from social_platform.app.shared.events import publish_domain_event
from social_platform.app.shared.unit_of_work import commit_session, rollback_session



class SelfFollowError(Exception):
    """
    自定义异常：不能关注自己

    当用户尝试关注自己时抛出此异常
    """

    def __init__(self):
        """初始化关注领域应用服务中的异常或服务对象，保存后续处理需要的上下文。"""
        super().__init__("不能关注自己")


class UserNotFoundError(Exception):
    """
    自定义异常：用户不存在

    当目标用户不存在时抛出此异常

    Attributes:
        user_id: 不存在的用户 ID
    """

    def __init__(self, user_id: int):
        """初始化关注领域应用服务中的异常或服务对象，保存后续处理需要的上下文。"""
        self.user_id = user_id
        super().__init__(f"用户不存在 (ID: {user_id})")


class AlreadyFollowingError(Exception):
    """
    自定义异常：已关注此用户

    当检测到重复关注时抛出此异常
    注：由于数据库唯一约束，实际上不会发生此情况
    """

    def __init__(self, follower_id: int, following_id: int):
        """初始化关注领域应用服务中的异常或服务对象，保存后续处理需要的上下文。"""
        self.follower_id = follower_id
        self.following_id = following_id
        super().__init__(f"已关注此用户")


def toggle_follow(
    db: Session,
    follower_id: int,
    following_id: int
) -> Tuple[bool, int, int]:
    """
    切换关注状态（关注/取消关注）

    在数据库事务中同时执行关注关系操作和用户计数更新，
    确保数据一致性。任何一步失败都会回滚整个事务。

    Args:
        db: 数据库会话
        follower_id: 关注者用户 ID（主动发起关注的一方）
        following_id: 被关注者用户 ID（被动接收关注的一方）

    Returns:
        Tuple[bool, int, int]: (是否已关注, 被关注者的被关注数, 关注者的关注数)
        - is_following: True 表示关注成功，False 表示取消关注成功
        - 被关注者的被关注数（操作后的值）
        - 关注者的关注数（操作后的值）

    Raises:
        SelfFollowError: 当尝试关注自己时抛出
        UserNotFoundError: 当目标用户不存在时抛出
        AlreadyFollowingError: 当检测到重复关注时抛出（理论上不会发生）

    Example:
        >>> is_following, followers_count, following_count = toggle_follow(
        ...     db=session, follower_id=123, following_id=456
        ... )
        >>> print(f"关注状态：{is_following}, 被关注数：{followers_count}")
    """
    # 参数校验：不能关注自己
    if follower_id == following_id:
        raise SelfFollowError()

    # 检查目标用户是否存在
    target_user = db.query(User).filter(User.id == following_id).first()
    if not target_user:
        raise UserNotFoundError(following_id)

    # 检查是否已经关注
    existing = db.query(Follow).filter(
        Follow.follower_id == follower_id,
        Follow.following_id == following_id
    ).first()

    try:
        if existing:
            # 已关注，执行取消关注操作
            # 1. 删除关注记录
            db.delete(existing)
            is_following = False
        else:
            # 未关注，执行关注操作
            # 1. 创建新的关注记录
            new_follow = Follow(
                follower_id=follower_id,
                following_id=following_id
            )
            db.add(new_follow)
            is_following = True

        # 更新冗余计数字段（悲观策略）
        # 先处理关系，再更新计数，保证一致性
        follower = db.query(User).filter(User.id == follower_id).first()
        following = db.query(User).filter(User.id == following_id).first()

        if is_following:
            # 关注操作：关注者的关注数 +1，被关注者的被关注数 +1
            follower.following_count += 1
            following.followers_count += 1
            publish_domain_event(
                db,
                FollowChanged(
                    follower_id=follower_id,
                    following_id=following_id,
                    previous_state=False,
                    current_state=True,
                ),
            )
        else:
            # 取消关注操作：关注者的关注数 -1，被关注者的被关注数 -1
            # 使用 max 确保不会减到负数
            follower.following_count = max(0, follower.following_count - 1)
            following.followers_count = max(0, following.followers_count - 1)
            publish_domain_event(
                db,
                FollowChanged(
                    follower_id=follower_id,
                    following_id=following_id,
                    previous_state=True,
                    current_state=False,
                ),
            )

        # 提交事务
        commit_session(db)
        # 刷新对象以获取最新计数值
        db.refresh(follower)
        db.refresh(following)

        return (is_following, following.followers_count, follower.following_count)

    except IntegrityError as e:
        # 数据库完整性错误（如唯一约束冲突）
        rollback_session(db)
        raise AlreadyFollowingError(follower_id, following_id) from e


def get_follow_status(
    db: Session,
    current_user_id: int,
    target_user_id: int
) -> Dict[str, bool]:
    """
    获取当前用户与目标用户之间的关注状态

    查询两人之间的关注关系，返回单向关注状态和互相关注标识。

    Args:
        db: 数据库会话
        current_user_id: 当前登录用户 ID
        target_user_id: 目标用户 ID

    Returns:
        Dict[str, bool]: 包含三个布尔值的字典
        - is_following: 当前用户是否关注了目标用户
        - is_followed_by: 目标用户是否关注了当前用户
        - is_mutual: 是否互相关注（双方都关注对方）

    Example:
        >>> status = get_follow_status(db=session, current_user_id=123, target_user_id=456)
        >>> if status["is_mutual"]:
        ...     print("你们互相关注了！")
    """
    # 查询当前用户是否关注了目标用户
    is_following = db.query(Follow).filter(
        Follow.follower_id == current_user_id,
        Follow.following_id == target_user_id
    ).first() is not None

    # 查询目标用户是否关注了当前用户
    is_followed_by = db.query(Follow).filter(
        Follow.follower_id == target_user_id,
        Follow.following_id == current_user_id
    ).first() is not None

    return {
        "is_following": is_following,
        "is_followed_by": is_followed_by,
        "is_mutual": is_following and is_followed_by
    }


def get_following_list(
    db: Session,
    user_id: int,
    page: int = 1,
    page_size: int = 20,
    current_user_id: Optional[int] = None
) -> Tuple[List[Follow], int]:
    """
    获取用户的关注列表（分页）

    查询指定用户关注的所有用户，支持分页查询。

    Args:
        db: 数据库会话
        user_id: 要查询的用户 ID
        page: 页码，从 1 开始
        page_size: 每页记录数，默认 20
        current_user_id: 当前登录用户 ID（可选，用于批量查询关注状态）

    Returns:
        Tuple[List[Follow], int]: (关注记录列表, 总数)
        - follows: 关注记录列表，每条记录包含被关注用户信息
        - total: 符合条件的总记录数

    Note:
        返回的 Follow 记录已预加载 following 用户信息
    """
    offset = (page - 1) * page_size

    # 查询关注记录，使用 joinedload 预加载被关注用户信息避免 N+1
    follows = db.query(Follow).options(
        joinedload(Follow.following)
    ).filter(
        Follow.follower_id == user_id
    ).order_by(
        Follow.created_at.desc()
    ).offset(offset).limit(page_size).all()

    # 获取总数（单独查询，不预加载）
    total = db.query(func.count(Follow.id)).filter(
        Follow.follower_id == user_id
    ).scalar()

    return (follows, total)


def get_followers_list(
    db: Session,
    user_id: int,
    page: int = 1,
    page_size: int = 20,
    current_user_id: Optional[int] = None
) -> Tuple[List[Follow], int]:
    """
    获取用户的被关注列表（分页）

    查询指定用户的所有被关注，支持分页查询。

    Args:
        db: 数据库会话
        user_id: 要查询的用户 ID
        page: 页码，从 1 开始
        page_size: 每页记录数，默认 20
        current_user_id: 当前登录用户 ID（可选，用于批量查询关注状态）

    Returns:
        Tuple[List[Follow], int]: (被关注记录列表, 总数)
        - follows: 被关注记录列表，每条记录包含被关注用户信息
        - total: 符合条件的总记录数

    Note:
        返回的 Follow 记录已预加载 follower（被关注）用户信息
    """
    offset = (page - 1) * page_size

    # 查询被关注记录，使用 joinedload 预加载被关注用户信息避免 N+1
    follows = db.query(Follow).options(
        joinedload(Follow.follower)
    ).filter(
        Follow.following_id == user_id
    ).order_by(
        Follow.created_at.desc()
    ).offset(offset).limit(page_size).all()

    # 获取总数（单独查询，不预加载）
    total = db.query(func.count(Follow.id)).filter(
        Follow.following_id == user_id
    ).scalar()

    return (follows, total)


def get_follow_status_batch(
    db: Session,
    current_user_id: int,
    target_user_ids: List[int]
) -> Dict[int, Dict[str, bool]]:
    """
    批量获取当前用户对多个目标用户的关注状态

    一次性查询多个目标用户的关注状态，避免循环查询造成的 N+1 问题。

    Args:
        db: 数据库会话
        current_user_id: 当前登录用户 ID
        target_user_ids: 目标用户 ID 列表

    Returns:
        Dict[int, Dict[str, bool]]: {user_id: {is_following, is_followed_by, is_mutual}}

    Note:
        如果 target_user_ids 为空，返回空字典
        未在返回结果中的 user_id 表示没有关注关系

    Example:
        >>> statuses = get_follow_status_batch(
        ...     db=session,
        ...     current_user_id=123,
        ...     target_user_ids=[456, 789, 101]
        ... )
        >>> for uid, status in statuses.items():
        ...     print(f"用户{uid}: 关注={status['is_following']}, 被关注={status['is_followed_by']}")
    """
    if not target_user_ids:
        return {}

    # 批量查询：当前用户关注了哪些人
    following_ids = set(
        row[0] for row in db.query(Follow.following_id).filter(
            Follow.follower_id == current_user_id,
            Follow.following_id.in_(target_user_ids)
        ).all()
    )

    # 批量查询：哪些人关注了当前用户
    follower_ids = set(
        row[0] for row in db.query(Follow.follower_id).filter(
            Follow.following_id == current_user_id,
            Follow.follower_id.in_(target_user_ids)
        ).all()
    )

    # 组装结果
    result = {}
    for uid in target_user_ids:
        is_following = uid in following_ids
        is_followed_by = uid in follower_ids
        result[uid] = {
            "is_following": is_following,
            "is_followed_by": is_followed_by,
            "is_mutual": is_following and is_followed_by
        }

    return result


def is_following(
    db: Session,
    follower_id: int,
    following_id: int
) -> bool:
    """
    检查用户是否关注了另一个用户

    Args:
        db: 数据库会话
        follower_id: 关注者用户 ID
        following_id: 被关注者用户 ID

    Returns:
        bool: True 表示已关注，False 表示未关注

    Example:
        >>> if is_following(db=session, follower_id=123, following_id=456):
        ...     print("已关注")
    """
    return db.query(Follow).filter(
        Follow.follower_id == follower_id,
        Follow.following_id == following_id
    ).first() is not None


def get_user_follow_counts(
    db: Session,
    user_id: int
) -> Dict[str, int]:
    """
    获取用户的关注统计数据

    直接从数据库查询用户的关注数和被关注数。

    Args:
        db: 数据库会话
        user_id: 用户 ID

    Returns:
        Dict[str, int]: {following_count, followers_count}

    Note:
        此函数直接查询冗余计数字段，性能较好
        如果需要实时准确数据，应使用此函数
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise UserNotFoundError(user_id)

    return {
        "following_count": user.following_count,
        "followers_count": user.followers_count
    }
