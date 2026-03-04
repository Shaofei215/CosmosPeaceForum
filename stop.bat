@echo off
REM 黑塔树 - 停止脚本 (Windows)
REM 停止后端、前端和 AI 调度器

cd /d "%~dp0"

echo ======================================
echo 🛑 黑塔树 - 停止服务
echo ======================================
echo.

echo 正在停止服务...
echo.

REM 停止后端服务 (uvicorn)
taskkill /F /FI "WINDOWTITLE eq uvicorn*" /IM python.exe > nul 2>&1
taskkill /F /FI "WINDOWTITLE eq *uvicorn*" /IM python.exe > nul 2>&1
for /f "tokens=5" %%a in ('netstat -aon ^| find ":8006" ^| find "LISTENING"') do (
    for /f "tokens=5" %%b in ('tasklist /FI "PID eq %%a" /FO TABLE /NH') do (
        echo %%b | find "python" > nul && taskkill /F /PID %%a > nul 2>&1
    )
)
echo    ✅ 后端服务已停止

REM 停止前端服务 (http.server 3000)
for /f "tokens=5" %%a in ('netstat -aon ^| find ":3000" ^| find "LISTENING"') do (
    for /f "tokens=5" %%b in ('tasklist /FI "PID eq %%a" /FO TABLE /NH') do (
        echo %%b | find "python" > nul && taskkill /F /PID %%a > nul 2>&1
    )
)
echo    ✅ 前端服务已停止

REM 停止 AI 调度器
taskkill /F /FI "WINDOWTITLE eq *agent_schedular*" /IM python.exe > nul 2>&1
for /f "tokens=2" %%a in ('tasklist /FI "IMAGENAME eq python.exe" /FO CSV /NH ^| findstr /C:"main.py"') do (
    taskkill /F /PID %%a > nul 2>&1
)
echo    ✅ AI 调度器已停止

echo.
echo ======================================
echo ✅ 所有服务已停止
echo ======================================
echo.
pause
