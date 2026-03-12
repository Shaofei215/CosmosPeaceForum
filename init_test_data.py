"""
初始化测试数据脚本
创建初始用户和帖子
"""
import sys
sys.path.insert(0, 'social_platform')

from app.database import SessionLocal
from app import crud, schemas
import json

db = SessionLocal()

try:
    # 读取初始帖子配置
    with open('initial_posts.json', 'r', encoding='utf-8') as f:
        config = json.load(f)
    
    initial_posts = config.get('initial_posts', [])
    
    print("=" * 60)
    print("开始初始化测试数据...")
    print("=" * 60)
    
    # 创建用户和帖子
    created_users = {}
    
    for post_data in initial_posts:
        username = post_data.get('username')
        content = post_data.get('content')
        
        if not username or not content:
            continue
        
        # 如果用户不存在，创建用户
        if username not in created_users:
            existing_user = crud.get_user_by_username(db, username)
            if not existing_user:
                user = crud.create_user(
                    db, 
                    schemas.UserCreate(username=username, bio=f"{username}的官方账号")
                )
                created_users[username] = user
                print(f"✓ 创建用户：{username} (ID={user.id})")
            else:
                created_users[username] = existing_user
                print(f"✓ 用户已存在：{username} (ID={existing_user.id})")
        
        # 创建帖子
        user = created_users[username]
        post = crud.create_post(
            db,
            schemas.PostCreate(content=content),
            author_id=user.id
        )
        print(f"  → 创建帖子：{content[:30]}...")
    
    print("\n" + "=" * 60)
    print("✓ 初始化完成！")
    print("=" * 60)
    
    # 统计
    users_count = db.query(crud.models.User).count()
    posts_count = db.query(crud.models.Post).count()
    print(f"\n当前数据库状态:")
    print(f"  - 用户数：{users_count}")
    print(f"  - 帖子数：{posts_count}")
    print(f"\n现在可以刷新前端页面查看了！")
    
except Exception as e:
    print(f"\n❌ 错误：{e}")
    import traceback
    traceback.print_exc()
finally:
    db.close()
