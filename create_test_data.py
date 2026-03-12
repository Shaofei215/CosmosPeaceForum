"""
创建测试数据
"""
import sys
sys.path.insert(0, 'social_platform')

from app.database import SessionLocal
from app import crud, schemas

db = SessionLocal()

try:
    # 创建测试用户
    print("创建测试用户...")
    user1 = crud.create_user(db, schemas.UserCreate(username="黑塔", bio="空间站负责人，喜欢转圈圈～"))
    user2 = crud.create_user(db, schemas.UserCreate(username="布洛妮娅", bio="大塔主，认真负责"))
    user3 = crud.create_user(db, schemas.UserCreate(username="希儿", bio="努力成长的量子少女"))
    
    print(f"✓ 创建用户：{user1.username} (ID={user1.id})")
    print(f"✓ 创建用户：{user2.username} (ID={user2.id})")
    print(f"✓ 创建用户：{user3.username} (ID={user3.id})")
    
    # 创建原创帖子
    print("\n创建原创帖子...")
    post1 = crud.create_post(db, schemas.PostCreate(content="今天测试了新的空间站设备，效果不错！转圈圈～ 🌀"), author_id=user1.id)
    post2 = crud.create_post(db, schemas.PostCreate(content="空间站的工作虽然繁忙，但很有意义。"), author_id=user2.id)
    post3 = crud.create_post(db, schemas.PostCreate(content="希儿会继续努力，不辜负大家的期望！"), author_id=user3.id)
    
    print(f"✓ 创建帖子 (ID={post1.id})")
    print(f"✓ 创建帖子 (ID={post2.id})")
    print(f"✓ 创建帖子 (ID={post3.id})")
    
    # 创建转发
    print("\n创建转发...")
    quote1 = crud.create_quote_post(db, quote_from_id=post1.id, author_id=user2.id, content="黑塔女士总是这么有活力。布洛妮娅会继续协助空间站的科研工作。")
    
    print(f"✓ 创建转发 (ID={quote1.id})")
    
    # 创建二级转发
    quote2 = crud.create_quote_post(db, quote_from_id=quote1.id, author_id=user3.id, content="希儿也觉得黑塔姐姐很厉害！我也要更加努力才行！")
    
    print(f"✓ 创建转发 (ID={quote2.id})")
    
    print("\n" + "="*50)
    print("✓ 测试数据创建完成！")
    print("="*50)
    print(f"\n现在有：")
    print(f"  - 3 个用户")
    print(f"  - 3 个原创帖子")
    print(f"  - 2 个转发帖子")
    print(f"\n可以刷新前端页面查看了！")
    
except Exception as e:
    print(f"\n❌ 错误：{e}")
    import traceback
    traceback.print_exc()
finally:
    db.close()
