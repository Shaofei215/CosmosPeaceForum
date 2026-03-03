"""创建数据库表"""
import sys
sys.path.append('social_platform')

from app.database import engine
from app import models

print("正在创建数据库表...")
models.Base.metadata.create_all(bind=engine)
print("数据库表创建完成！")

# 显示所有表
from sqlalchemy import inspect
inspector = inspect(engine)
print("\n现有表:")
for table_name in inspector.get_table_names():
    print(f"  - {table_name}")
