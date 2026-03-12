"""
检查转发计数
"""
import sys
sys.path.insert(0, 'social_platform')

from app.database import SessionLocal
from app import models
from app.crud import count_all_reposts

db = SessionLocal()

try:
    # 获取所有帖子
    posts = db.query(models.Post).order_by(models.Post.id).all()
    
    print("=" * 60)
    print("帖子数据检查")
    print("=" * 60)
    
    for post in posts:
        print(f"\n帖子 ID={post.id}")
        print(f"  作者：{post.author.username}")
        print(f"  post_type: {post.post_type}")
        print(f"  quote_from_id: {post.quote_from_id}")
        print(f"  original_post_id: {post.original_post_id}")
        
        # 直接转发数
        direct_count = db.query(models.Post).filter(
            models.Post.quote_from_id == post.id
        ).count()
        print(f"  直接转发数：{direct_count}")
        
        # 递归转发数
        total_count = count_all_reposts(db, post.id)
        print(f"  递归转发数：{total_count}")
        
        # 查询所有 quote_from_id=1 的帖子
        if post.id == 1:
            reposts = db.query(models.Post).filter(
                models.Post.quote_from_id == post.id
            ).all()
            print(f"  直接转发的帖子：{[(r.id, r.author.username) for r in reposts]}")
            
            # 检查 E 的 quote_from_id
            post_e = db.query(models.Post).filter(
                models.Post.author_id == 3  # E 的 ID
            ).first()
            if post_e:
                print(f"  E 的帖子：ID={post_e.id}, quote_from_id={post_e.quote_from_id}")
    
finally:
    db.close()
