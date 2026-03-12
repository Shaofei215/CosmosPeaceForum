"""
CRUD 操作模块
提供所有数据库操作的封装函数
"""
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import desc
from typing import List, Optional, Dict
from datetime import datetime

from app import models, schemas


def count_all_reposts(db: Session, post_id: int) -> int:
    """
    统计所有转发（包括直接转发和间接转发）
    ✅ 优化：单次查询 + 内存递归，解决 N+1 查询问题
    
    Args:
        db: 数据库会话
        post_id: 帖子 ID
    
    Returns:
        总转发数
    """
    # ✅ 一次性获取所有转发记录
    all_quotes = db.query(models.Post).filter(
        models.Post.post_type == 'quote'
    ).all()
    
    # ✅ 构建转发关系图（内存中）
    # quote_map[from_id] = [所有转发 from_id 的帖子 ID 列表]
    quote_map = {}
    for quote in all_quotes:
        if quote.quote_from_id not in quote_map:
            quote_map[quote.quote_from_id] = []
        quote_map[quote.quote_from_id].append(quote.id)
    
    # ✅ 递归计数（纯内存操作，无数据库查询）
    def count_descendants(pid):
        count = 0
        if pid in quote_map:
            for child_id in quote_map[pid]:
                count += 1 + count_descendants(child_id)
        return count
    
    return count_descendants(post_id)


def create_user(db: Session, user: schemas.UserCreate) -> models.User:
    """创建新用户"""
    db_user = models.User(
        username=user.username,
        bio=user.bio,
        avatar=user.avatar
    )
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
    """根据 ID 获取帖子"""
    post = db.query(models.Post).filter(models.Post.id == post_id).first()
    if post:
        # 动态添加统计属性
        post.likes_count = db.query(models.Like).filter(models.Like.post_id == post_id).count()
        # 评论数 = 评论数 + 回复数
        comment_count = db.query(models.Comment).filter(models.Comment.post_id == post_id).count()
        reply_count = db.query(models.Reply).join(models.Comment).filter(models.Comment.post_id == post_id).count()
        post.comments_count = comment_count + reply_count
        post.reposts_count = db.query(models.Post).filter(
            models.Post.quote_from_id == post_id
        ).count()  # 统计转发数
        post.views_count = post.hot_score  # 用热度分数作为浏览量估算
        # 获取点赞用户列表（最多 3 个）
        likers = db.query(models.Like).filter(models.Like.post_id == post_id).limit(3).all()
        post.likers = [like.user for like in likers if like.user]
    return post


def get_posts(db: Session, skip: int = 0, limit: int = 50) -> List[models.Post]:
    """获取帖子列表（按时间倒序）"""
    posts = (
        db.query(models.Post)
        .options(joinedload(models.Post.original_post).joinedload(models.Post.author))
        .order_by(desc(models.Post.created_at))
        .offset(skip)
        .limit(limit)
        .all()
    )
    # 为每个帖子添加统计属性
    for post in posts:
        post.likes_count = db.query(models.Like).filter(models.Like.post_id == post.id).count()
        # 评论数 = 评论数 + 回复数
        comment_count = db.query(models.Comment).filter(models.Comment.post_id == post.id).count()
        reply_count = db.query(models.Reply).join(models.Comment).filter(models.Comment.post_id == post.id).count()
        post.comments_count = comment_count + reply_count
        # 递归统计转发数（包括间接转发）
        post.reposts_count = count_all_reposts(db, post.id)
        post.views_count = post.hot_score
        # 获取点赞用户列表（最多 3 个）
        likers = db.query(models.Like).filter(models.Like.post_id == post.id).limit(3).all()
        post.likers = [like.user for like in likers if like.user]
    return posts


def get_user_posts(db: Session, user_id: int, skip: int = 0, limit: int = 50) -> List[models.Post]:
    """获取用户的帖子列表"""
    posts = (
        db.query(models.Post)
        .filter(models.Post.author_id == user_id)
        .order_by(desc(models.Post.created_at))
        .offset(skip)
        .limit(limit)
        .all()
    )
    # 为每个帖子添加统计属性
    for post in posts:
        post.likes_count = db.query(models.Like).filter(models.Like.post_id == post.id).count()
        # 评论数 = 评论数 + 回复数
        comment_count = db.query(models.Comment).filter(models.Comment.post_id == post.id).count()
        reply_count = db.query(models.Reply).join(models.Comment).filter(models.Comment.post_id == post.id).count()
        post.comments_count = comment_count + reply_count
        post.reposts_count = db.query(models.Post).filter(
            models.Post.quote_from_id == post.id
        ).count()
        post.views_count = post.hot_score
    return posts


