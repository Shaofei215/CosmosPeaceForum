@echo off
REM 实时查看日志文件

cd /d "%~dp0"

echo ======================================
echo 🌳 黑塔树 - 实时日志查看
echo ======================================
echo.
echo 按 Ctrl+C 退出
echo.
echo [1] 查看后端日志
echo [2] 查看前端日志  
echo [3] 查看 LangGraph 日志
echo [4] 查看所有日志 (分屏)
echo.

set /p choice="请选择 (1-4): "

if "%choice%"=="1" (
    type logs\backend.log
    goto :end
)

if "%choice%"=="2" (
    type logs\frontend.log
    goto :end
)

if "%choice%"=="3" (
    type logs\langgraph.log
    goto :end
)

if "%choice%"=="4" (
    echo ========== 后端日志 ==========
    type logs\backend.log
    echo.
    echo ========== 前端日志 ==========
    type logs\frontend.log
    echo.
    echo ========== LangGraph 日志 ==========
    type logs\langgraph.log
    goto :end
)

echo 无效选项
:end
pause
