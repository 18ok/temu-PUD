@echo off
chcp 65001 >nul
cd /d "%~dp0"
title Temu 选品助手 V10.3 — 本地开发

echo.
echo   ╔══════════════════════════════════════╗
echo   ║  Temu 选品助手 V10.3 — 本地开发        ║
echo   ╚══════════════════════════════════════╝
echo.

:: ========== 1. 检查 Python ==========
echo [1/3] 检查 Python...
where python >nul 2>&1
if %errorlevel% neq 0 (
    echo.
    echo   ❌ 未检测到 Python！
    echo.
    echo   📥 请先安装 Python 3：
    echo      https://www.python.org/downloads/
    echo.
    echo   ⚠️ 安装时务必勾选 "Add Python to PATH"
    echo.
    pause
    exit /b 1
)

for /f "tokens=2" %%v in ('python --version 2^>^&1') do set PYVER=%%v
echo   ✅ Python %PYVER%

:: ========== 2. 检查依赖（只用标准库，无需 pip install） ==========
echo [2/3] 检查依赖...
echo   ✅ 使用 Python 标准库，无需额外安装

:: ========== 3. 启动服务 ==========
echo [3/3] 启动本地服务...
echo   浏览器将在服务就绪后自动打开...
echo.
start "" /min python -c "import time,urllib.request,webbrowser; url='http://localhost:8080/temu-dashboard.html#import'; probe='http://localhost:8080/temu-dashboard.html'; exec('for _ in range(40):\n    try:\n        urllib.request.urlopen(probe,timeout=1).close(); break\n    except Exception:\n        time.sleep(0.5)'); webbrowser.open(url)"

echo   ╔══════════════════════════════════════╗
echo   ║  浏览器就绪后自动打开                 ║
echo   ║  http://localhost:8080               ║
echo   ║                                      ║
echo   ║  同事请用网页版（无需 bat）：           ║
echo   ║  https://18ok.github.io/temu-PUD/     ║
echo   ║                                      ║
echo   ║  本窗口：api_server · OSS · 协作 API   ║
echo   ║  协作数据目录：OSS collab/             ║
echo   ║                                      ║
echo   ║  关闭此窗口 = 停止服务                ║
echo   ╚══════════════════════════════════════╝
echo.

python api_server.py

pause
