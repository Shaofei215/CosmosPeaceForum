# Imaginary Tree 后端 Dockerfile
# FastAPI + PostgreSQL 应用

FROM m.daocloud.io/docker.io/library/python:3.11-slim

# 设置工作目录
WORKDIR /app

# 设置环境变量
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

# 安装系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 创建应用目录
RUN mkdir -p /app/app_platform

# 复制依赖文件
COPY requirements.txt .

# 安装 Python 依赖
RUN pip install --no-cache-dir -r requirements.txt --only-binary :all:

# 复制应用代码和迁移配置（保持 app_platform 包路径）
COPY app/ ./app_platform/app/
COPY alembic/ ./app_platform/alembic/
COPY alembic.ini ./app_platform/alembic.ini
COPY entrypoint.sh ./app_platform/entrypoint.sh
RUN chmod +x /app/app_platform/entrypoint.sh

# 暴露端口
EXPOSE 8000

# 启动命令
CMD ["/app/app_platform/entrypoint.sh"]
