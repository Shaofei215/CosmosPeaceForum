"""
检查转发数据
"""
import sys
sys.path.insert(0, 'social_platform')

from app.database import SessionLocal
from app import models

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
        print(f"  内容：{post.content[:50]}...")
        print(f"  post_type: {post.post_type}")
        print(f"  quote_from_id: {post.quote_from_id}")
        print(f"  original_post_id: {post.original_post_id}")
        print(f"  hot_score: {post.hot_score}")
        
        # 检查 original_post
        if post.original_post_id:
            original_post = db.query(models.Post).filter(
                models.Post.id == post.original_post_id
            ).first()
            if original_post:
                print(f"  original_post: ID={original_post.id}, 作者={original_post.author.username}, 内容={original_post.content[:20]}...")
    
finally:
    db.close()
