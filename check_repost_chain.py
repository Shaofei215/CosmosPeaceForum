"""
检查转发链数据
"""
import sys
sys.path.insert(0, 'social_platform')

from app.database import SessionLocal
from app import models

db = SessionLocal()

try:
    # 获取所有转发帖子
    quotes = db.query(models.Post).filter(
        models.Post.post_type == 'quote'
    ).order_by(models.Post.id).all()
    
    print("=" * 60)
    print("转发帖子数据检查")
    print("=" * 60)
    
    for quote in quotes:
        print(f"\n帖子 ID={quote.id}")
        print(f"  作者：{quote.author.username}")
        print(f"  内容：{quote.content[:50]}...")
        print(f"  post_type: {quote.post_type}")
        print(f"  quote_from_id: {quote.quote_from_id}")
        print(f"  repost_type: {quote.repost_type}")
        print(f"  comment_id: {quote.comment_id}")
        print(f"  reply_id: {quote.reply_id}")
        print(f"  quote_comment: {quote.quote_comment}")
        
        # 检查 quote_from
        if quote.quote_from:
            print(f"  quote_from 帖子:")
            print(f"    ID={quote.quote_from.id}")
            print(f"    作者：{quote.quote_from.author.username}")
            print(f"    类型：{quote.quote_from.post_type}")
            print(f"    内容：{quote.quote_from.content[:30]}...")
    
    # 特别检查 E 的帖子
    print("\n" + "=" * 60)
    print("E 的帖子详细信息")
    print("=" * 60)
    
    user_e = db.query(models.User).filter(models.User.username == "用户 E").first()
    if user_e:
        post_e = db.query(models.Post).filter(
            models.Post.author_id == user_e.id
        ).first()
        
        if post_e:
            print(f"E 的帖子 ID={post_e.id}")
            print(f"  quote_from_id={post_e.quote_from_id}")
            
            # 追溯 quote_from 链
            current_id = post_e.quote_from_id
            depth = 0
            while current_id and depth < 10:
                current_post = db.query(models.Post).filter(
                    models.Post.id == current_id
                ).first()
                if current_post:
                    print(f"  第{depth+1}层：ID={current_post.id}, 作者={current_post.author.username}, 类型={current_post.post_type}")
                    current_id = current_post.quote_from_id
                    depth += 1
                else:
                    break
    
finally:
    db.close()
