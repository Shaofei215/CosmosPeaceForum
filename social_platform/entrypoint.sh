#!/bin/bash
set -e

# 应用启动前先执行显式数据库迁移。
python -m alembic -c /app/social_platform/alembic.ini upgrade head

# 启动公开平台服务，Docker 内保持对容器网络监听 8000。
exec python -u -m social_platform --host 0.0.0.0 --port 8000
