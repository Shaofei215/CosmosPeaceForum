# 评论业务逻辑层
# 实现评论相关的核心业务逻辑，包括创建、查询、点赞等功能
from sqlalchemy.orm import Session, joinedload
from sqlalchemy.exc import IntegrityError
from typing import Tuple, List, Optional, Dict
from collections import defaultdict

from app.models.comment import Comment, CommentLike
from app.models.post import Post
from app.models.user import User


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


def create_comment(
    post_id: int,
    user_id: int,
    content: str,
    parent_id: Optional[int],
    db: Session
) -> Comment:
    """
    创建评论或回复
    
    在数据库事务中创建评论，并更新相关的计数器：
    - 更新帖子的 comment_count
    - 如果是回复，循环更新所有祖先的 reply_count
    
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
    
    # 如果指定了父评论，检查父评论是否存在且属于同一帖子
    if parent_id is not None:
        parent_comment = db.query(Comment).filter(Comment.id == parent_id).first()
        if not parent_comment:
            raise ParentCommentNotFoundError(parent_id)
        if parent_comment.post_id != post_id:
            raise ParentCommentMismatchError(parent_id, post_id, parent_comment.post_id)
    
    try:
        # 1. 创建新评论
        new_comment = Comment(
            post_id=post_id,
            owner_id=user_id,
            parent_id=parent_id,
            content=content,
            like_count=0,
            reply_count=0
        )
        db.add(new_comment)
        db.flush()  # 刷新以获取新评论的 ID
        
        # 2. 更新帖子的评论计数
        post.comment_count = post.comment_count + 1
        
        # 3. 如果是回复，循环更新所有祖先的 reply_count
        if parent_id is not None:
            current_id = parent_id
            while current_id is not None:
                # 更新当前祖先的 reply_count
                ancestor = db.query(Comment).filter(Comment.id == current_id).first()
                if ancestor:
                    ancestor.reply_count = ancestor.reply_count + 1
                    current_id = ancestor.parent_id  # 继续向上追溯
                else:
                    break  # 祖先不存在，退出循环
        
        # 4. 提交事务
        db.commit()
        db.refresh(new_comment)
        
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
    db: Session
) -> Tuple[List[Comment], int]:
    """
    获取帖子的评论树
    
    查询指定帖子的一级评论列表，并递归加载所有回复。
    使用批量加载策略优化性能。
    
    Args:
        post_id: 帖子 ID
        user_id: 当前用户 ID（用于判断点赞状态），可为空
        skip: 跳过的数量（分页）
        limit: 返回的最大数量（分页）
        db: 数据库会话
    
    Returns:
        Tuple[List[Comment], int]: (评论列表，总数)
        - 评论列表：一级评论对象列表，每个评论的 children 属性包含回复
        - 总数：帖子下所有评论的总数
    
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
    # 检查帖子是否存在
    post = db.query(Post).filter(Post.id == post_id).first()
    if not post:
        raise PostNotFoundError(post_id)
    
    # 获取帖子下所有评论的总数
    total = db.query(Comment).filter(Comment.post_id == post_id).count()
    
    # 查询一级评论（parent_id IS NULL）
    # 使用 joinedload 预加载 owner 信息，减少 N+1 查询
    root_comments = db.query(Comment).filter(
        Comment.post_id == post_id,
        Comment.parent_id == None
    ).options(
        joinedload(Comment.owner)
    ).order_by(
        Comment.created_at.desc()
    ).offset(skip).limit(limit).all()
    
    # 如果没有一级评论，直接返回
    if not root_comments:
        return ([], total)
    
    # 获取所有一级评论的 ID
    root_comment_ids = [c.id for c in root_comments]
    
    # 批量查询所有回复（非一级评论）
    all_replies = db.query(Comment).filter(
        Comment.post_id == post_id,
        Comment.parent_id != None
    ).options(
        joinedload(Comment.owner)
    ).order_by(
        Comment.created_at.asc()  # 回复按时间正序排列
    ).all()
    
    # 构建评论树结构
    # 使用字典存储每个评论的子评论列表
    children_map: Dict[int, List[Comment]] = defaultdict(list)
    
    # 按 parent_id 分组回复
    for reply in all_replies:
        children_map[reply.parent_id].append(reply)
    
    # 递归函数：为每个评论设置 children
    def attach_children(comment: Comment) -> None:
        """递归附加子评论"""
        comment.children = children_map.get(comment.id, [])
        for child in comment.children:
            attach_children(child)
    
    # 为每个一级评论附加子评论树
    for root_comment in root_comments:
        attach_children(root_comment)
    
    # 如果提供了 user_id，注入点赞状态
    if user_id is not None:
        # 获取所有评论的 ID（包括一级评论和所有回复）
        all_comment_ids = root_comment_ids.copy()
        for reply in all_replies:
            all_comment_ids.append(reply.id)
        
        # 批量查询用户的点赞记录
        liked_comment_ids = set(
            row[0] for row in db.query(CommentLike.comment_id).filter(
                CommentLike.user_id == user_id,
                CommentLike.comment_id.in_(all_comment_ids)
            ).all()
        )
        
        # 递归函数：设置点赞状态
        def set_like_status(comment: Comment) -> None:
            """递归设置点赞状态"""
            comment.is_liked = comment.id in liked_comment_ids
            for child in comment.children:
                set_like_status(child)
        
        # 为每个评论设置点赞状态
        for root_comment in root_comments:
            set_like_status(root_comment)
    
    return (root_comments, total)


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
    comment = db.query(Comment).filter(Comment.id == comment_id).first()
    if not comment:
        return None
    
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


def delete_comment(
    comment_id: int,
    user_id: int,
    db: Session
) -> bool:
    """
    删除评论
    
    删除评论并更新相关的计数器：
    - 更新帖子的 comment_count
    - 更新所有祖先的 reply_count
    
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
        
        # 获取该评论下的所有回复数量（用于更新计数）
        reply_count_to_subtract = 1 + comment.reply_count  # 1 是评论本身 + 所有回复
        
        # 1. 删除评论（级联删除会自动删除子评论和点赞记录）
        db.delete(comment)
        
        # 2. 更新帖子的评论计数
        post = db.query(Post).filter(Post.id == post_id).first()
        if post:
            post.comment_count = max(0, post.comment_count - reply_count_to_subtract)
        
        # 3. 更新所有祖先的 reply_count
        if parent_id is not None:
            current_id = parent_id
            while current_id is not None:
                ancestor = db.query(Comment).filter(Comment.id == current_id).first()
                if ancestor:
                    ancestor.reply_count = max(0, ancestor.reply_count - reply_count_to_subtract)
                    current_id = ancestor.parent_id
                else:
                    break
        
        # 4. 提交事务
        db.commit()
        
        return True
    
    except Exception as e:
        db.rollback()
        raise e
