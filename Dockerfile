# Imaginary Tree 统一 Dockerfile
# 支持 app_platform 后端和 agents 调度器
#
# 使用方法：
# 1. 构建镜像：docker build -t herta-tree .
# 2. 运行后端：docker run -p 8000:8000 herta-tree
# 3. 运行调度器：docker run herta-tree python -m agents

# 基于 Python 3.11 精简版镜像（使用国内镜像加速）
FROM m.daocloud.io/docker.io/library/python:3.11-slim

# 设置工作目录
WORKDIR /app

# Python 环境配置
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

# 安装系统依赖（build-essential 用于编译某些 Python 包，curl 用于健康检查）
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 创建数据目录
RUN mkdir -p /app/data /app/app_platform/data && \
    chmod 777 /app/data /app/app_platform/data

# 复制依赖配置文件（分开复制利用 Docker 缓存）
COPY requirements.txt ./

# 安装 Python 依赖
RUN pip install --no-cache-dir -r requirements.txt

# 复制整个项目代码
COPY . .

# 设置入口脚本执行权限
RUN chmod +x /app/agents/entrypoint.sh /app/app_platform/entrypoint.sh

# 暴露端口
EXPOSE 8000

# 启动命令（默认启动后端服务）
CMD ["uvicorn", "app_platform.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