def create_quote_post(
    db: Session,
    quote_from_id: int,
    author_id: int,
    content: str
) -> models.Post:
    """
    创建引用转发帖子（直接转发）
    
    Args:
        db: 数据库会话
        quote_from_id: 被转发的帖子 ID（可能是转发帖）
        author_id: 转发者 ID
        content: 转发评论（正文内容，会自动添加转发链）
    
    Returns:
        转发帖子对象
    """
    # 检查被转发的帖子是否存在
    quoted_post = db.query(models.Post).filter(
        models.Post.id == quote_from_id
    ).first()
    if not quoted_post:
        raise ValueError(f"原帖不存在：{quote_from_id}")
    
    # 追溯到最原始的帖子（小卡片应该显示原始帖子）
    original_post_id = quote_from_id
    current_post = quoted_post
    while current_post.post_type == 'quote':
        current_post = db.query(models.Post).filter(
            models.Post.id == current_post.quote_from_id
        ).first()
        if current_post:
            original_post_id = current_post.id
        else:
            break
    
    # 构建完整的正文内容（包括转发链）
    full_content = build_repost_content(
        db=db,
        current_content=content,
        quote_from_id=quote_from_id  # 使用传入的 quote_from_id 来构建转发链
    )
    
    # 创建转发帖子（独立记录）
    db_post = models.Post(
        author_id=author_id,
        content=full_content,  # 完整的正文内容（包括转发链）
        post_type="quote",
        repost_type="direct",  # 直接转发
        quote_from_id=quote_from_id,  # 指向直接转发的帖子（用于计数）
        original_post_id=original_post_id,  # 指向原始帖子（用于小卡片）
        quote_comment=content  # 仅存储转发者的评论
    )
    
    db.add(db_post)
    db.commit()
    db.refresh(db_post)
    
    # 通知直接转发的帖子作者
    if quoted_post.author_id != author_id:
        create_notification(
            db=db,
            user_id=quoted_post.author_id,
            actor_id=author_id,
            notification_type=models.NotificationType.QUOTE,
            post_id=quote_from_id
        )
    
    # 递归更新热度（从直接转发的帖子开始，会递归到原始帖子）
    from app.hot_score import update_post_hot_score
    update_post_hot_score(db, quote_from_id, recursive=True)
    
    return db_post


def create_comment_with_repost(
    db: Session,
    post_id: int,
    author_id: int,
    content: str,
    quote_from_id: int
) -> tuple[models.Comment, models.Post]:
    """
    创建评论并同时转发
    
    Args:
        db: 数据库会话
        post_id: 被评论的帖子 ID
        author_id: 评论者 ID
        content: 评论内容
        quote_from_id: 被转发的帖子 ID（通常与 post_id 相同）
    
    Returns:
        (评论对象，转发帖子对象)
    """
    try:
        # 1. 检查原帖是否存在（提前验证）
        original_post = db.query(models.Post).filter(
            models.Post.id == quote_from_id
        ).first()
        if not original_post:
            raise ValueError(f"原帖不存在：{quote_from_id}")
        
        # 2. 创建评论（不 commit）
        db_comment = models.Comment(
            post_id=post_id,
            author_id=author_id,
            content=content
        )
        db.add(db_comment)
        db.flush()  # 获取 comment_id 但不提交
        
        # 3. 追溯到最原始的帖子（小卡片应该显示原始帖子）
        original_post_id = quote_from_id
        current_post = original_post
        while current_post.post_type == 'quote':
            current_post = db.query(models.Post).filter(
                models.Post.id == current_post.quote_from_id
            ).first()
            if current_post:
                original_post_id = current_post.id
            else:
                break
        
        # 4. 构建完整的正文内容（包括转发链）
        full_content = build_repost_content(
            db=db,
            current_content=content,
            quote_from_id=quote_from_id,
            comment_id=db_comment.id
        )
        
        # 5. 创建转发帖子
        db_post = models.Post(
            author_id=author_id,
            content=full_content,  # 完整的正文内容（包括转发链）
            post_type="quote",
            repost_type="comment",  # 评论并转发
            quote_from_id=quote_from_id,
            original_post_id=original_post_id,  # 指向原始帖子（用于小卡片）
            comment_id=db_comment.id,
            quote_comment=content  # 仅存储评论内容
        )
        db.add(db_post)
        
        # 6. 统一提交
        db.commit()
        db.refresh(db_comment)
        db.refresh(db_post)
        
        # 7. 创建通知：通知帖子作者
        if original_post.author_id != author_id:
            create_notification(
                db=db,
                user_id=original_post.author_id,
                actor_id=author_id,
                notification_type=models.NotificationType.COMMENT,
                post_id=post_id,
                comment_id=db_comment.id
            )
            # 同时通知被转发
            create_notification(
                db=db,
                user_id=original_post.author_id,
                actor_id=author_id,
                notification_type=models.NotificationType.QUOTE,
                post_id=quote_from_id
            )
        
        # 8. 更新原帖热度
        from app.hot_score import update_post_hot_score
        update_post_hot_score(db, quote_from_id)
        update_post_hot_score(db, post_id)
        
        return db_comment, db_post
        
    except Exception as e:
        db.rollback()
        raise


