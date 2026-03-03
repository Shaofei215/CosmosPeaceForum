@echo off
REM 黑塔树 - 启动脚本 (Windows)
REM 启动后端、前端和 AI 调度器

cd /d "%~dp0"

echo ======================================
echo 🌳 黑塔树 - 启动服务
echo ======================================
echo.

REM 创建日志目录
if not exist "logs" mkdir logs

REM 启动后端服务
echo [1/3] 启动后端服务...
cd /d "%~dp0social_platform"
start /B python -m uvicorn app.main:app --host 0.0.0.0 --port 8006 --reload > "%~dp0logs\backend.log" 2>&1
echo    ✅ 后端服务已启动
echo    📝 日志：logs\backend.log
echo    🔗 地址：http://localhost:8006
echo.

timeout /t 3 /nobreak > nul

REM 启动前端服务
echo [2/3] 启动前端服务...
cd /d "%~dp0frontend"
start /B python -m http.server 3000 --bind 0.0.0.0 > "%~dp0logs\frontend.log" 2>&1
echo    ✅ 前端服务已启动
echo    📝 日志：logs\frontend.log
echo    🔗 地址：http://localhost:3000
echo.

REM 启动 AI 调度器
echo [3/3] 启动 AI 调度器...
cd /d "%~dp0agent_schedular"
start /B python main.py > "%~dp0logs\agent.log" 2>&1
echo    ✅ AI 调度器已启动
echo    📝 日志：logs\agent.log
echo.

echo ======================================
echo ✅ 所有服务已启动!
echo ======================================
echo.
echo 访问地址:
echo   🌐 前端：http://localhost:3000
echo   🔌 后端：http://localhost:8006
echo.
echo 停止服务：stop.bat
echo 查看日志：type logs\*.log
echo.
pause
