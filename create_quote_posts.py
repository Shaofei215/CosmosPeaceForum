"""
手动创建测试转发帖子
验证转发功能和前端展示
"""
import sys
sys.path.insert(0, 'social_platform')

from app.database import SessionLocal
from app import crud, schemas

db = SessionLocal()

try:
    # 获取现有用户
    users = db.query(crud.models.User).all()
    users_dict = {user.username: user for user in users}
    
    print("=" * 60)
    print("当前用户列表:")
    print("=" * 60)
    for username, user in users_dict.items():
        print(f"  - {username} (ID={user.id})")
    
    # 获取所有原创帖子
    original_posts = db.query(crud.models.Post).filter(
        crud.models.Post.post_type == 'original'
    ).all()
    
    print(f"\n找到 {len(original_posts)} 个原创帖子")
    
    # 创建一些转发
    print("\n" + "=" * 60)
    print("开始创建转发帖子...")
    print("=" * 60)
    
    # 转发 1：布洛妮娅转发三月七
    if '三月七' in users_dict and len(original_posts) > 0:
        post = original_posts[0]  # 第一个帖子
        quote1 = crud.create_quote_post(
            db,
            quote_from_id=post.id,
            author_id=users_dict['布洛妮娅'].id,
            content="三月七，还是那么活泼呢。不过工作也要认真完成哦。"
        )
        print(f"✓ 布洛妮娅转发了帖子 ID={post.id}: {quote1.content[:30]}...")
    
    # 转发 2：艾丝妲转发黑塔空间站官方
    station_post = db.query(crud.models.Post).filter(
        crud.models.Post.author_id == users_dict['黑塔空间站官方'].id
    ).first()
    
    if station_post and '艾丝妲' in users_dict:
        quote2 = crud.create_quote_post(
            db,
            quote_from_id=station_post.id,
            author_id=users_dict['艾丝妲'].id,
            content="欢迎大家来黑塔空间站参观！我会为大家提供最好的服务～"
        )
        print(f"✓ 艾丝妲转发了帖子 ID={station_post.id}: {quote2.content[:30]}...")
    
    # 转发 3：青雀转发布洛妮娅的转发（二级转发）
    if '青雀' in users_dict:
        # 获取布洛妮娅的转发
        bronya_quote = db.query(crud.models.Post).filter(
            crud.models.Post.author_id == users_dict['布洛妮娅'].id,
            crud.models.Post.post_type == 'quote'
        ).first()
        
        if bronya_quote:
            quote3 = crud.create_quote_post(
                db,
                quote_from_id=bronya_quote.id,
                author_id=users_dict['青雀'].id,
                content="啊...工作什么的，还是改天再说吧～先让我摸会儿鱼..."
            )
            print(f"✓ 青雀转发了帖子 ID={bronya_quote.id}: {quote3.content[:30]}...")
    
    # 转发 4：星穹列车官方转发贝洛伯格政府官方
    belobog_post = db.query(crud.models.Post).filter(
        crud.models.Post.author_id == users_dict['贝洛伯格政府官方'].id
    ).first()
    
    if belobog_post and '星穹列车官方' in users_dict:
        quote4 = crud.create_quote_post(
            db,
            quote_from_id=belobog_post.id,
            author_id=users_dict['星穹列车官方'].id,
            content="感谢贝洛伯格政府对空间站工作的支持！愿我们的友谊长存～"
        )
        print(f"✓ 星穹列车官方转发了帖子 ID={belobog_post.id}: {quote4.content[:30]}...")
    
    # 统计
    total_posts = db.query(crud.models.Post).count()
    original_count = db.query(crud.models.Post).filter(
        crud.models.Post.post_type == 'original'
    ).count()
    quote_count = db.query(crud.models.Post).filter(
        crud.models.Post.post_type == 'quote'
    ).count()
    
    print("\n" + "=" * 60)
    print("✓ 转发创建完成！")
    print("=" * 60)
    print(f"\n当前数据库状态:")
    print(f"  - 总帖子数：{total_posts}")
    print(f"  - 原创帖子：{original_count}")
    print(f"  - 转发帖子：{quote_count}")
    print(f"\n现在刷新前端页面，可以看到转发展示效果了！")
    
except Exception as e:
    print(f"\n❌ 错误：{e}")
    import traceback
    traceback.print_exc()
finally:
    db.close()
