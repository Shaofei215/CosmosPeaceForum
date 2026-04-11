#!/bin/bash
set -e

# 确保数据目录存在并有正确权限
mkdir -p /app/data
chmod 777 /app/data

# 启动应用（使用新的包名路径）
exec uvicorn app_platform.app.main:app --host 0.0.0.0 --port 8000