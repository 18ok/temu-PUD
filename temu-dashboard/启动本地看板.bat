@echo off
chcp 65001 >nul
cd /d "%~dp0"
title Temu 看板 V10

echo.
echo   ╔══════════════════════════════════════╗
echo   ║     Temu 运营看板 V10 — 启动中...    ║
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
echo.
start "" http://localhost:8080/temu-dashboard.html

echo   ╔══════════════════════════════════════╗
echo   ║  浏览器已打开看板                     ║
echo   ║  http://localhost:8080               ║
echo   ║                                      ║
echo   ║  关闭此窗口 = 停止服务                ║
echo   ╚══════════════════════════════════════╝
echo.

python local_server.py

pause
