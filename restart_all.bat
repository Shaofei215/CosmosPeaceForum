@echo off
REM 重启所有服务

cd /d "%~dp0"

echo ======================================
echo 🌳 黑塔树 - 重启所有服务
echo ======================================
echo.

REM 停止旧服务
echo [1/4] 停止旧服务...
taskkill /F /FI "WINDOWTITLE eq uvicorn*" > nul 2>&1
taskkill /F /FI "WINDOWTITLE eq python*" > nul 2>&1
timeout /t 2 /nobreak > nul
echo    ✅ 旧服务已停止
echo.

REM 创建日志目录
if not exist "logs" mkdir logs

REM 启动后端
echo [2/4] 启动后端服务...
cd /d "%~dp0social_platform"
start "后端服务" /B e:\1A_Share\code\Herta-Tree\.venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8006
timeout /t 3 /nobreak > nul
echo    ✅ 后端服务已启动
echo    📝 日志：..\logs\backend.log
echo    🔗 地址：http://localhost:8006
echo.

REM 启动前端
echo [3/4] 启动前端服务...
cd /d "%~dp0frontend"
start "前端服务" /B e:\1A_Share\code\Herta-Tree\.venv\Scripts\python.exe -m http.server 3000 --bind 0.0.0.0
timeout /t 2 /nobreak > nul
echo    ✅ 前端服务已启动
echo    📝 日志：..\logs\frontend.log
echo    🔗 地址：http://localhost:3000
echo.

REM 启动 LangGraph 调度器
echo [4/4] 启动 LangGraph AI 调度器...
cd /d "%~dp0agent_schedular"
start "LangGraph 调度器" /B e:\1A_Share\code\Herta-Tree\.venv\Scripts\python.exe test_langgraph.py --version langgraph
echo    ✅ LangGraph 调度器已启动
echo    📝 日志：..\logs\langgraph.log
echo.

echo ======================================
echo ✅ 所有服务已重启!
echo ======================================
echo.
echo 访问地址:
echo   🌐 前端：http://localhost:3000
echo   🔌 后端：http://localhost:8006/docs
echo.
echo 查看日志:
echo   type ..\logs\backend.log
echo   type ..\logs\frontend.log
echo   type ..\logs\langgraph.log
echo.
echo 停止服务：stop.bat
echo.
pause