def create_reply_with_repost(
    db: Session,
    comment_id: int,
    author_id: int,
    content: str,
    quote_from_id: int
) -> tuple[models.Reply, models.Post]:
    """
    创建回复并同时转发
    
    Args:
        db: 数据库会话
        comment_id: 被回复的评论 ID
        author_id: 回复者 ID
        content: 回复内容
        quote_from_id: 被转发的帖子 ID
    
    Returns:
        (回复对象，转发帖子对象)
    """
    # 1. 创建回复
    db_reply = models.Reply(
        comment_id=comment_id,
        author_id=author_id,
        content=content
    )
    db.add(db_reply)
    db.commit()
    db.refresh(db_reply)
    
    # 2. 创建转发帖子
    original_post = db.query(models.Post).filter(
        models.Post.id == quote_from_id
    ).first()
    if not original_post:
        db.rollback()
        raise ValueError(f"原帖不存在：{quote_from_id}")
    
    # 追溯到最原始的帖子（小卡片应该显示原始帖子）
    original_post_id = quote_from_id
    current_post = original_post
    while current_post.post_type == 'quote':
        current_post = db.query(models.Post).filter(
            models.Post.id == current_post.quote_from_id
        ).first()
        if current_post:
            original_post_id = current_post.id
        else:
            break
    
    # 获取被回复的评论作者
    comment = db.query(models.Comment).filter(
        models.Comment.id == comment_id
    ).first()
    reply_to_username = comment.author.username if comment else "未知用户"
    
    # 构建完整的正文内容（包括转发链）
    full_content = build_repost_content(
        db=db,
        current_content=content,
        quote_from_id=quote_from_id,
        reply_id=db_reply.id,
        is_reply=True,
        reply_to_username=reply_to_username
    )
    
    db_post = models.Post(
        author_id=author_id,
        content=full_content,  # 完整的正文内容（包括转发链）
        post_type="quote",
        repost_type="reply",  # 回复并转发
        quote_from_id=quote_from_id,
        original_post_id=original_post_id,  # 指向原始帖子（用于小卡片）
        reply_id=db_reply.id,
        quote_comment=content  # 仅存储回复内容
    )
    db.add(db_post)
    db.commit()
    db.refresh(db_post)
    
    # 3. 创建通知：通知评论作者
    if comment and comment.author_id != author_id:
        create_notification(
            db=db,
            user_id=comment.author_id,
            actor_id=author_id,
            notification_type=models.NotificationType.REPLY,
            post_id=original_post.id,
            comment_id=comment_id,
            reply_id=db_reply.id
        )
    
    # 同时通知被转发
    if original_post.author_id != author_id:
        create_notification(
            db=db,
            user_id=original_post.author_id,
            actor_id=author_id,
            notification_type=models.NotificationType.QUOTE,
            post_id=quote_from_id
        )
    
    # 4. 更新原帖热度
    from app.hot_score import update_post_hot_score
    update_post_hot_score(db, quote_from_id)
    
    return db_reply, db_post


