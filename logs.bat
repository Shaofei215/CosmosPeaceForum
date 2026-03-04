@echo off
REM 黑塔树 - 实时日志查看脚本 (Windows)

cd /d "%~dp0"

set LOGS_DIR=%~dp0logs

echo ======================================
echo 📊 黑塔树 - 实时日志查看
echo ======================================
echo.

REM 检查日志目录
if not exist "%LOGS_DIR%" (
    echo ⚠️  日志目录不存在，请先启动服务
    echo    运行：start.bat
    pause
    exit /b 1
)

REM 检查日志文件
dir /b "%LOGS_DIR%\*.log" > nul 2>&1
if errorlevel 1 (
    echo ⚠️  未找到日志文件，请先启动服务
    echo    运行：start.bat
    pause
    exit /b 1
)

echo ✓ 找到以下日志文件:
echo.

dir /b "%LOGS_DIR%\*.log" | find /n "" /v ""

echo.
echo ======================================
echo 按 Ctrl+C 退出日志查看
echo ======================================
echo.

REM 使用 PowerShell 的 Get-Content -Wait 实时查看日志
powershell -Command "Get-ChildItem '%LOGS_DIR%\*.log' | ForEach-Object { Get-Content $_.FullName -Wait }"
