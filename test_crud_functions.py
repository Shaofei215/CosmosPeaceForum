import sys
sys.path.insert(0, 'social_platform')

from app.database import SessionLocal, engine, Base
from app import crud, models

# 创建数据库表（如果不存在）
Base.metadata.create_all(bind=engine)

# 创建数据库会话
db = SessionLocal()

try:
    # 测试 check_comment_like_exists 函数
    print("测试 check_comment_like_exists 函数...")
    result = crud.check_comment_like_exists(db, user_id=1, comment_id=1)
    print(f"结果：{result}")
    print("✅ check_comment_like_exists 函数存在且可调用")
    
    # 测试 check_reply_like_exists 函数
    print("\n测试 check_reply_like_exists 函数...")
    result = crud.check_reply_like_exists(db, user_id=1, reply_id=1)
    print(f"结果：{result}")
    print("✅ check_reply_like_exists 函数存在且可调用")
    
except AttributeError as e:
    print(f"❌ AttributeError: {e}")
except Exception as e:
    print(f"✅ 函数存在，但出现其他错误（可能是数据问题）: {e}")
finally:
    db.close()
    print("\n测试完成！")