def get_post_quotes(db: Session, post_id: int, skip: int = 0, limit: int = 50) -> List[models.Post]:
    """
    获取帖子的所有转发
    
    Args:
        db: 数据库会话
        post_id: 原帖 ID
        skip: 跳过数量
        limit: 返回数量
    
    Returns:
        转发帖子列表
    """
    quotes = (
        db.query(models.Post)
        .filter(models.Post.quote_from_id == post_id)
        .order_by(desc(models.Post.created_at))
        .offset(skip)
        .limit(limit)
        .all()
    )
    
    # 为每个转发添加统计属性
    for quote in quotes:
        quote.likes_count = db.query(models.Like).filter(models.Like.post_id == quote.id).count()
        comment_count = db.query(models.Comment).filter(models.Comment.post_id == quote.id).count()
        reply_count = db.query(models.Reply).join(models.Comment).filter(models.Comment.post_id == quote.id).count()
        quote.comments_count = comment_count + reply_count
        quote.reposts_count = 0
        quote.views_count = quote.hot_score
    
    return quotes


def get_repost_chain(db: Session, quote_from_id: int, comment_id: Optional[int] = None, reply_id: Optional[int] = None) -> List[Dict]:
    """
    获取转发链（从被转发对象追溯到原帖评论）
    
    Args:
        db: 数据库会话
        quote_from_id: 被转发的帖子 ID
        comment_id: 被转发的评论 ID（可选）
        reply_id: 被转发的回复 ID（可选）
    
    Returns:
        转发链列表，每个元素包含：
        - username: 用户名
        - content: 内容
        - type: 类型（post/comment/reply）
        
    示例：
        A 发布帖子，B 评论，C 回复，D 转发 C 的回复
        返回：[{'username': 'D', 'content': '+1', 'type': 'reply'},
              {'username': 'C', 'content': '我也同意', 'type': 'reply'},
              {'username': 'B', 'content': '确实不错', 'type': 'comment'}]
    """
    chain = []
    
    # 1. 如果是转发回复，追溯回复链
    if reply_id:
        reply = db.query(models.Reply).filter(models.Reply.id == reply_id).first()
        if reply:
            # 添加当前回复
            chain.append({
                'username': reply.author.username,
                'content': reply.content,
                'type': 'reply'
            })
            
            # 追溯父回复（只追溯回复链，不追溯帖子）
            current_reply = reply
            while current_reply.parent_reply_id:
                parent_reply = db.query(models.Reply).filter(
                    models.Reply.id == current_reply.parent_reply_id
                ).first()
                if parent_reply:
                    chain.append({
                        'username': parent_reply.author.username,
                        'content': parent_reply.content,
                        'type': 'reply'
                    })
                    current_reply = parent_reply
                else:
                    break
            
            # 添加评论
            comment = db.query(models.Comment).filter(
                models.Comment.id == current_reply.comment_id
            ).first()
            if comment:
                chain.append({
                    'username': comment.author.username,
                    'content': comment.content,
                    'type': 'comment'
                })
    
    # 2. 如果是转发评论，直接添加评论
    elif comment_id:
        comment = db.query(models.Comment).filter(models.Comment.id == comment_id).first()
        if comment:
            chain.append({
                'username': comment.author.username,
                'content': comment.content,
                'type': 'comment'
            })
    
    # 3. 如果是直接转发帖子，检查是否是转发链
    else:
        post = db.query(models.Post).filter(models.Post.id == quote_from_id).first()
        if post and post.post_type == 'quote':
            # 如果是转发帖子，提取 quote_comment 并继续追溯
            if post.quote_comment:
                chain.append({
                    'username': post.author.username,
                    'content': post.quote_comment,
                    'type': 'post'
                })
            # 递归获取上一级转发链
            parent_chain = get_repost_chain(
                db,
                post.quote_from_id,
                post.comment_id,
                post.reply_id
            )
            chain.extend(parent_chain)
    
    return chain


