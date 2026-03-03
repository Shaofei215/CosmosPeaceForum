#!/bin/bash

# 黑塔树 - 启动脚本 (Linux/Mac)
# 启动后端、前端和 AI 调度器

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

echo "======================================"
echo "🌳 黑塔树 - 启动服务"
echo "======================================"
echo ""

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 检查 Python
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}❌ 错误：未找到 Python3${NC}"
    exit 1
fi

# 检查 Node.js (可选，如果有前端构建步骤)
# if ! command -v node &> /dev/null; then
#     echo -e "${YELLOW}⚠️  警告：未找到 Node.js${NC}"
# fi

# 创建日志目录
mkdir -p logs

# 启动后端服务
echo -e "${GREEN}[1/3] 启动后端服务...${NC}"
cd "$SCRIPT_DIR/social_platform"
nohup python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8006 --reload > "$SCRIPT_DIR/logs/backend.log" 2>&1 &
BACKEND_PID=$!
echo "   ✅ 后端服务已启动 (PID: $BACKEND_PID)"
echo "   📝 日志：logs/backend.log"
echo "   🔗 地址：http://localhost:8006"
echo ""

# 等待后端启动
sleep 3

# 启动前端服务
echo -e "${GREEN}[2/3] 启动前端服务...${NC}"
cd "$SCRIPT_DIR/frontend"
nohup python3 -m http.server 3000 --bind 0.0.0.0 > "$SCRIPT_DIR/logs/frontend.log" 2>&1 &
FRONTEND_PID=$!
echo "   ✅ 前端服务已启动 (PID: $FRONTEND_PID)"
echo "   📝 日志：logs/frontend.log"
echo "   🔗 地址：http://localhost:3000"
echo ""

# 启动 AI 调度器
echo -e "${GREEN}[3/3] 启动 AI 调度器...${NC}"
cd "$SCRIPT_DIR/agent_schedular"
nohup python3 main.py > "$SCRIPT_DIR/logs/agent.log" 2>&1 &
AGENT_PID=$!
echo "   ✅ AI 调度器已启动 (PID: $AGENT_PID)"
echo "   📝 日志：logs/agent.log"
echo ""

# 保存 PID 到文件
echo "$BACKEND_PID" > "$SCRIPT_DIR/logs/backend.pid"
echo "$FRONTEND_PID" > "$SCRIPT_DIR/logs/frontend.pid"
echo "$AGENT_PID" > "$SCRIPT_DIR/logs/agent.pid"

echo "======================================"
echo -e "${GREEN}✅ 所有服务已启动!${NC}"
echo "======================================"
echo ""
echo "访问地址:"
echo "  🌐 前端：http://localhost:3000"
echo "  🔌 后端：http://localhost:8006"
echo ""
echo "停止服务：./stop.sh"
echo "查看日志：tail -f logs/*.log"
echo ""
