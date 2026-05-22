#!/bin/bash
set -e

# 应用启动前先执行显式数据库迁移。
python -m alembic -c /app/social_platform/alembic.ini upgrade head

# 启动应用（使用新的包名路径）
exec uvicorn social_platform.app.main:app --host 0.0.0.0 --port 8000
