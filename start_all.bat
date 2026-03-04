@echo off
chcp 65001 >nul
echo ========================================
echo     黑塔树 - 一键启动所有服务
echo ========================================
echo.

:: 启动后端服务
echo [1/3] 启动后端服务...
start "后端服务" cmd /k "cd /d %~dp0social_platform && uvicorn app.main:app --host 0.0.0.0 --port 8006 --reload"
timeout /t 3 /nobreak >nul

:: 启动前端服务
echo [2/3] 启动前端服务...
start "前端服务" cmd /k "cd /d %~dp0frontend && python -m http.server 3000 --bind 0.0.0.0"
timeout /t 2 /nobreak >nul

:: 启动 Agent 调度器
echo [3/3] 启动 Agent 调度器...
start "Agent 调度器" cmd /k "cd /d %~dp0agent_sched