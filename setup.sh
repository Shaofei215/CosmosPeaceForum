#!/bin/bash

# 黑塔树 - 依赖安装脚本 (Linux/Mac)

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

echo "======================================"
echo "📦 黑塔树 - 安装依赖"
echo "======================================"
echo ""

# 颜色定义
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# 检测 Python
PYTHON_CMD=""
if command -v python3 &> /dev/null; then
    PYTHON_CMD="python3"
elif command -v python &> /dev/null; then
    PYTHON_CMD="python"
else
    echo -e "${RED}❌ 错误：未找到 Python${NC}"
    exit 1
fi

echo -e "${GREEN}✓ 使用 Python: $PYTHON_CMD${NC}"
echo ""

# 安装后端依赖
echo -e "${GREEN}[1/3] 安装后端依赖...${NC}"
if [ -f "$SCRIPT_DIR/social_platform/requirements.txt" ]; then
    cd "$SCRIPT_DIR/social_platform"
    $PYTHON_CMD -m pip install -r requirements.txt -q
    echo "   ✅ 后端依赖安装完成"
else
    echo -e "${YELLOW}⚠️  未找到后端 requirements.txt${NC}"
fi
echo ""

# 安装前端依赖（如果有）
echo -e "${GREEN}[2/3] 检查前端依赖...${NC}"
if [ -f "$SCRIPT_DIR/frontend/requirements.txt" ]; then
    cd "$SCRIPT_DIR/frontend"
    $PYTHON_CMD -m pip install -r requirements.txt -q
    echo "   ✅ 前端依赖安装完成"
else
    echo "   ℹ️  前端无需额外依赖"
fi
echo ""

# 安装 AI 调度器依赖
echo -e "${GREEN}[3/3] 安装 AI 调度器依赖...${NC}"
if [ -f "$SCRIPT_DIR/agent_schedular/requirements.txt" ]; then
    cd "$SCRIPT_DIR/agent_schedular"
    $PYTHON_CMD -m pip install -r requirements.txt -q
    echo "   ✅ AI 调度器依赖安装完成"
else
    echo -e "${YELLOW}⚠️  未找到 AI 调度器 requirements.txt${NC}"
fi
echo ""

echo "======================================"
echo -e "${GREEN}✅ 所有依赖安装完成!${NC}"
echo "======================================"
echo ""
echo "现在可以运行：./start.sh"
echo ""