def build_repost_content(db: Session, current_content: str, quote_from_id: int, 
                         comment_id: Optional[int] = None, reply_id: Optional[int] = None,
                         is_reply: bool = False, reply_to_username: str = None) -> str:
    """
    构建转发正文内容
    
    Args:
        db: 数据库会话
        current_content: 当前转发者的内容
        quote_from_id: 被转发的帖子 ID
        comment_id: 被转发的评论 ID（可选）
        reply_id: 被转发的回复 ID（可选）
        is_reply: 是否是回复转发
        reply_to_username: 回复的用户名
    
    Returns:
        完整的正文内容（当前内容 + 转发链）
    
    示例：
        回复@D：好极了。//@D: +1 //@C: 我也同意 //@B: 确实不错
    """
    # 1. 构建正文开头
    if is_reply and reply_to_username:
        # 回复转发：回复@xxx：内容。//@xxx: ...
        content = f"回复@{reply_to_username}：{current_content}。"
    else:
        # 直接转发或评论转发：内容。//@xxx: ...
        content = f"{current_content}。"
    
    # 2. 如果有 reply_id，追溯回复链（但不包括当前回复，只追溯父级）
    if reply_id:
        current_reply = db.query(models.Reply).filter(models.Reply.id == reply_id).first()
        # 追溯父回复（不包括当前回复）
        if current_reply and current_reply.parent_reply_id:
            current_reply = db.query(models.Reply).filter(
                models.Reply.id == current_reply.parent_reply_id
            ).first()
            # 开始追溯父回复链
            while current_reply:
                content += f"//@{current_reply.author.username}: {current_reply.content}"
                # 检查是否有父回复
                if current_reply.parent_reply_id:
                    current_reply = db.query(models.Reply).filter(
                        models.Reply.id == current_reply.parent_reply_id
                    ).first()
                else:
                    # 没有父回复，添加评论
                    comment = db.query(models.Comment).filter(
                        models.Comment.id == current_reply.comment_id
                    ).first()
                    if comment:
                        content += f"//@{comment.author.username}: {comment.content}"
                    break
        elif current_reply:
            # 没有父回复，直接添加评论
            comment = db.query(models.Comment).filter(
                models.Comment.id == current_reply.comment_id
            ).first()
            if comment:
                content += f"//@{comment.author.username}: {comment.content}"
    
    # 3. 如果有 comment_id（没有 reply_id），不添加转发链
    # 因为这是第一个评论转发，没有上级可以追溯
    elif comment_id:
        # 第一个评论转发，没有转发链
        pass
    
    # 4. 如果只有 quote_from_id，检查被转发的帖子
    else:
        quoted_post = db.query(models.Post).filter(models.Post.id == quote_from_id).first()
        if not quoted_post:
            return content
        
        # 如果被转发的帖子是原创帖，不再添加到正文（前端会用小卡片展示）
        # ✅ 修复：避免正文和小卡片重复展示原帖
        if quoted_post.post_type == 'original':
            # 不再添加原帖内容到正文，前端会用小卡片展示
            pass  # 正文只包含转发评论，原帖内容在小卡片中展示
        
        # 如果被转发的帖子是转发帖，递归获取转发链
        elif quoted_post.post_type == 'quote':
            # 添加被转发帖子的内容（quote_comment，不是完整 content）
            if quoted_post.quote_comment:
                content += f"//@{quoted_post.author.username}: {quoted_post.quote_comment}"
            
            # 递归构建上一级转发链
            parent_content = build_repost_content(
                db=db,
                current_content="",
                quote_from_id=quoted_post.quote_from_id,
                comment_id=quoted_post.comment_id,
                reply_id=quoted_post.reply_id,
                is_reply=False
            )
            content += parent_content
    
    return content


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
    
    # 创建通知：通知帖子作者
    post = db.query(models.Post).filter(models.Post.id == post_id).first()
    if post and post.author_id != author_id:
        create_notification(
            db=db,
            user_id=post.author_id,
            actor_id=author_id,
            notification_type=models.NotificationType.COMMENT,
            post_id=post_id,
            comment_id=db_comment.id
        )
    
    return db_comment


def get_comment(db: Session, comment_id: int) -> Optional[models.Comment]:
    """根据ID获取评论"""
    return db.query(models.Comment).filter(models.Comment.id == comment_id).first()


def get_post_comments(db: Session, post_id: int, skip: int = 0, limit: int = 50, include_replies: bool = True) -> List[models.Comment]:
    """获取帖子的评论列表"""
    comments = (
        db.query(models.Comment)
        .filter(models.Comment.post_id == post_id)
        .order_by(desc(models.Comment.created_at))
        .offset(skip)
        .limit(limit)
        .all()
    )
    # 为每条评论添加统计属性和回复
    for comment in comments:
        comment.likes_count = db.query(models.Like).filter(models.Like.comment_id == comment.id).count()
        replies = db.query(models.Reply).filter(models.Reply.comment_id == comment.id).all()
        comment.replies_count = len(replies)
        if include_replies:
            # 为每个回复添加作者信息
            for reply in replies:
                reply.likes_count = db.query(models.Like).filter(models.Like.reply_id == reply.id).count()
            comment.replies = replies
    return comments


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
    
    # 创建通知：通知评论作者或父回复作者
    comment = db.query(models.Comment).filter(models.Comment.id == comment_id).first()
    if comment:
        # 如果是回复评论，通知评论作者
        if comment.author_id != author_id:
            create_notification(
                db=db,
                user_id=comment.author_id,
                actor_id=author_id,
                notification_type=models.NotificationType.REPLY,
                comment_id=comment_id,
                reply_id=db_reply.id
            )
        # 如果是回复回复，通知父回复作者
        elif parent_reply_id:
            parent_reply = db.query(models.Reply).filter(models.Reply.id == parent_reply_id).first()
            if parent_reply and parent_reply.author_id != author_id:
                create_notification(
                    db=db,
                    user_id=parent_reply.author_id,
                    actor_id=author_id,
                    notification_type=models.NotificationType.REPLY,
                    comment_id=comment_id,
                    reply_id=db_reply.id
                )
    
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
    
    # 创建通知：通知帖子作者
    post = db.query(models.Post).filter(models.Post.id == post_id).first()
    if post and post.author_id != user_id:
        create_notification(
            db=db,
            user_id=post.author_id,
            actor_id=user_id,
            notification_type=models.NotificationType.LIKE_POST,
            post_id=post_id
        )
    
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
    
    # 创建通知：通知被关注者
    create_notification(
        db=db,
        user_id=following_id,
        actor_id=follower_id,
        notification_type=models.NotificationType.FOLLOW
    )
    
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
        user_id: 用户 ID
        
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


def check_comment_like_exists(db: Session, user_id: int, comment_id: int) -> bool:
    """
    检查用户是否已点赞评论
    
    Args:
        db: 数据库会话
        user_id: 用户 ID
        comment_id: 评论 ID
        
    Returns:
        是否已点赞
    """
    return (
        db.query(models.Like)
        .filter(models.Like.user_id == user_id, models.Like.comment_id == comment_id)
        .first()
        is not None
    )


def check_reply_like_exists(db: Session, user_id: int, reply_id: int) -> bool:
    """
    检查用户是否已点赞回复
    
    Args:
        db: 数据库会话
        user_id: 用户 ID
        reply_id: 回复 ID
        
    Returns:
        是否已点赞
    """
    return (
        db.query(models.Like)
        .filter(models.Like.user_id == user_id, models.Like.reply_id == reply_id)
        .first()
        is not None
    )


def create_comment_like(db: Session, user_id: int, comment_id: int) -> models.Like:
    """
    创建评论点赞
    
    Args:
        db: 数据库会话
        user_id: 用户 ID
        comment_id: 评论 ID
        
    Returns:
        点赞记录
    """
    existing_like = (
        db.query(models.Like)
        .filter(models.Like.user_id == user_id, models.Like.comment_id == comment_id)
        .first()
    )
    if existing_like:
        return existing_like

    db_like = models.Like(user_id=user_id, comment_id=comment_id)
    db.add(db_like)
    db.commit()
    db.refresh(db_like)
    
    # 创建通知：通知评论作者
    comment = db.query(models.Comment).filter(models.Comment.id == comment_id).first()
    if comment and comment.author_id != user_id:
        create_notification(
            db=db,
            user_id=comment.author_id,
            actor_id=user_id,
            notification_type=models.NotificationType.LIKE_COMMENT,
            comment_id=comment_id
        )
    
    return db_like


def create_reply_like(db: Session, user_id: int, reply_id: int) -> models.Like:
    """
    创建回复点赞
    
    Args:
        db: 数据库会话
        user_id: 用户 ID
        reply_id: 回复 ID
        
    Returns:
        点赞记录
    """
    existing_like = (
        db.query(models.Like)
        .filter(models.Like.user_id == user_id, models.Like.reply_id == reply_id)
        .first()
    )
    if existing_like:
        return existing_like

    db_like = models.Like(user_id=user_id, reply_id=reply_id)
    db.add(db_like)
    db.commit()
    db.refresh(db_like)
    
    # 创建通知：通知回复作者
    reply = db.query(models.Reply).filter(models.Reply.id == reply_id).first()
    if reply and reply.author_id != user_id:
        create_notification(
            db=db,
            user_id=reply.author_id,
            actor_id=user_id,
            notification_type=models.NotificationType.LIKE_REPLY,
            reply_id=reply_id
        )
    
    return db_like


# ==================== 通知相关操作 ====================

def create_notification(
    db: Session,
    user_id: int,
    actor_id: int,
    notification_type: models.NotificationType,
    post_id: int = None,
    comment_id: int = None,
    reply_id: int = None
) -> models.Notification:
    """
    创建通知
    
    Args:
        db: 数据库会话
        user_id: 接收者用户 ID
        actor_id: 发起者用户 ID
        notification_type: 通知类型
        post_id: 关联的帖子 ID（可选）
        comment_id: 关联的评论 ID（可选）
        reply_id: 关联的回复 ID（可选）
        
    Returns:
        通知记录
    """
    # 不通知自己
    if user_id == actor_id:
        print(f"[DEBUG] 跳过通知：user_id={user_id} == actor_id={actor_id}")
        return None
    
    notification = models.Notification(
        user_id=user_id,
        actor_id=actor_id,
        type=notification_type,
        post_id=post_id,
        comment_id=comment_id,
        reply_id=reply_id
    )
    db.add(notification)
    db.commit()
    db.refresh(notification)
    print(f"[DEBUG] 通知创建成功：user_id={user_id}, type={notification_type.value}")
    return notification


def get_user_notifications(
    db: Session,
    user_id: int,
    limit: int = 20,
    is_read: bool = None
) -> list:
    """
    获取用户的通知列表（按时间倒序）
    
    Args:
        db: 数据库会话
        user_id: 用户 ID
        limit: 最大返回数量
        is_read: 是否只返回已读/未读（None 表示全部）
        
    Returns:
        通知列表
    """
    query = db.query(models.Notification).filter(models.Notification.user_id == user_id)
    
    if is_read is not None:
        query = query.filter(models.Notification.is_read == is_read)
    
    notifications = (
        query
        .order_by(models.Notification.created_at.desc())
        .limit(limit)
        .all()
    )
    
    # 为每个通知加载关联对象
    for notif in notifications:
        if notif.post_id:
            notif.post = db.query(models.Post).filter(models.Post.id == notif.post_id).first()
        if notif.comment_id:
            notif.comment = db.query(models.Comment).filter(models.Comment.id == notif.comment_id).first()
        if notif.reply_id:
            notif.reply = db.query(models.Reply).filter(models.Reply.id == notif.reply_id).first()
        notif.actor = db.query(models.User).filter(models.User.id == notif.actor_id).first()
    
    return notifications


def mark_notification_read(db: Session, notification_id: int) -> models.Notification:
    """
    标记通知为已读
    
    Args:
        db: 数据库会话
        notification_id: 通知 ID
        
    Returns:
        通知记录
    """
    notification = db.query(models.Notification).filter(models.Notification.id == notification_id).first()
    if notification:
        notification.is_read = True
        db.commit()
        db.refresh(notification)
    return notification


def mark_all_notifications_read(db: Session, user_id: int) -> int:
    """
    标记用户的所有通知为已读
    
    Args:
        db: 数据库会话
        user_id: 用户 ID
        
    Returns:
        标记的数量
    """
    result = (
        db.query(models.Notification)
        .filter(
            models.Notification.user_id == user_id,
            models.Notification.is_read == False
        )
        .update({"is_read": True})
    )
    db.commit()
    return result


def get_unread_notifications_count(db: Session, user_id: int) -> int:
    """
    获取用户的未读通知数量
    
    Args:
        db: 数据库会话
        user_id: 用户 ID
        
    Returns:
        未读通知数量
    """
    return (
        db.query(models.Notification)
        .filter(
            models.Notification.user_id == user_id,
            models.Notification.is_read == False
        )
        .count()
    )
